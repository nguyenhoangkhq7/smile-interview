#!/usr/bin/env bash
# Invoked as root through SSM in a private, per-transaction release directory.
set -euo pipefail
umask 077
cd "$(dirname "$0")/../.."
source /etc/smile/production.conf
export AWS_DEFAULT_REGION AWS_PAGER=""
export BACKEND_IMAGE AI_IMAGE CODE_RUNNER_IMAGE GNN_CHECKPOINT_DIR RDS_CA_BUNDLE
export APP_CORS_ALLOWED_ORIGINS RDS_ENDPOINT RDS_DB_NAME
BACKEND_IMAGE=$(jq -er .backend manifest.json)
AI_IMAGE=$(jq -er .ai manifest.json)
CODE_RUNNER_IMAGE=$(jq -er .code_runner manifest.json)
checksum=$(awk '{print $1}' deploy/gnn-v4.sha256)
filename=$(awk '{print $2}' deploy/gnn-v4.sha256)
[[ $checksum == "$(jq -er .checkpoint manifest.json)" ]]
[[ $API_HOST =~ ^[a-z0-9.-]+$ && $APP_CORS_ALLOWED_ORIGINS =~ ^https://[A-Za-z0-9.-]+$ ]]
GNN_CHECKPOINT_DIR="/var/lib/smile/models/$checksum"
RDS_CA_BUNDLE=/etc/smile/rds-global-bundle.pem
compose=(docker compose -p smile-production -f deploy/docker-compose.staging.yml -f deploy/production/compose.yml)

case "${1:?prepare or activate}" in
prepare)
    [[ -s $RDS_CA_BUNDLE && -s /etc/letsencrypt/live/$API_HOST/fullchain.pem ]]
    [[ -s /etc/letsencrypt/live/$API_HOST/privkey.pem ]]
    mkdir -p backend ai-service "$GNN_CHECKPOINT_DIR"
    for service in backend ai-service; do
        aws ssm get-parameter --with-decryption --name "/smile/production/$service" \
            --query Parameter.Value --output text > "$service/.env"
    done
    # Only accept the team's pinned model before touching live containers.
    if [[ ! -f $GNN_CHECKPOINT_DIR/$filename ]]; then
        aws s3 cp "s3://$RELEASE_BUCKET/models/$checksum/$filename" "$GNN_CHECKPOINT_DIR/download"
        (cd "$GNN_CHECKPOINT_DIR"; echo "$checksum  download" | sha256sum -c -)
        chmod 644 "$GNN_CHECKPOINT_DIR/download"
        mv "$GNN_CHECKPOINT_DIR/download" "$GNN_CHECKPOINT_DIR/$filename"
    fi
    (cd "$GNN_CHECKPOINT_DIR"; sha256sum -c "$OLDPWD/deploy/gnn-v4.sha256")
    chmod 755 "$GNN_CHECKPOINT_DIR"
    sed -i "s/api-staging\.example\.com/$API_HOST/g" deploy/nginx/staging.conf
    chmod 644 deploy/nginx/staging.conf
    registry=${BACKEND_IMAGE%%/*}
    aws ecr get-login-password | docker login --username AWS --password-stdin "$registry"
    "${compose[@]}" config --quiet
    "${compose[@]}" pull
    "${compose[@]}" run --rm --no-deps --entrypoint sh backend -ec 'test -n "$JWT_SECRET" && test -n "$SPRING_DATASOURCE_USERNAME" && test -n "$SPRING_DATASOURCE_PASSWORD"'
    "${compose[@]}" run --rm --no-deps --entrypoint sh ai-service -ec 'test -n "$OPENROUTER_API_KEY"'
    "${compose[@]}" run --rm --no-deps -T ai-service python -c \
        'from matching_cv.app.core.config import settings; from matching_cv.app.core.model_loader import model_loader; model_loader.load_model(settings.STAGE3_MODEL_NAME, revision=settings.STAGE3_MODEL_REVISION)'
    # Check TLS files/config even on the first release, before backend DNS exists.
    "${compose[@]}" run --rm --no-deps --entrypoint sh nginx -ec 'echo "127.0.0.1 backend" >> /etc/hosts; nginx -t'
    ;;
activate)
    "${compose[@]}" up -d --no-build --wait --wait-timeout 420
    "${compose[@]}" exec -T nginx nginx -s reload
    "${compose[@]}" exec -T ai-service python - < deploy/production/smoke-gnn.py
    curl -fsS --retry 5 --retry-all-errors "https://$API_HOST/actuator/health" | jq -e '.status == "UP"'
    ;;
*) exit 2 ;;
esac
