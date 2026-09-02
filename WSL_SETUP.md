# Reconfigurar WSL (esta máquina)

Guía para volver a dejar Ubuntu + Docker + Apoteca-dev + Plane como ahora, si reinstalas WSL o cambias de distro.

Rutas de este entorno:

| Qué                  | Dónde                                         |
| -------------------- | --------------------------------------------- |
| Distro               | Ubuntu 24.04 (`DISCCSP13DAVQUI`)              |
| Usuario Linux        | `devdavid` (`/home/devdavid`)                 |
| Terminals Cursor     | suelen ser **root**; nvm está en `/root/.nvm` |
| Proyectos            | `/home/devdavid/proyectos/`                   |
| Scripts autostart    | `/home/devdavid/bin/`                         |
| `.wslconfig` Windows | `C:\Users\david.quiroz\.wslconfig`            |

Detalle de Plane (puertos, God mode, integraciones): [LOCAL_SETUP.md](./LOCAL_SETUP.md).

---

## 0. Windows (una vez)

1. Instala **WSL2** y **Ubuntu 24.04**.
2. Instala **Docker Desktop** y activa integración WSL2 con esta distro.
3. Crea o edita `C:\Users\david.quiroz\.wslconfig`:

```ini
[wsl2]
systemd=true
networkingMode=mirrored
dnsTunneling=true
autoProxy=true

[network]
generateResolvConf = false
```

4. En la distro, `/etc/wsl.conf`:

```ini
[network]
generateResolvConf = true
```

5. Aplica cambios (PowerShell):

```powershell
wsl --shutdown
```

Vuelve a abrir Ubuntu. Comprueba: `docker ps` funciona **dentro de WSL**.

---

## 1. Paquetes en Ubuntu

```bash
sudo apt update
sudo apt install -y git curl php-cli php-xml php-mbstring unzip
php -v   # 8.3.x en esta máquina
```

Usuario de trabajo:

```bash
# si no existe
sudo useradd -m -s /bin/bash devdavid
```

Crea el árbol:

```bash
sudo mkdir -p /home/devdavid/proyectos /home/devdavid/bin
sudo chown -R devdavid:devdavid /home/devdavid/proyectos /home/devdavid/bin
```

Docker desde WSL (root o usuario en grupo `docker`):

```bash
# en ~/.bashrc de quien use docker:
docker context use desktop-linux
export DOCKER_HOST=unix:///var/run/docker.sock
```

---

## 2. Node 22 **dentro de WSL** (no el de Windows)

En esta máquina nvm está en **root** (`/root/.nvm`), porque Cursor abre shells como root.

```bash
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm install 22
corepack enable
node -v   # >= 22.18
pnpm -v
```

Si `which node` apunta a `/mnt/c/Program Files/nodejs/...`, abre una terminal nueva o recarga nvm. El Node de Windows **no** sirve para Plane.

Añade al final de `/root/.bashrc` (y de `/home/devdavid/.bashrc` si trabajas como `devdavid`):

```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
```

---

## 3. Clonar / colocar repos

```bash
cd /home/devdavid/proyectos
# Apoteca-dev, ApotecaBack, plane — como ya los tengas
```

| Repo          | Arranque                                                                         |
| ------------- | -------------------------------------------------------------------------------- |
| `ApotecaBack` | `docker compose up -d` (`restart: unless-stopped`) → API `http://localhost:8800` |
| `Apoteca-dev` | PHP built-in `:8888` (script abajo)                                              |
| `plane`       | `./setup.sh` una vez; Docker `docker-compose-local.yml`; frontends `pnpm dev`    |

Plane (primera vez):

```bash
cd /home/devdavid/proyectos/plane
chmod +x setup.sh
./setup.sh
docker compose -f docker-compose-local.yml up -d
# migrator debe salir 0; si api se queda en "Waiting for database migrations":
docker compose -f docker-compose-local.yml up -d --force-recreate migrator
docker compose -f docker-compose-local.yml restart api worker beat-worker
```

