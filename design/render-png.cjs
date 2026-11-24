// Рендер SVG-артбордов в PNG (2x) через @resvg/resvg-js.
// Зависимость: npm install @resvg/resvg-js  (или NODE_PATH=<путь к node_modules>)
const fs = require("fs");
const path = require("path");
const { Resvg } = require("@resvg/resvg-js");

const here = __dirname;
const svgDir = path.join(here, "svg");
const pngDir = path.join(here, "png");
fs.mkdirSync(pngDir, { recursive: true });

const fontFiles = [
  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
].filter((f) => fs.existsSync(f));

for (const file of fs.readdirSync(svgDir).filter((f) => f.endsWith(".svg"))) {
  const svg = fs.readFileSync(path.join(svgDir, file), "utf8");
  const isIcon = file === "app-icon.svg";
  const resvg = new Resvg(svg, {
    fitTo: { mode: "width", value: isIcon ? 512 : 780 },
    font: { fontFiles, loadSystemFonts: true, defaultFontFamily: "DejaVu Sans" },
  });
  const png = resvg.render().asPng();
  const out = path.join(pngDir, file.replace(/\.svg$/, ".png"));
  fs.writeFileSync(out, png);
  console.log("png/", path.basename(out), " (", png.length, "bytes )");
}
