API (Docker). Ayer el contenedor no resolvía el host plane-db (failed to resolve host 'plane-db': Try again). Es el DNS interno de Docker en WSL2: los contenedores siguen “Up”, pero Django no encuentra Postgres y todas las peticiones salen 500. Tras el reinicio, la API en :8704 responde otra vez.

Frontend. Vite no pudo ocupar el 8700 y se fue al 8701 (el puerto del admin). El Dev Tunnel apunta a …-8700.use2.devtunnels.ms, así que veías el servicio caído aunque el proceso siguiera vivo. Lo relancé en 8700 y dejé strictPort: true para que, si el puerto está ocupado, falle en claro en vez de saltar de puerto.

Ahora: web http://localhost:8700/ → 200, proxy /api → 200, API :8704 → 200, admin :8701 → 302.

Si vuelve a pasar: docker compose -f docker-compose-local.yml restart cuando el API dé 500, y no dejes otro proceso en 8700.
