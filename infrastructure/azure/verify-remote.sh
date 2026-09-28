#!/usr/bin/env bash
set -euo pipefail

echo "CONTAINERS"
docker ps -a --format '{{.Names}}|{{.Status}}|{{.Image}}'

echo "QDRANT"
docker exec -i retail-recommendation-azure-api-1 python - <<'PY'
from qdrant_client import QdrantClient

info = QdrantClient(
    url="http://qdrant:6333",
    check_compatibility=False,
).get_collection("retail_items")
print(f"points_count={info.points_count}")
print(f"status={info.status}")
PY

echo "API_METRICS"
docker exec retail-recommendation-azure-api-1 python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/metrics').read().decode(), end='')"

echo "INDEXER_LOGS"
docker logs --tail 10 retail-recommendation-azure-qdrant-indexer-1 2>&1
