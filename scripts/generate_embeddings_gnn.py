import json
import logging
from pathlib import Path
from hashlib import md5

import torch
from torch import nn, optim
import torch.nn.functional as F
from torch_geometric.data import HeteroData
from torch_geometric.transforms import ToUndirected, RandomLinkSplit
from torch_geometric.loader import LinkNeighborLoader
from torch_geometric.nn import SAGEConv, GATConv, TransformerConv, BatchNorm, to_hetero
import pandas as pd
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "database"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    filename=LOG_DIR / "generate_embeddings.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",
)
BAR_FMT = "{desc}: {n:,} / {total:,} {unit} [{elapsed}, {rate_fmt}]"


def md5_hash_list(cat_str):
    if not cat_str or cat_str == "None":
        return []
    tokens = [
        tok.replace("&", " ")
        .replace("/", " ")
        .replace("   ", " ")
        .strip()
        for tok in cat_str.split(",")
    ]
    return [md5(tok.encode("utf-8")).hexdigest() for tok in tokens if tok]


def bpr_loss(pos_scores, neg_scores):
    return -torch.mean(F.logsigmoid(pos_scores - neg_scores))


class GNNEncoder(nn.Module):
    """GraphSAGE -> BN -> GAT -> Linear  (*2)  +  SAGE -> Transformer -> Linear  + SAGE *2."""

    def __init__(self, hidden=128, out=128, dropout=0.2):
        super().__init__()
        self.conv1 = SAGEConv((-1, -1), hidden)
        self.bn1 = BatchNorm(hidden)
        self.gat1 = GATConv(hidden, hidden, heads=8, dropout=dropout, add_self_loops=False)
        self.lin1 = nn.Linear(hidden * 8, hidden)

        self.conv2 = SAGEConv((-1, -1), hidden)
        self.bn2 = BatchNorm(hidden)
        self.gat2 = GATConv(hidden, hidden, heads=8, dropout=dropout, add_self_loops=False)
        self.lin2 = nn.Linear(hidden * 8, hidden)

        self.conv3 = SAGEConv((-1, -1), hidden)
        self.trans = TransformerConv(hidden, hidden, heads=4, dropout=dropout)
        self.lin3 = nn.Linear(hidden * 4, hidden)

        self.conv4 = SAGEConv((-1, -1), hidden)
        self.conv5 = SAGEConv((-1, -1), out)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index).relu()
        x = self.bn1(x)
        x = self.gat1(x, edge_index).relu()
        x = self.lin1(x).relu()

        x = self.conv2(x, edge_index).relu()
        x = self.bn2(x)
        x = self.gat2(x, edge_index).relu()
        x = self.lin2(x).relu()

        x = self.conv3(x, edge_index).relu()
        x = self.trans(x, edge_index).relu()
        x = self.lin3(x).relu()

        x = self.conv4(x, edge_index).relu()
        x = self.conv5(x, edge_index)
        return x


class EdgeDecoder(nn.Module):
    """
    Dot-product decoder with two-layer MLP projections.
    """

    def __init__(self, hidden=128, dropout=0.2):
        super().__init__()
        self.user_mlp = nn.Sequential(
            nn.Linear(hidden, hidden * 2), nn.ReLU(), nn.Dropout(dropout), nn.Linear(hidden * 2, hidden)
        )
        self.rest_mlp = nn.Sequential(
            nn.Linear(hidden, hidden * 2), nn.ReLU(), nn.Dropout(dropout), nn.Linear(hidden * 2, hidden)
        )

    def forward(self, z_dict, edge_label_index):
        row, col = edge_label_index
        u_emb = self.user_mlp(z_dict["user"][row])
        r_emb = self.rest_mlp(z_dict["restaurant"][col])
        return (u_emb * r_emb).sum(dim=-1)


class GNNRecModel(nn.Module):
    """
    Encoder + Decoder wrapper.
    """

    def __init__(self, metadata, hidden=128, device=None):
        super().__init__()
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.encoder = to_hetero(GNNEncoder(hidden, hidden), metadata, aggr="sum")
        self.decoder = EdgeDecoder(hidden)
        self.to(self.device)

    def forward(self, x_dict, edge_index_dict, edge_label_index):
        z_dict = self.encoder(x_dict, edge_index_dict)
        return self.decoder(z_dict, edge_label_index)


