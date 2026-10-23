// Executa os testes do front-end sem Vitest: o esbuild (já dependência do Vite) empacota cada
// arquivo *.test.js(x) e o executor nativo do Node (node:test) roda o resultado.
//
//   npm test
//
// Os testes de componentes usam renderização no servidor (react-dom/server), então não
// precisam de navegador. O comportamento no navegador é coberto pelo teste de ponta a ponta
// (veja a seção "Ponta a ponta no navegador" de docs/testes.md).
import { spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync, rmSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { delimiter, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { build } = require("esbuild");

const here = dirname(fileURLToPath(import.meta.url));
const files = readdirSync(here)
  .filter((name) => /\.test\.jsx?$/.test(name))
  .map((name) => join(here, name));

if (files.length === 0) {
  console.error("Nenhum arquivo *.test.js(x) encontrado em tests/.");
  process.exit(1);
}

const outdir = mkdtempSync(join(tmpdir(), "discplayer-tests-"));
try {
  await build({
    entryPoints: files,
    outdir,
    bundle: true,
    platform: "node",
    format: "cjs",
    outExtension: { ".js": ".cjs" },
    jsx: "automatic",
    define: { "import.meta.env": "{}" },
    loader: { ".css": "empty", ".woff": "empty" },
    // Respeita NODE_PATH, caso as dependências estejam instaladas fora de frontend/node_modules.
    nodePaths: (process.env.NODE_PATH ?? "").split(delimiter).filter(Boolean),
    logLevel: "warning",
  });
  const built = readdirSync(outdir).map((name) => join(outdir, name));
  const result = spawnSync(process.execPath, ["--test", "--test-reporter=spec", ...built], { stdio: "inherit" });
  process.exitCode = result.status ?? 1;
} finally {
  rmSync(outdir, { recursive: true, force: true });
}
