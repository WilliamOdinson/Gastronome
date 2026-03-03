"""
Management command: ``build_memmap_embeddings``

Converts the business embedding CSV into a memory-mapped float32 binary
file (``biz_emb.f32``) and a companion ``biz_id.npy`` that records the
row-order business IDs. The mem-map allows the recommendation service
to access high-dimensional vectors without loading the entire matrix
into RAM.
"""

import time
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Convert embeddings.csv to memory-mapped float32 matrix"

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            default="database/embeddings.csv",
            help="Input CSV produced by node2vec",
        )
        parser.add_argument(
            "--id_out",
            default="assets/weights/biz_id.npy",
            help="Output NumPy file containing business_id strings "
                 "in the exact order used by the mem-map",
        )
        parser.add_argument(
            "--mm_out",
            default="assets/weights/biz_emb.f32",
            help="Output memory-mapped float32 binary file "
                 "(rows = businesses, cols = 128 dims)",
        )

    def handle(self, *args, **opts):
        t0 = time.time()
        csv_path = Path(opts["csv"])
        id_path = Path(opts["id_out"])
        mm_path = Path(opts["mm_out"])

        self.stdout.write(f"Reading {csv_path} ...")
        emb = pd.read_csv(csv_path)
        biz = emb[emb.id.str.endswith("_b")].copy()
        biz["business_id"] = biz.id.str.rstrip("_b")
        biz.drop(columns="id", inplace=True)
        biz.set_index("business_id", inplace=True)

        ids = biz.index.to_numpy()
        vec = biz.to_numpy(dtype="float32")

        # L2 normalize in place to get cosine similarity for dot product
        norm = np.linalg.norm(vec, axis=1, keepdims=True)
        vec /= np.where(norm == 0, 1.0, norm)

        self.stdout.write("Writing mem-map and id map ...")
        shape = vec.shape
        mm = np.memmap(mm_path, dtype="float32", mode="w+", shape=shape)
        mm[:] = vec
        mm.flush()
        np.save(id_path, ids.astype("U"))

        elapsed = time.time() - t0
        logging.info(
            "mem-map built: %d rows , %d dims (%.2f GB) in %.1f s",
            shape[0],
            shape[1],
            mm.nbytes / 1e9,
            elapsed,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Finished: {shape[0]} vectors -> {mm_path} ({mm.nbytes / 1e9:.2f} GB) "
                f"in {elapsed:.1f}s"
            )
        )