---

## 4. Autostart (como está ahora)

Docker **no** hace falta relanzarlo a mano: `unless-stopped` / `always` lo recupera al subir Docker Desktop.

Los procesos **fuera** de Docker (PHP `:8888` y `pnpm dev`) se relanzan al abrir una **terminal interactiva**, con `setsid` para que sobrevivan al cerrar esa terminal.

### 4.1 Scripts

Copia los cuatro ficheros a `/home/devdavid/bin/` y:

```bash
chmod +x /home/devdavid/bin/{apoteca,plane}-dev-{start,stop}
chown devdavid:devdavid /home/devdavid/bin/{apoteca,plane}-dev-{start,stop}
```

Los contenidos actuales están en:

- `/home/devdavid/bin/apoteca-dev-start`
- `/home/devdavid/bin/apoteca-dev-stop`
- `/home/devdavid/bin/plane-dev-start`
- `/home/devdavid/bin/plane-dev-stop`

Si los perdiste, recrea `plane-dev-start` así:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/devdavid/proyectos/plane"
PIDFILE="${XDG_RUNTIME_DIR:-/tmp}/plane-dev.pid"
LOG="${XDG_RUNTIME_DIR:-/tmp}/plane-dev.log"
PORT=8700
COMPOSE="$ROOT/docker-compose-local.yml"

load_nvm() {
  local dir
  for dir in "${NVM_DIR:-}" "$HOME/.nvm" /root/.nvm /home/devdavid/.nvm; do
    [[ -n "$dir" && -s "$dir/nvm.sh" ]] || continue
    export NVM_DIR="$dir"
    . "$dir/nvm.sh"
    return 0
  done
  return 1
}

port_up() { ss -tln 2>/dev/null | grep -qE ":${PORT}\\s"; }

plane_node_pids() {
  local pid cwd
  for pid in $(pgrep -f node 2>/dev/null || true); do
    cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || true)
    if [[ "$cwd" == "$ROOT" || "$cwd" == "$ROOT/"* ]]; then echo "$pid"; fi
  done
}

find_pnpm_pid() {
  local p cmd
  for p in $(plane_node_pids); do
    cmd=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null || true)
    if [[ "$cmd" == *"pnpm"* && "$cmd" == *" dev"* && "$cmd" != *"pnpm run dev"* ]]; then
      echo "$p"; return 0
    fi
  done
  return 1
}

ensure_docker() {
  command -v docker >/dev/null 2>&1 || return 0
  ss -tln 2>/dev/null | grep -qE ':8704\s' && return 0
  docker compose -f "$COMPOSE" up -d >/dev/null 2>&1 || true
}

if port_up || [[ -n "$(find_pnpm_pid || true)" ]]; then
  PID=$(find_pnpm_pid || cat "$PIDFILE" 2>/dev/null || echo "?")
  echo "$PID" > "$PIDFILE" 2>/dev/null || true
  echo "Plane ya corre (pid $PID) → http://localhost:$PORT/"
  ensure_docker
  exit 0
fi

