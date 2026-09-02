# Plane — arranque local (WSL / Linux)

Guía práctica para levantar este monorepo en desarrollo con los puertos de este entorno (`8700`–`8704`).

Para **reinstalar o reconfigurar WSL** (Docker Desktop, nvm, scripts de autostart, Apoteca + Plane): [WSL_SETUP.md](./WSL_SETUP.md).

## Requisitos

- Docker Engine en marcha
- Node.js **≥ 22.18** instalado **dentro de WSL** (no el Node de Windows)
- pnpm vía Corepack
- ~12 GB RAM recomendados

### Instalar Node en WSL (una vez)

```bash
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.bashrc   # o: export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"
nvm install 22
corepack enable
node -v && pnpm -v
```

Si `pnpm` sigue apuntando a `/mnt/c/Program Files/nodejs/...`, abre una terminal nueva o carga nvm como arriba.

## 1. Setup inicial (solo la primera vez)

```bash
cd /home/devdavid/proyectos/plane
chmod +x setup.sh
./setup.sh
```

Copia los `.env`, genera `SECRET_KEY` e instala dependencias.

En este repo los frontends usan:

| Servicio         | URL                             |
| ---------------- | ------------------------------- |
| Web (app)        | http://localhost:8700           |
| Admin (God mode) | http://localhost:8701/god-mode/ |
| Spaces           | http://localhost:8702/spaces/   |
| Live             | http://localhost:8703           |
| API              | http://localhost:8704           |

Usa siempre **`localhost`**, no mezcles con `127.0.0.1` (rompe CSRF/cookies en el setup).

## 2. Arrancar backend (Docker)

Terminal 1:

```bash
cd /home/devdavid/proyectos/plane
docker compose -f docker-compose-local.yml up
```

Espera a que `migrator` termine con **exit 0**. Si `api` se queda en `Waiting for database migrations to complete...`:

```bash
docker compose -f docker-compose-local.yml up -d --force-recreate migrator
# cuando migrator salga OK:
docker compose -f docker-compose-local.yml restart api worker beat-worker
```

Comprobar API:

```bash
curl -s http://127.0.0.1:8704/
# {"status": "OK"}
```

## 3. Arrancar frontends (pnpm)

Terminal 2:

```bash
cd /home/devdavid/proyectos/plane
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
pnpm dev
```

Si el navegador **recarga solo** al entrar en una sección: suele ser Vite re-optimizando deps (`optimized dependencies changed. reloading`), no un crash de la API. Mitigación ya en `apps/web/vite.config.ts` (`optimizeDeps.include`). Tras cambiarla, reinicia `pnpm dev`.

Con poca RAM (~16 GB) y muchos contenedores, preferible solo la app web:

```bash
pnpm --filter=web dev
# opcional: packages que uses
# pnpm --filter=@plane/propel --filter=@plane/ui --filter=@plane/editor dev
```

## 4. Primera configuración (God mode)

1. Abre **http://localhost:8701/god-mode/**
2. Completa **Setup your Plane Instance**
3. Contraseña **fuerte** (letras, números y símbolos; si es débil, la API te redirige al formulario)
4. Tras el éxito irás a God mode → General
5. App de usuario: **http://localhost:8700** (mismas credenciales)

## 5. Checklist CE “completo” (integraciones + AI parcial)

Community Edition no incluye Wiki Pro ni Plane AI de producto. Sí puedes dejar Slack/GitHub/Jira + LLM básico operativos.

### Credenciales en `apps/api/.env`

Variables (también en root `.env` por consistencia):

```bash
SLACK_CLIENT_ID=...
SLACK_CLIENT_SECRET=...
SLACK_SIGNING_SECRET=...
SLACK_OAUTH_URL=https://slack.com/api/oauth.v2.access

GITHUB_APP_ID=...
GITHUB_APP_NAME=...          # slug de la GitHub App (no vacío)
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=...

LLM_API_KEY=...              # opcional CE; vacío = sin AI (evita 500 si la key es fake)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
```

Hoy hay **placeholders de prueba** (`test-slack-client-id`, `plane-local-test`, etc.). Sirven para que `/api/instances/` ya no mande strings vacíos; **Install OAuth solo funcionará** cuando los sustituyas por apps reales (ver [docs/integrations/README.md](./docs/integrations/README.md)).

