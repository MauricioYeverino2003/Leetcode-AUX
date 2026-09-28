import { fileURLToPath } from "node:url";

import { defineConfig } from "vite";

const root = fileURLToPath(new URL(".", import.meta.url));

/**
 * Pass 2 (and 3) of the build — the content scripts.
 *
 * Chrome injects content scripts as classic scripts, so `import` / `export`
 * at the top level is a syntax error there. IIFE output bundles each one into
 * a single self-contained file instead.
 *
 * IIFE output cannot code-split, which rules out building both scripts in one
 * pass. So this config is a function of `--mode`, and package.json runs it
 * once per script:
 *
 *   vite build -c vite.content.config.ts --mode content
 *   vite build -c vite.content.config.ts --mode main-world
 *
 * Both run after vite.config.ts, so they must leave dist/ alone: no emptying,
 * and no second copy of public/.
 */
const ENTRIES: Record<string, string> = {
  content: "src/content.ts",
  "main-world": "src/main-world.ts",
};

export default defineConfig(({ mode }) => {
  const entry = ENTRIES[mode];
  if (!entry) {
    throw new Error(
      `Unknown content-script mode "${mode}". Pass --mode with one of: ${Object.keys(ENTRIES).join(", ")}`,
    );
  }

  return {
    publicDir: false,
    build: {
      outDir: "dist",
      emptyOutDir: false,
      rolldownOptions: {
        input: { [mode]: `${root}${entry}` },
        output: {
          format: "iife",
          entryFileNames: "[name].js",
        },
      },
    },
  };
});