load_nvm || { echo "ERROR: nvm/node" >&2; exit 1; }
command -v pnpm >/dev/null || { echo "ERROR: pnpm" >&2; exit 1; }
ensure_docker
cd "$ROOT"
: > "$LOG"
setsid pnpm dev >>"$LOG" 2>&1 < /dev/null &
disown || true
sleep 1
PID=$(find_pnpm_pid || true)
[[ -n "${PID:-}" ]] || { echo "ERROR: no arrancó. Log:" >&2; tail -n 40 "$LOG" >&2; exit 1; }
echo "$PID" > "$PIDFILE"
echo "Plane iniciado (pid $PID) → http://localhost:$PORT/  (log: $LOG)"
```

`plane-dev-stop`:

```bash
#!/usr/bin/env bash
ROOT="/home/devdavid/proyectos/plane"
PIDFILE="${XDG_RUNTIME_DIR:-/tmp}/plane-dev.pid"
kill_tree() {
  local pid cwd
  for pid in $(pgrep -f node 2>/dev/null || true); do
    cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || true)
    if [[ "$cwd" == "$ROOT" || "$cwd" == "$ROOT/"* ]]; then kill "$pid" 2>/dev/null || true; fi
  done
}
[[ -f "$PIDFILE" ]] && { kill "$(cat "$PIDFILE")" 2>/dev/null || true; rm -f "$PIDFILE"; }
kill_tree; sleep 0.4; kill_tree
echo "Plane frontends detenidos (Docker se deja; para pararlo: docker compose -f $ROOT/docker-compose-local.yml down)"
```

`apoteca-dev-start` (PHP `:8888`):

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$HOME/proyectos/Apoteca-dev"
PIDFILE="${XDG_RUNTIME_DIR:-/tmp}/apoteca-dev-8888.pid"
LOG="${XDG_RUNTIME_DIR:-/tmp}/apoteca-dev-8888.log"
PORT=8888

is_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && [[ -r "/proc/$pid/cmdline" ]] \
    && tr '\0' ' ' < "/proc/$pid/cmdline" | grep -q "php -S 0.0.0.0:${PORT}"
}

find_php_pid() {
  local p cmd
  for p in $(pgrep -x php 2>/dev/null || true); do
    cmd=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null || true)
    if [[ "$cmd" == *"php -S 0.0.0.0:${PORT}"* ]]; then echo "$p"; return 0; fi
  done
  return 1
}

if is_alive "$(cat "$PIDFILE" 2>/dev/null || true)"; then
  echo "Apoteca-dev ya corre (pid $(cat "$PIDFILE")) → http://localhost:$PORT/"
  exit 0
fi
EXISTING=$(find_php_pid || true)
if [[ -n "${EXISTING:-}" ]]; then
  echo "$EXISTING" > "$PIDFILE"
  echo "Apoteca-dev ya escucha en :$PORT (pid $EXISTING)"
  exit 0
fi
cd "$ROOT"
: > "$LOG"
setsid /usr/bin/php -S 0.0.0.0:${PORT} -t . >>"$LOG" 2>&1 < /dev/null &
disown || true
sleep 0.6
PID=$(find_php_pid || true)
[[ -n "${PID:-}" ]] || { echo "ERROR: no arrancó. Log:" >&2; cat "$LOG" >&2; exit 1; }
echo "$PID" > "$PIDFILE"
echo "Apoteca-dev iniciado (pid $PID) → http://localhost:$PORT/"
```

`apoteca-dev-stop`:

```bash
#!/usr/bin/env bash
PIDFILE="${XDG_RUNTIME_DIR:-/tmp}/apoteca-dev-8888.pid"
PORT=8888
[[ -f "$PIDFILE" ]] && { kill "$(cat "$PIDFILE")" 2>/dev/null || true; rm -f "$PIDFILE"; }
for p in $(pgrep -x php 2>/dev/null || true); do
  cmd=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null || true)
  if [[ "$cmd" == *"php -S 0.0.0.0:${PORT}"* ]]; then kill "$p" 2>/dev/null || true; fi
done
echo "Apoteca-dev detenido"
```

Si Cursor corre como **root**, `apoteca-dev-start` usa `$HOME/proyectos/Apoteca-dev` → `/root/proyectos/...`. En ese caso o bien enlazas el repo:

```bash
sudo mkdir -p /root/proyectos
sudo ln -sfn /home/devdavid/proyectos/Apoteca-dev /root/proyectos/Apoteca-dev
```

o cambias `ROOT=` en el script a `/home/devdavid/proyectos/Apoteca-dev` (Plane ya usa ruta absoluta).

### 4.2 Ganchos `.bashrc`

**`/home/devdavid/.bashrc`** (al final, después de Docker):

