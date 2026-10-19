import assert from "node:assert/strict";
import { test } from "node:test";
import { matchPath } from "../src/router/index.jsx";

test("matchPath casa rotas estáticas e com parâmetro", () => {
  assert.deepEqual(matchPath("/", "/"), {});
  assert.deepEqual(matchPath("/jogos", "/jogos"), {});
  assert.deepEqual(matchPath("/jogos/:id", "/jogos/12-hades"), { id: "12-hades" });
  assert.deepEqual(matchPath("/u/:username", "/u/ana"), { username: "ana" });
  assert.deepEqual(matchPath("*", "/qualquer/coisa"), {});
});

test("matchPath recusa caminhos de tamanho ou texto diferente", () => {
  assert.equal(matchPath("/jogos", "/jogos/1"), null);
  assert.equal(matchPath("/jogos/:id", "/jogos"), null);
  assert.equal(matchPath("/listas", "/jogos"), null);
});

test("matchPath ignora barras repetidas e final", () => {
  assert.deepEqual(matchPath("/jogos/:id", "/jogos/5/"), { id: "5" });
  assert.deepEqual(matchPath("/jogos", "//jogos"), {});
});

test("matchPath decodifica parâmetros e rejeita %XX inválido", () => {
  assert.deepEqual(matchPath("/u/:username", "/u/ana%20maria"), { username: "ana maria" });
  assert.equal(matchPath("/u/:username", "/u/%E0%A4%A"), null);
});
