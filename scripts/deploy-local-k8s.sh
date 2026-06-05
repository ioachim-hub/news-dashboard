#!/usr/bin/env bash
set -euo pipefail

TAG="${1:-local}"
IMAGE="localhost:5000/news-dashboard:${TAG}"

docker build -t "${IMAGE}" .
docker push "${IMAGE}"
helm upgrade --install news-dashboard ./helm/news-dashboard \
  --namespace news-dashboard --create-namespace \
  --set image.repository=localhost:5000/news-dashboard \
  --set image.tag="${TAG}" \
  --set persistence.hostPath=/home/ioachim-minipc/news-dashboard-data \
  --set postgresql.persistence.hostPath=/home/ioachim-minipc/news-dashboard-postgres-data \
  --set ingress.enabled=false

kubectl -n news-dashboard rollout status statefulset/news-dashboard-news-dashboard-postgres
kubectl -n news-dashboard rollout status deploy/news-dashboard-news-dashboard
