#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
mkdir -p /opt/retail/artifacts /opt/retail/qdrant /opt/retail/source

if ! command -v az >/dev/null 2>&1; then
  curl -sL https://aka.ms/InstallAzureCLIDeb | bash
fi

az login \
  --identity \
  --client-id "__IDENTITY_CLIENT_ID__" \
  --allow-no-subscriptions \
  --output none

downloaded=false
for attempt in $(seq 1 30); do
  if az storage blob download-batch \
    --account-name "__STORAGE_ACCOUNT__" \
    --source models \
    --destination /opt/retail/artifacts \
    --pattern "__MODEL_PREFIX__/*" \
    --auth-mode login \
    --overwrite true \
    --only-show-errors; then
    downloaded=true
    break
  fi
  sleep 10
done

if [[ "$downloaded" != "true" ]]; then
  echo "Model download failed after 30 attempts" >&2
  exit 1
fi

source_downloaded=false
for attempt in $(seq 1 30); do
  if az storage blob download \
    --account-name "__STORAGE_ACCOUNT__" \
    --container-name models \
    --name source/retail-api.zip \
    --file /opt/retail/source/retail-api.zip \
    --auth-mode login \
    --overwrite true \
    --only-show-errors; then
    source_downloaded=true
    break
  fi
  sleep 10
done

if [[ "$source_downloaded" != "true" ]]; then
  echo "API source download failed after 30 attempts" >&2
  exit 1
fi

unzip -q -o /opt/retail/source/retail-api.zip -d /opt/retail/source/app
az acr login --name "__ACR_NAME__" --only-show-errors
docker build \
  --tag "__API_IMAGE__" \
  --file /opt/retail/source/app/Dockerfile.api \
  /opt/retail/source/app
docker push "__API_IMAGE__"
docker pull qdrant/qdrant:v1.13.6

cat >/opt/retail/.env <<'EOF'
API_IMAGE=__API_IMAGE__
MODEL_ROOT=/opt/retail/artifacts
QDRANT_DATA_DIR=/opt/retail/qdrant
QDRANT_COLLECTION=retail_items
QDRANT_IMAGE=qdrant/qdrant:v1.13.6
EOF

cd /opt/retail
docker compose --env-file .env -f compose.yaml up -d
