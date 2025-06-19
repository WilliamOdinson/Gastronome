import numpy as np
import pandas as pd
import faiss
import time
import logging
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Build FAISS HNSW index over business embeddings"

    def add_arguments(self, p):
        p.add_argument("--emb", default="database/embeddings.csv")
        p.add_argument("--index_out", default="assets/weights/biz_hnsw.index")
        p.add_argument("--map_out", default="assets/weights/biz_id.npy")

    def handle(self, *a, **o):
        t0 = time.time()
        emb = pd.read_csv(o["emb"])
        biz = emb[emb.id.str.endswith("_b")].copy()
        vec = biz.drop(columns="id").values.astype("float32").copy()
        ids64 = np.arange(len(biz), dtype="int64")
        strings = biz.id.str.rstrip("_b").to_numpy()

        faiss.normalize_L2(vec)
        index = faiss.IndexHNSWFlat(vec.shape[1], 32)
        index = faiss.IndexIDMap(index)
        index.add_with_ids(vec, ids64)

        faiss.write_index(index, o["index_out"])
        np.save(o["map_out"], strings.astype("U"))
        logging.info("built %d vectors -> %.1fs", vec.shape[0], time.time() - t0)
