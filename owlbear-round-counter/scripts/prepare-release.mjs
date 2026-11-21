import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const TAG = process.env.OBR_RELEASE_TAG || "owlbear-round-counter-v1.0.0";
const RAW_BASE = `https://raw.githubusercontent.com/owlclockl/anifa/${TAG}/owlbear-round-counter/dist`;

const dist = resolve("dist");
let html = readFileSync(resolve(dist, "extension.html"), "utf8");

const scriptMatch = html.match(/<script[^>]+src="\.\/assets\/[^"]+\.js"><\/script>/);
const styleMatch = html.match(/<link[^>]+rel="stylesheet"[^>]+href="\.\/assets\/[^"]+\.css">/);

if (!scriptMatch || !styleMatch) {
  throw new Error("Bundled script or stylesheet not found in dist/extension.html");
}

const scriptPath = scriptMatch[0].match(/src="([^"]+)"/)[1];
const stylePath = styleMatch[0].match(/href="([^"]+)"/)[1];
let js = readFileSync(resolve(dist, scriptPath), "utf8");
const css = readFileSync(resolve(dist, stylePath), "utf8");

// A literal closing script tag inside the bundle would end the inline block.
js = js.replace(/<\/script/gi, "<\\/script");

html = html
  .replace(scriptMatch[0], "")
  .replace(styleMatch[0], "")
  .replace(/<link[^>]+rel="modulepreload"[^>]*>/g, "")
  .replace("</head>", `<style>\n${css}\n</style>\n<script type="module">\n${js}\n</script>\n</head>`);

writeFileSync(resolve(dist, "extension.html"), html);

const manifest = {
  name: "Round Counter",
  version: "1.0.0",
  manifest_version: 1,
  description: "Shared round counter for Owlbear Rodeo scenes",
  author: "owlclockl",
  homepage_url: "https://github.com/owlclockl/anifa/tree/main/owlbear-round-counter",
  action: {
    title: "Round Counter",
    icon: `${RAW_BASE}/icon.svg`,
    popover: `${RAW_BASE}/extension.html`,
    width: 320,
    height: 420,
  },
};

writeFileSync(
  resolve(dist, "manifest-install.json"),
  `${JSON.stringify(manifest, null, 2)}\n`,
);

console.log(`Prepared self-contained extension and manifest for ${TAG}`);
