import http from "node:http";
import path from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";
import * as dotenv from "dotenv";
import { reactRouter } from "@react-router/dev/vite";
import type { Plugin } from "vite";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

dotenv.config({ path: path.resolve(__dirname, ".env") });

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
]);

function filterRequestHeaders(src: IncomingMessage["headers"]): http.OutgoingHttpHeaders {
  const headers: http.OutgoingHttpHeaders = {};
  for (const [key, value] of Object.entries(src)) {
    if (HOP_BY_HOP.has(key.toLowerCase())) continue;
    headers[key] = value;
  }
  return headers;
}

function rewriteSetCookie(value: string | string[] | undefined): string[] | undefined {
  if (!value) return undefined;
  const list = Array.isArray(value) ? value : [value];
  return list.map((cookie) => cookie.replace(/;\s*Domain=[^;]*/gi, ""));
}

function proxyRequest(opts: {
  hostname: string;
  port: number;
  changeOrigin: boolean;
  req: IncomingMessage;
  res: ServerResponse;
}) {
  const { hostname, port, changeOrigin, req, res } = opts;
  const headers = filterRequestHeaders(req.headers);
  if (changeOrigin) headers.host = `${hostname}:${port}`;

  const proxyReq = http.request({ hostname, port, path: req.url, method: req.method, headers }, (proxyRes) => {
    const outHeaders = { ...proxyRes.headers };
    const cookies = rewriteSetCookie(proxyRes.headers["set-cookie"]);
    if (cookies) outHeaders["set-cookie"] = cookies;
    delete outHeaders["transfer-encoding"];
    res.writeHead(proxyRes.statusCode ?? 502, outHeaders);
    proxyRes.pipe(res);
  });

  proxyReq.on("error", (err) => {
    console.error(`[plane-dev-proxy] ${hostname}:${port} ${req.url} → ${err.message}`);
    if (!res.headersSent) {
      res.writeHead(502, { "content-type": "application/json" });
      res.end(JSON.stringify({ success: false, message: "API proxy failed" }));
      return;
    }
    res.end();
  });

  req.pipe(proxyReq);
}

/**
 * React Router's Vite plugin handles GET requests as the SPA before Vite's
 * built-in `server.proxy` runs. That made `/api/instances/` return HTML, so
 * the login page thought no auth methods were enabled.
 */
function planeBackendProxy(): Plugin {
  return {
    name: "plane-backend-proxy",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url ?? "";
        if (url.startsWith("/api") || url.startsWith("/auth")) {
          proxyRequest({ hostname: "127.0.0.1", port: 8704, changeOrigin: true, req, res });
          return;
        }
        if (url.startsWith("/uploads")) {
          proxyRequest({ hostname: "127.0.0.1", port: 8790, changeOrigin: false, req, res });
          return;
        }
        next();
      });
    },
  };
}

// Expose only vars starting with VITE_
const viteEnv = Object.keys(process.env)
  .filter((k) => k.startsWith("VITE_"))
  .reduce<Record<string, string>>((a, k) => {
    a[k] = process.env[k] ?? "";
    return a;
  }, {});

export default defineConfig(() => ({
  define: {
    "process.env": JSON.stringify(viteEnv),
  },
  build: {
    assetsInlineLimit: 0,
  },
  plugins: [
    planeBackendProxy(),
    reactRouter(),
    tsconfigPaths({ projects: [path.resolve(__dirname, "tsconfig.json")] }),
  ],
  resolve: {
    alias: {
      // Next.js compatibility shims used within web
      "next/link": path.resolve(__dirname, "app/compat/next/link.tsx"),
      "next/navigation": path.resolve(__dirname, "app/compat/next/navigation.ts"),
      "next/script": path.resolve(__dirname, "app/compat/next/script.tsx"),
    },
    dedupe: ["react", "react-dom", "@headlessui/react"],
  },
  server: {
    // Keep in sync with APP_BASE_URL / CORS (localhost, not only 127.0.0.1)
    host: "localhost",
    // Dev Tunnels forward with the public hostname
    allowedHosts: [".use2.devtunnels.ms", ".devtunnels.ms", "localhost", "127.0.0.1"],
    // Same-origin /api /auth /uploads proxy lives in planeBackendProxy()
    // (React Router intercepts GET before Vite's built-in server.proxy).
  },
  // Pre-bundle deps that are often first imported on navigation; otherwise Vite
  // re-optimizes mid-session and forces a full browser reload ("page refresh").
  optimizeDeps: {
    include: [
      "swr",
      "swr/infinite",
      "mobx",
      "mobx-react",
      "mobx-utils",
      "axios",
      "lodash-es",
      "date-fns",
      "uuid",
      "clsx",
      "tailwind-merge",
      "class-variance-authority",
      "@atlaskit/pragmatic-drag-and-drop/element/adapter",
      "@atlaskit/pragmatic-drag-and-drop/combine",
      "@atlaskit/pragmatic-drag-and-drop-hitbox/closest-edge",
      "@headlessui/react",
      "@radix-ui/react-scroll-area",
      "lucide-react",
      "i18next",
      "react-i18next",
      "next-themes",
    ],
  },
}));
