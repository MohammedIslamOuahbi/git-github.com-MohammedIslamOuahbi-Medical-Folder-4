import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

const srcPath = fileURLToPath(new URL("./src", import.meta.url));

export default defineConfig({
  plugins: [
    react({
      babel: {
        generatorOpts: {
          compact: true,
        },
      },
    }),
  ],
  resolve: {
    alias: {
      "@": srcPath,
    },
  },
  server: {
    port: 5173,
    host: "0.0.0.0",
    strictPort: true,
  },
});
