import path from "node:path";
import * as dotenv from "dotenv";
import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

dotenv.config({ path: path.resolve(__dirname, ".env") });

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
  plugins: [reactRouter(), tsconfigPaths({ projects: [path.resolve(__dirname, "tsconfig.json")] })],
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
    // Same-origin proxy so CSRF/session cookies work over Dev Tunnels
    // (web host …-8700 ≠ API host …-8704 would otherwise be third-party cookies).
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8704",
        changeOrigin: true,
        cookieDomainRewrite: "",
      },
      "/auth": {
        target: "http://127.0.0.1:8704",
        changeOrigin: true,
        cookieDomainRewrite: "",
      },
      // MinIO path-style. Dev Tunnels rewrite Host → localhost:8700; API signs
      // against AWS_S3_SIGNING_ENDPOINT_URL and rewrites the public URL.
      "/uploads": {
        target: "http://127.0.0.1:8790",
        changeOrigin: false,
      },
    },
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