```bash
if [[ $- == *i* ]] && [[ -x "$HOME/bin/apoteca-dev-start" ]]; then
  "$HOME/bin/apoteca-dev-start" >/dev/null 2>&1 || true
fi
if [[ $- == *i* ]] && [[ -x "$HOME/bin/plane-dev-start" ]]; then
  "$HOME/bin/plane-dev-start" >/dev/null 2>&1 || true
fi
```

**`/root/.bashrc`** (después de cargar nvm; Cursor usa este):

```bash
if [[ $- == *i* ]] && [[ -x /home/devdavid/bin/plane-dev-start ]]; then
  /home/devdavid/bin/plane-dev-start >/dev/null 2>&1 || true
fi
# opcional, misma idea para Apoteca:
# if [[ $- == *i* ]] && [[ -x /home/devdavid/bin/apoteca-dev-start ]]; then
#   /home/devdavid/bin/apoteca-dev-start >/dev/null 2>&1 || true
# fi
```

Hay un unit systemd de usuario `~/.config/systemd/user/apoteca-dev.service`. En esta distro **no hay bus systemd de usuario** (`PID 1` = `/init`); el mecanismo que sí funciona es **bashrc + setsid**.

---

## 5. Comprobar

```bash
curl -s http://127.0.0.1:8704/          # Plane API → {"status": "OK"}
curl -sI http://127.0.0.1:8700/         # web
curl -sI http://127.0.0.1:8701/god-mode/
curl -sI http://127.0.0.1:8888/         # Apoteca PHP
curl -sI http://127.0.0.1:8800/         # Apoteca API
docker compose -f /home/devdavid/proyectos/plane/docker-compose-local.yml ps
docker compose -f /home/devdavid/proyectos/ApotecaBack/docker-compose.yml ps
```

| Servicio       | URL                             |
| -------------- | ------------------------------- |
| Plane app      | http://localhost:8700           |
| Plane God mode | http://localhost:8701/god-mode/ |
| Plane Spaces   | http://localhost:8702/spaces/   |
| Plane Live     | http://localhost:8703           |
| Plane API      | http://localhost:8704           |
| Apoteca PHP    | http://localhost:8888           |
| Apoteca API    | http://localhost:8800           |

Usa **`localhost`** (no mezclar con `127.0.0.1` en el setup de Plane: CSRF/cookies).

---

## 6. Día a día

```bash
# Arrancar (idempotente; también se dispara al abrir una shell)
/home/devdavid/bin/plane-dev-start
/home/devdavid/bin/apoteca-dev-start

# Parar solo frontends (Docker sigue)
/home/devdavid/bin/plane-dev-stop
/home/devdavid/bin/apoteca-dev-stop

# Parar backends Docker
docker compose -f /home/devdavid/proyectos/plane/docker-compose-local.yml down
docker compose -f /home/devdavid/proyectos/ApotecaBack/docker-compose.yml down
```

Logs Plane: `${XDG_RUNTIME_DIR:-/tmp}/plane-dev.log` (aquí suele ser `/mnt/wslg/runtime-dir/plane-dev.log`).

---

## Problemas frecuentes

| Síntoma                                   | Qué hacer                                                                                       |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `exec: node: not found` / pnpm de Windows | Recarga nvm; no uses Node de `/mnt/c`                                                           |
| `docker: permission denied` / no socket   | Docker Desktop + `DOCKER_HOST=unix:///var/run/docker.sock` + `docker context use desktop-linux` |
| Frontends mueren al cerrar la terminal    | Tienen que ser `setsid` (TTY `?`). Relanza con `plane-dev-start`, no `pnpm dev` en primer plano |
| Tras `wsl --shutdown` no hay web          | Abre una terminal WSL (dispara bashrc) o ejecuta `plane-dev-start`. Docker tarda unos segundos  |
| RAM alta                                  | `pnpm dev` usa varios GB. Cierra stacks que no uses o filtra a `pnpm --filter=web dev`          |
| Apoteca `:8888` no sube como root         | `ROOT` del script apunta a `$HOME`; usa ruta absoluta o el symlink de la sección 4.1            |
