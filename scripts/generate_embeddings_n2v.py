from pathlib import Path
from hashlib import md5
import json
import logging
import os

import networkx as nx
import pandas as pd
from node2vec import Node2Vec
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "database"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "generate_embeddings.log"
PROGRESS_FMT = "{desc}: {n:,} / {total:,} {unit} [{elapsed}, {rate_fmt}]"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",
)


def clean_friends(friends_str: str, valid_users: set[str]) -> list[str]:
    """
    Return valid friend ids with '_u' suffix.
    """
    if friends_str == "None":
        return []
    friends = {f"{uid}_u" for uid in friends_str.split(",")}
    return list(friends & valid_users)


def category_to_hash_list(cat_str: str) -> list[str]:
    """
    Turn category string into md5-hashed token list.
    """

    if not cat_str or cat_str == "None":
        return []
    cat_tokens = [
        token.replace("&", " ")
        .replace("/", " ")
        .replace("   ", " ")
        .strip()
        for token in cat_str.split(",")
    ]
    return [md5(tok.encode("utf-8")).hexdigest() for tok in cat_tokens if tok]


def main() -> None:
    logging.info("=== Embedding generation started ===")

    # 1. Load all interaction data
    logging.info("Loading CSVs...")
    yelp_data = pd.read_csv(DATA_DIR / "Yelp_final.csv",
                            usecols=["user_id", "business_id", "stars"])
    yelp_data["user_id"] = yelp_data["user_id"].astype(str) + "_u"
    yelp_data["business_id"] = yelp_data["business_id"].astype(str) + "_b"

    user_ids: set[str] = set(yelp_data["user_id"])
    biz_ids: set[str] = set(yelp_data["business_id"])

    # 2. Load business + user meta
    logging.info("Loading business.json and user.json...")
    business_df = pd.DataFrame(map(json.loads, open(DATA_DIR
                                                    / "yelp_academic_dataset_business.json",
                                                    encoding="utf-8")))
    business_df["business_id"] = business_df["business_id"].astype(str) + "_b"
    business_df = business_df[business_df["business_id"].isin(biz_ids)].reset_index(drop=True)

    user_df = pd.DataFrame(map(json.loads, open(DATA_DIR
                                                / "yelp_academic_dataset_user.json",
                                                encoding="utf-8")))
    user_df["user_id"] = user_df["user_id"].astype(str) + "_u"
    user_df = user_df[user_df["user_id"].isin(user_ids)].reset_index(drop=True)

    # 3. Build additional edges
    tqdm_kwargs = dict(
        total=len(user_df),
        unit="users",
        dynamic_ncols=True,
        bar_format=PROGRESS_FMT)
    friend_edges: set[tuple[str, str]] = set()
    logging.info("Parsing friendship edges...")
    with logging_redirect_tqdm():
        for _, row in tqdm(user_df.iterrows(), desc="Friendship edges", **tqdm_kwargs):
            uid = row["user_id"]
            for fid in clean_friends(row.get("friends", "None"), user_ids):
                friend_edges.add(tuple(sorted((uid, fid))))

    logging.info("Parsing business-category edges...")
    business_df["cat_list"] = business_df["categories"].map(category_to_hash_list)
    tqdm_kwargs = dict(
        total=len(business_df),
        unit="businesses",
        dynamic_ncols=True,
        bar_format=PROGRESS_FMT)
    biz_cat_edges: set[tuple[str, str]] = set()
    with logging_redirect_tqdm():
        for _, row in tqdm(business_df.iterrows(), desc="Category edges", **tqdm_kwargs):
            bid = row["business_id"]
            for cat in row["cat_list"]:
                biz_cat_edges.add(tuple(sorted((bid, cat))))

    # 4. Write edges.txt
    edges_path = DATA_DIR / "edges.txt"
    logging.info("Writing edges.txt...")
    with edges_path.open("w", encoding="utf-8") as fp, logging_redirect_tqdm():
        # user-business interactions
        tqdm_kwargs = dict(
            total=len(yelp_data),
            unit="pairs",
            dynamic_ncols=True,
            bar_format=PROGRESS_FMT)
        for _, row in tqdm(yelp_data.iterrows(), desc="Interaction edges", **tqdm_kwargs):
            fp.write(f"{row['user_id']} {row['business_id']}\n")

        # friendship
        tqdm_kwargs = dict(
            total=len(friend_edges),
            unit="pairs",
            dynamic_ncols=True,
            bar_format=PROGRESS_FMT)
        for u, v in tqdm(friend_edges, desc="Friend edges write", **tqdm_kwargs):
            fp.write(f"{u} {v}\n")

        # business-category
        tqdm_kwargs = dict(
            total=len(biz_cat_edges),
            unit="pairs",
            dynamic_ncols=True,
            bar_format=PROGRESS_FMT)
        for b, c in tqdm(biz_cat_edges, desc="Biz-cat write", **tqdm_kwargs):
            fp.write(f"{b} {c}\n")

    # 5. Train Node2Vec
    logging.info("Training node2vec...")
    graph = nx.read_edgelist(edges_path, create_using=nx.DiGraph(), data=False)
    n2v = Node2Vec(
        graph,
        dimensions=128,
        walk_length=25,
        num_walks=250,
        p=0.25,
        q=4,
        workers=4,
        seed=42)
    w2v_model = n2v.fit(window=15, epochs=40, workers=4)
    embeddings = {node: w2v_model.wv[node] for node in w2v_model.wv.index_to_key}

    # 6. Save embeddings
    emb_df = (
        pd.DataFrame.from_dict(embeddings, orient="index", columns=[f"E_{i}" for i in range(128)])
        .reset_index()
        .rename(columns={"index": "id"})
    )
    emb_df.to_csv(DATA_DIR / "embeddings.csv", index=False)
    logging.info("Embeddings saved to database/embeddings.csv")
    logging.info("=== Embedding generation finished ===")


if __name__ == "__main__":
    main()
