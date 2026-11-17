// Serve the installed PDF.js worker and data locally, with matching versions.
const fs = require("node:fs");
const path = require("node:path");

const packageFile = require.resolve("pdfjs-dist/package.json");
const source = path.dirname(packageFile);
const { version } = JSON.parse(fs.readFileSync(packageFile, "utf8"));
const destination = path.resolve(__dirname, "../public/pdfjs", version);
fs.mkdirSync(destination, { recursive: true });
fs.copyFileSync(
  path.join(source, "build/pdf.worker.min.mjs"),
  path.join(destination, "pdf.worker.min.mjs")
);
for (const directory of ["cmaps", "standard_fonts", "wasm", "iccs"]) {
  fs.cpSync(path.join(source, directory), path.join(destination, directory), {
    recursive: true,
  });
}
console.log(`Prepared local PDF.js ${version} assets`);