def main():
    logging.info("=== GNN embedding generation started ===")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # load split data
    train_df = pd.read_csv(DATA_DIR / "yelp_train.csv",
                           usecols=["user_id", "business_id", "stars"])
    val_df = pd.read_csv(DATA_DIR / "yelp_val.csv",
                         usecols=["user_id", "business_id", "stars"])
    test_df = pd.read_csv(DATA_DIR / "yelp_test_ans.csv",
                          usecols=["user_id", "business_id", "stars"])
    for df in (train_df, val_df, test_df):
        df["user_id"] = df["user_id"].astype(str) + "_u"
        df["business_id"] = df["business_id"].astype(str) + "_b"

    users = set(pd.concat([train_df, val_df, test_df])["user_id"])
    rests = set(pd.concat([train_df, val_df, test_df])["business_id"])

    # load meta JSONs
    business_df = pd.DataFrame(
        map(json.loads, open(DATA_DIR / "yelp_academic_dataset_business.json", encoding="utf-8"))
    )
    business_df["business_id"] = business_df["business_id"].astype(str) + "_b"
    business_df = business_df[business_df["business_id"].isin(rests)].reset_index(drop=True)

    user_df = pd.DataFrame(
        map(json.loads, open(DATA_DIR / "yelp_academic_dataset_user.json", encoding="utf-8"))
    )
    user_df["user_id"] = user_df["user_id"].astype(str) + "_u"
    user_df = user_df[user_df["user_id"].isin(users)].reset_index(drop=True)

    # simple numeric features
    business_df["avg_rating"] = business_df["stars"].fillna(0).astype("float32")
    business_df["cat_hash"] = business_df["categories"].map(
        lambda s: len(md5_hash_list(s))).astype("float32")
    user_df["review_cnt"] = user_df["review_count"].fillna(0).astype("float32")
    user_df["useful"] = user_df["useful"].fillna(0).astype("float32")

    # build HeteroData
    data = HeteroData()
    data["restaurant"].x = torch.tensor(
        business_df[["avg_rating", "cat_hash"]].values, dtype=torch.float32)
    data["user"].x = torch.tensor(user_df[["review_cnt", "useful"]].values, dtype=torch.float32)

    rest_id2idx = {bid: i for i, bid in enumerate(business_df["business_id"])}
    user_id2idx = {uid: i for i, uid in enumerate(user_df["user_id"])}

    inter_df = pd.concat([train_df, val_df, test_df], ignore_index=True)
    rows = inter_df["user_id"].map(user_id2idx.get).astype("int64").values
    cols = inter_df["business_id"].map(rest_id2idx.get).astype("int64").values
    data[("user", "reviews", "restaurant")].edge_index = torch.tensor([rows, cols], dtype=torch.long)
    data[("user", "reviews", "restaurant")].edge_attr = torch.tensor(
        inter_df["stars"].values, dtype=torch.float32
    ).unsqueeze(-1)

    data = ToUndirected()(data)

    # train/val/test split
    transform = RandomLinkSplit(
        num_val=0.15,
        num_test=0.15,
        disjoint_train_ratio=0.3,
        neg_sampling_ratio=1.0,
        add_negative_train_samples=False,
        edge_types=[("user", "reviews", "restaurant")],
        rev_edge_types=[("restaurant", "rev_reviews", "user")],
    )
    train_data, val_data, _ = transform(data)

    e_type = ("user", "reviews", "restaurant")
    train_loader = LinkNeighborLoader(
        train_data,
        num_neighbors=[20, 10],
        neg_sampling_ratio=1.0,
        edge_label_index=(e_type, train_data[e_type].edge_label_index),
        edge_label=train_data[e_type].edge_label,
        batch_size=1024,
        shuffle=True,
        num_workers=4,
    )

    # model & optimizer
    model = GNNRecModel(train_data.metadata(), hidden=128, device=device)
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)

    # train with hard-negative BPR
    def train_epoch(epoch):
        model.train()
        tot_loss = tot_examples = 0
        bar = tqdm(train_loader, total=len(train_loader), unit="batch",
                   desc=f"Epoch {epoch}", dynamic_ncols=True, bar_format=BAR_FMT)
        for batch in bar:
            batch = batch.to(device)
            optimizer.zero_grad()

            edge_idx = batch[e_type].edge_label_index
            labels = batch[e_type].edge_label
            pos_mask = labels == 1
            pos_edge = edge_idx[:, pos_mask]
            neg_edge = edge_idx[:, ~pos_mask]

            with torch.no_grad():
                neg_scores = model(batch.x_dict, batch.edge_index_dict, neg_edge)
                hard_idx = neg_scores.argsort(descending=True)[:100]
                hard_neg = neg_edge[:, hard_idx]
                if hard_neg.size(1) < pos_edge.size(1):
                    rand_idx = torch.randint(0, neg_edge.size(1),
                                             (pos_edge.size(1) - hard_neg.size(1),))
                    hard_neg = torch.cat([hard_neg, neg_edge[:, rand_idx]], dim=1)

            pos_out = model(batch.x_dict, batch.edge_index_dict, pos_edge)
            neg_out = model(batch.x_dict, batch.edge_index_dict, hard_neg)

            loss = bpr_loss(pos_out, neg_out)
            loss.backward()
            optimizer.step()

            tot_loss += loss.item() * pos_edge.size(1)
            tot_examples += pos_edge.size(1)
        avg = tot_loss / tot_examples
        logging.info(f"Epoch {epoch} - avg BPR loss: {avg:.6f}")
        return avg

    # early-stopping params
    max_epochs = 50
    min_delta = 1e-3
    patience = 3
    best_loss = float("inf")
    stagnate = 0

    logging.info("Training ...")
    with logging_redirect_tqdm():
        for ep in range(1, max_epochs + 1):
            cur_loss = train_epoch(ep)
            if best_loss - cur_loss > min_delta:
                best_loss = cur_loss
                stagnate = 0
            else:
                stagnate += 1
            if stagnate >= patience:
                logging.info(f"Early stop: no improvement >={min_delta} for {patience} epochs.")
                break

    # dump embeddings
    logging.info("Computing final embeddings on CPU to avoid GPU OOM ...")
    model_cpu = model.to("cpu")
    data_cpu = data.to("cpu")
    model_cpu.eval()
    model.eval()
    with torch.no_grad():
        z_dict = model_cpu.encoder(data_cpu.x_dict, data_cpu.edge_index_dict)
    ids = list(user_df["user_id"]) + list(business_df["business_id"])
    vecs = torch.cat([z_dict["user"].cpu(), z_dict["restaurant"].cpu()], dim=0).numpy()
    emb_df = pd.DataFrame(vecs, columns=[f"E_{i}" for i in range(vecs.shape[1])])
    emb_df.insert(0, "id", ids)
    emb_df.to_csv(DATA_DIR / "embeddings.csv", index=False)
    logging.info("Embeddings saved -> database/embeddings.csv")
    logging.info("=== done ===")


if __name__ == "__main__":
    main()
