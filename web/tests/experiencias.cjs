const { test } = require("node:test");
const assert = require("node:assert/strict");
const ts = require("typescript");
const fs = require("node:fs");
// Compile only local TypeScript helpers for Node's built-in test runner.
require.extensions[".ts"] = (module, file) =>
  module._compile(
    ts.transpileModule(fs.readFileSync(file, "utf8"), {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
      },
    }).outputText,
    file,
  );
const { favorito } = require("../lib/partida.ts");
const { sortearCasos } = require("../lib/trivia.ts");
const { escenasResumen } = require("../lib/resumenPartida.ts");
const point = (ply, p) => ({
  ply,
  gana_blancas: p,
  empate: 0.1,
  gana_negras: 0.9 - p,
});
const analysis = (curve, length = 150) => ({
  jugadas: Array(length).fill("e4"),
  curva: curve,
  partida: { resultado: "Empate" },
  final: "repetition",
});

test("model chooses by probability, using established class order for ties", () => {
  assert.equal(
    favorito({ gana_blancas: 0.45, empate: 0.1, gana_negras: 0.45 }),
    "Gana Blancas",
  );
  assert.equal(
    favorito({ gana_blancas: 0.1, empate: 0.8, gana_negras: 0.1 }),
    "Empate",
  );
  assert.equal(
    favorito({ gana_blancas: 0.2, empate: 0.1, gana_negras: 0.7 }),
    "Gana Negras",
  );
});
test("deck does not repeat before exhaustion, or within a round crossing exhaustion", () => {
  const ids = ["a", "b", "c", "d", "e", "f", "g"];
  const first = sortearCasos(ids, 3),
    second = sortearCasos(ids, 3);
  assert.equal(new Set([...first, ...second]).size, 6);
  const third = sortearCasos(ids, 3);
  assert.equal(new Set(third).size, 3);
  assert.ok(third.some((id) => ![...first, ...second].includes(id)));
  assert.throws(() => sortearCasos(["x"], 3));
});
test("summary chooses separated changes, sorts chronologically and excludes extrapolation", () => {
  const scenes = escenasResumen(
    analysis([
      point(0, 0.4),
      point(10, 0.6),
      point(11, 0.2),
      point(20, 0.7),
      point(40, 0.1),
      point(130, 0.9),
    ]),
  );
  assert.equal(scenes[0].ply, 0);
  assert.equal(scenes.at(-1).ply, 150);
  const moments = scenes.slice(1, -1);
  assert.ok(moments.length <= 3);
  assert.ok(moments.every((s) => s.ply <= 120 && s.ply - s.desde <= 4));
  for (let i = 1; i < moments.length; i++)
    assert.ok(moments[i].ply - moments[i - 1].ply >= 6);
  assert.equal(scenes.at(-1).final, true);
});
test("short games and games without strong changes only show start and actual ending", () => {
  const scenes = escenasResumen(analysis([point(0, 0.4), point(1, 0.42)], 2));
  assert.deepEqual(
    scenes.map((s) => s.ply),
    [0, 2],
  );
  assert.match(scenes[1].texto, /Empate/);
});
