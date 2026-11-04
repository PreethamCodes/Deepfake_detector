import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "TRUTHSCAN_");
  const target = env.TRUTHSCAN_BACKEND_URL || "http://127.0.0.1:8000";
  const proxy = {
    "/api": { target, timeout: 0, proxyTimeout: 0 },
    "/health": { target },
  };
  return {
    plugins: [react(), tailwind()],
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    server: { host: "127.0.0.1", proxy },
    preview: { host: "127.0.0.1", proxy },
  };
});
