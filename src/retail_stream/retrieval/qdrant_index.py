from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np


def index_item_embeddings(
    model_dir: str | Path,
    qdrant_url: str,
    collection_name: str,
    batch_size: int = 2048,
    skip_if_ready: bool = False,
) -> int:
    from qdrant_client import QdrantClient, models

    model_dir = Path(model_dir)
    item_ids = np.load(model_dir / "item_ids.npy")
    embeddings = np.load(model_dir / "item_embeddings.npy")
    client = QdrantClient(url=qdrant_url)
    collection_exists = client.collection_exists(collection_name)
    if collection_exists and skip_if_ready:
        collection = client.get_collection(collection_name)
        if collection.points_count == len(item_ids):
            return len(item_ids)
    if collection_exists:
        client.delete_collection(collection_name)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=embeddings.shape[1], distance=models.Distance.COSINE
        ),
    )
    for start in range(0, len(item_ids), batch_size):
        end = min(start + batch_size, len(item_ids))
        points = [
            models.PointStruct(
                id=int(item_ids[index]),
                vector=embeddings[index].tolist(),
                payload={"item_id": int(item_ids[index])},
            )
            for index in range(start, end)
        ]
        client.upsert(collection_name=collection_name, points=points, wait=True)
    return len(item_ids)


class QdrantVectorIndex:
    def __init__(self, url: str, collection_name: str) -> None:
        from qdrant_client import QdrantClient

        self.client = QdrantClient(url=url)
        self.collection_name = collection_name

    def search(self, query, k: int, excluded_item_ids=()):
        excluded = set(map(int, excluded_item_ids))
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=query.tolist(),
            limit=min(k + len(excluded) + 100, 1000),
            with_payload=True,
        ).points
        recommendations = []
        for point in result:
            item_id = int((point.payload or {}).get("item_id", point.id))
            if item_id in excluded:
                continue
            recommendations.append((item_id, float(point.score)))
            if len(recommendations) == k:
                break
        return recommendations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load trained item embeddings into Qdrant")
    parser.add_argument("--model-dir", default=os.getenv("MODEL_DIR", "artifacts/model"))
    parser.add_argument("--url", default=os.getenv("QDRANT_URL", "http://localhost:6333"))
    parser.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION", "retail_items"))
    parser.add_argument(
        "--skip-if-ready",
        action="store_true",
        help="Keep an existing collection when its point count matches the model artifacts",
    )
    args = parser.parse_args(argv)
    count = index_item_embeddings(
        args.model_dir,
        args.url,
        args.collection,
        skip_if_ready=args.skip_if_ready,
    )
    print(f"indexed {count} item embedding(s) into {args.collection}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
