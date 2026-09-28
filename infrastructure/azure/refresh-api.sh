#!/usr/bin/env bash
set -euo pipefail

image_tag="${IMAGE_TAG:-v2}"
bootstrap=/usr/local/bin/retail-bootstrap.sh
storage_account=$(sed -n 's/.*--account-name "\([^"]*\)".*/\1/p' "$bootstrap" | head -n 1)
acr_name=$(sed -n 's/.*az acr login --name "\([^"]*\)".*/\1/p' "$bootstrap" | head -n 1)
identity_client_id=$(sed -n 's/.*--client-id "\([^"]*\)".*/\1/p' "$bootstrap" | head -n 1)

if [[ -z "$storage_account" || -z "$acr_name" || -z "$identity_client_id" ]]; then
  echo "Could not read deployment settings from $bootstrap" >&2
  exit 1
fi

login_server="${acr_name}.azurecr.io"
api_image="${login_server}/retail-api:${image_tag}"
if ! docker image inspect "$api_image" >/dev/null 2>&1; then
  az login --identity --client-id "$identity_client_id" --allow-no-subscriptions --output none
  az storage blob download \
    --account-name "$storage_account" \
    --container-name models \
    --name source/retail-api.zip \
    --file /opt/retail/source/retail-api.zip \
    --auth-mode login \
    --overwrite true \
    --only-show-errors

  unzip -oq /opt/retail/source/retail-api.zip -d /opt/retail/source/app
  docker build -f /opt/retail/source/app/Dockerfile.api -t "$api_image" /opt/retail/source/app
  az acr login --name "$acr_name" --output none
  docker push "$api_image"
fi

if grep -q '^API_IMAGE=' /opt/retail/.env; then
  sed -i "s|^API_IMAGE=.*|API_IMAGE=${api_image}|" /opt/retail/.env
else
  printf '\nAPI_IMAGE=%s\n' "$api_image" >> /opt/retail/.env
fi

cd /opt/retail
docker compose --env-file .env -f compose.yaml up -d --no-deps --force-recreate api

for _ in $(seq 1 30); do
  if docker exec retail-recommendation-azure-api-1 python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"; then
    docker exec retail-recommendation-azure-api-1 python -c \
      "import importlib.metadata; print('qdrant-client=' + importlib.metadata.version('qdrant-client'))"
    exit 0
  fi
  sleep 5
done

docker logs --tail 100 retail-recommendation-azure-api-1 >&2
exit 1
