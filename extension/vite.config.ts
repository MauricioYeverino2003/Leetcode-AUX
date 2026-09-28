import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const root = fileURLToPath(new URL(".", import.meta.url));

/**
 * Pass 1 of 2 — the side panel and the service worker.
 *
 * Both are allowed to be ES modules (the panel is an ordinary page, and the
 * manifest declares the worker as `"type": "module"`), so they can share one
 * build. The content script cannot, and lives in vite.content.config.ts.
 *
 * This pass runs first and is the one that empties dist/.
 */
export default defineConfig({
  // Relative asset URLs, so nothing depends on how chrome-extension:// roots
  // absolute paths.
  base: "./",
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rolldownOptions: {
      input: {
        panel: `${root}panel.html`,
        worker: `${root}src/worker.ts`,
      },
      output: {
        // No content hashes on entries: manifest.json refers to these by name.
        entryFileNames: "[name].js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
});
