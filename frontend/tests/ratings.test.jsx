// A distribuição de notas vai de 0 a 10 (11 barras) no perfil, na retrospectiva e na página do jogo.
import assert from "node:assert/strict";
import { test } from "node:test";
import { CommunityCard } from "../src/pages/game/CommunityBlock.jsx";
import { RATING_LABELS, RATING_SR } from "../src/utils/format.js";
import { count, html } from "./helpers.jsx";

test("rótulos: de 0 a 10, com o 10 sozinho e a leitura por voz de cada barra", () => {
  assert.deepEqual(RATING_LABELS, ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]);
  assert.equal(RATING_SR.length, RATING_LABELS.length);
  assert.equal(RATING_SR[0], "Notas de 0 a 0,5");
  assert.equal(RATING_SR[9], "Notas de 9 a 9,5");
  assert.equal(RATING_SR[10], "Nota 10");
});

const library = { total: 0, quero_jogar: 0, jogando: 0, zerado: 0, abandonado: 0, pausado: 0 };

test("comunidade do jogo: 11 barras, e o 10 não some dentro do 9", () => {
  const distribution = [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2];
  const markup = html(<CommunityCard community={{ average: 9.8, count: 3, with_text: 0, distribution, library }} />);
  assert.equal(count(markup, /class="histogram-label"/g), 11);
  assert.match(markup, /<th scope="row">Nota 10<\/th><td>2<\/td>/);
  assert.match(markup, /<th scope="row">Notas de 9 a 9,5<\/th><td>1<\/td>/);
  assert.match(markup, /a última é só a nota 10/);
});

test("comunidade do jogo: sem notas não desenha o gráfico", () => {
  const empty = { average: null, count: 0, with_text: 0, distribution: Array(11).fill(0), library };
  const markup = html(<CommunityCard community={empty} />);
  assert.match(markup, /Ainda sem notas/);
  assert.equal(count(markup, /histogram-label/g), 0);
});