Deja `LLM_API_KEY` vacío (o una key OpenAI real). Una key `test-*` marca `has_llm_configured=true` y el asistente falla con 500.
Tras editar `apps/api/.env`:

```bash
docker compose -f docker-compose-local.yml up -d --force-recreate api worker beat-worker
# Si SKIP_ENV_VAR=1 (default), actualiza también InstanceConfiguration en DB
# o re-ejecuta los valores con manage.py shell (ver docs/integrations).
docker exec plane-api-1 python manage.py seed_integrations
```

Comprobar:

```bash
curl -s http://127.0.0.1:8704/api/instances/ | python3 -c \
  "import json,sys; c=json.load(sys.stdin)['config']; print(c.get('slack_client_id'), c.get('github_app_name'), c.get('has_llm_configured'))"
```

UI: `http://localhost:8700/{workspace}/settings/integrations`

### ClickUp / Wiki (fases posteriores)

- **Wiki Pro:** no en CE; usar Pages o evaluar Commercial más adelante.
- **ClickUp:** bridge externo vía API token + webhooks + `external_id` (no hay módulo nativo).

## Arranque día a día

Con el setup ya hecho, Docker (`unless-stopped`) y los frontends se mantienen solos (como Apoteca PHP `:8888`). Al abrir una terminal WSL se relanzan si hace falta.

```bash
/home/devdavid/bin/plane-dev-start   # idempotente; huérfano de la TTY
# log: ${XDG_RUNTIME_DIR:-/tmp}/plane-dev.log
```

Manual (si no usas el script):

```bash
# Terminal 1
cd /home/devdavid/proyectos/plane
docker compose -f docker-compose-local.yml up -d

# Terminal 2
cd /home/devdavid/proyectos/plane
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
pnpm dev
```

## Problemas frecuentes

| Síntoma                                  | Qué hacer                                                                                                                                                                                                                                                                                    |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `exec: node: not found`                  | Node de Windows en el PATH; usa nvm en WSL                                                                                                                                                                                                                                                   |
| Setup “recarga” al Continuar             | Usa `localhost` (no `127.0.0.1`); contraseña más fuerte; mira `?error_message=` en la URL                                                                                                                                                                                                    |
| Página recarga al abrir una sección      | Vite `optimized dependencies changed. reloading` — reinicia `pnpm dev` tras el fix de `optimizeDeps`; o usa solo `pnpm --filter=web dev`                                                                                                                                                     |
| API no responde / migrator `Exited (1)`  | Recrear `migrator` y reiniciar `api` (paso 2)                                                                                                                                                                                                                                                |
| CORS / cookies raras                     | `apps/api/.env` → `CORS_ALLOWED_ORIGINS` debe incluir `localhost` y `127.0.0.1` en puertos 8700–8703; reinicia `api`                                                                                                                                                                         |
| RAM alta / lentitud WSL                  | `pnpm dev` lanza muchos watchers (~varios GB). Cierra stacks que no uses (Apoteca, dis-services) o filtra a `web`                                                                                                                                                                            |
| No suben / no cargan imágenes            | Vite proxifica `/uploads` → MinIO `:8790`. Local: `AWS_S3_BROWSER_ENDPOINT_URL=http://localhost:8700`. Con Dev Tunnel: browser URL = `-8700` **y** `AWS_S3_SIGNING_ENDPOINT_URL=http://localhost:8700` (el túnel reescribe `Host`; firmar contra `-8790` rompe SigV4). Reinicia `api` y web. |
| Tunnel (Dev Tunnels) muestra maintenance | Actualiza `apps/web/.env` (`VITE_API_BASE_URL` = URL pública :8704) y `apps/api/.env` (CORS + `COOKIE_SECURE=1` + `SESSION_COOKIE_SAMESITE=None` + MinIO público). Reinicia `pnpm` y `api`                                                                                                   |
| Tunnel CSRF Verification Failed          | Usa `VITE_API_BASE_URL=""` + proxy Vite `/api` y `/auth` en `apps/web/vite.config.ts` (cookies first-party). Reinicia `pnpm --filter=web dev`                                                                                                                                                |

## Parar

```bash
/home/devdavid/bin/plane-dev-stop
docker compose -f docker-compose-local.yml down
```

Más detalle upstream: [CONTRIBUTING.md](./CONTRIBUTING.md). Integraciones GitHub/Slack: [docs/integrations/README.md](./docs/integrations/README.md).
