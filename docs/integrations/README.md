# Plane Integrations (GitHub, Slack, Jira)

Community Edition module restored in `feature/stables`. Domain flows were ported from the pre-#3630 API and Segway patterns into Django + Celery.

## Ports (local)

| Service | URL                   |
| ------- | --------------------- |
| Web     | http://127.0.0.1:8700 |
| API     | http://127.0.0.1:8704 |

## Environment variables (`apps/api/.env`)

```bash
# Slack
SLACK_CLIENT_ID=
SLACK_CLIENT_SECRET=
SLACK_SIGNING_SECRET=
SLACK_OAUTH_URL=https://slack.com/api/oauth.v2.access

# GitHub App
GITHUB_APP_ID=
GITHUB_APP_NAME=
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=

# Optional: Silo-style external importer proxy (leave empty for local importer)
# PROXY_BASE_URL=
```

Also expose public ids via instance config (already supported):

- `SLACK_CLIENT_ID`
- `GITHUB_APP_NAME`

## Seed catalog

```bash
docker exec plane-api-1 python manage.py seed_integrations
# or
python manage.py seed_integrations
```

## Slack App setup

1. Create an app at https://api.slack.com/apps
2. OAuth Redirect URL: `http://127.0.0.1:8700/integrations/slack/callback`
3. Bot scopes: `chat:write`, `commands`, `incoming-webhook`, `users:read`, `users:read.email`, …
4. Slash command (e.g. `/plane`) Request URL: `http://127.0.0.1:8704/api/integrations/slack/events/`
5. Interactivity Request URL: same as above
6. Install to workspace from Plane → Settings → Integrations

## GitHub App setup

1. Create a GitHub App with permission to Issues (R/W), Metadata (R)
2. Setup URL: `http://127.0.0.1:8700/integrations/github/callback`
3. Webhook URL: `http://127.0.0.1:8704/api/integrations/github/webhook/`
4. Subscribe to `issues`, `issue_comment`
5. Set `GITHUB_APP_ID`, `GITHUB_APP_NAME`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`

## Jira Cloud

1. Create an Atlassian API token for your user
2. Workspace Settings → Integrations → Install Jira (email, token, `your-domain.atlassian.net`)
3. Workspace Settings → Imports → choose project + Jira project key

## UI entry points

- Workspace: `/{slug}/settings/integrations`
- Imports: `/{slug}/settings/imports`
- Project link (Slack channel / GitHub repo): `/{slug}/settings/projects/{projectId}/integrations`

## API surface (selected)

- `GET /api/integrations/`
- `GET|POST|DELETE /api/workspaces/{slug}/workspace-integrations/…`
- `…/project-slack-sync/`, `…/github-repository-sync/`
- `GET|POST /api/workspaces/{slug}/importers/…`
- `POST /api/integrations/slack/events/`
- `POST /api/integrations/github/webhook/`
