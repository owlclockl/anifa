import { defineConfig } from "vite";

// Owlbear embeds the popover in an iframe on owlbear.rodeo. Vite's dev server
// must answer preflight requests from that origin while the extension is local.
export default defineConfig({
  base: "./",
  server: {
    host: "0.0.0.0",
    allowedHosts: true,
    cors: {
      origin: [/^https:\/\/(.*\.)?owlbear\.rodeo$/, /^http:\/\/localhost:\d+$/],
    },
    headers: {
      "Cross-Origin-Resource-Policy": "cross-origin",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: new URL("./index.html", import.meta.url).pathname,
        extension: new URL("./extension.html", import.meta.url).pathname,
      },
    },
  },
});
