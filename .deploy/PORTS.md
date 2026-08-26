# Plane local-dev ports (from 8700)

| Service          | URL / host port                 |
| ---------------- | ------------------------------- |
| web              | http://localhost:8700           |
| admin (God mode) | http://localhost:8701/god-mode/ |
| space            | http://localhost:8702           |
| live             | http://localhost:8703           |
| api              | http://localhost:8704           |
| postgres         | localhost:8754                  |
| redis            | localhost:8739                  |
| minio API        | localhost:8790                  |
| minio console    | localhost:8791                  |

Uploads: Vite proxies `/uploads` → MinIO `:8790`. Set `AWS_S3_BROWSER_ENDPOINT_URL` to the web origin (`http://localhost:8700` or Dev Tunnel `-8700`). With Dev Tunnels also set `AWS_S3_SIGNING_ENDPOINT_URL=http://localhost:8700` (tunnel rewrites `Host`; signing against `-8790` yields `SignatureDoesNotMatch`).

Start backend: `./.deploy/dev.sh up`
Start frontends: `./.deploy/dev.sh frontend`

Integrations setup: docs/integrations/README.md
seed: docker exec plane-api-1 python manage.py seed_integrations
