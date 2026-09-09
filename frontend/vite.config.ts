import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, process.cwd(), "");
  const target =
    process.env.B2C_API_TARGET || fileEnv.B2C_API_TARGET || "http://127.0.0.1:8010";
  const port = Number(
    process.env.B2C_FRONTEND_PORT || fileEnv.B2C_FRONTEND_PORT || 5176,
  );
  return {
    plugins: [react()],
    server: {
      port,
      strictPort: true,
      proxy: { "/api": target, "/_allauth": target },
    },
  };
});
