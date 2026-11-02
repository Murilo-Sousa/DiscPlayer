// "Quem você segue jogou": o que o bloco da página do jogo mostra com os dados que o servidor devolve.
import assert from "node:assert/strict";
import { test } from "node:test";
import { FollowingPlayersView } from "../src/pages/game/FollowingPlayers.jsx";
import { count, html } from "./helpers.jsx";

const person = (username, extra = {}) => ({
  user: { username, display_name: username.toUpperCase(), avatar_url: null, is_demo: false },
  status: "zerado",
  is_favorite: false,
  rating: null,
  has_text: false,
  ...extra,
});

const data = (overrides = {}) => ({
  items: [person("bia", { rating: 9.5, is_favorite: true }), person("caio", { status: "jogando" })],
  total: 2,
  rated: 1,
  average: 9.5,
  want_to_play: 0,
  ...overrides,
});

const view = (value) => html(<FollowingPlayersView data={value} />);

test("seguidos: lista cada pessoa com link para o perfil, status e nota", () => {
  const markup = view(data());
  assert.match(markup, /Quem você segue jogou/);
  assert.equal(count(markup, /class="following-item"/g), 2);
  assert.match(markup, /href="\/u\/bia"/);
  assert.match(markup, /href="\/u\/caio"/);
  assert.match(markup, /Zerado/);
  assert.match(markup, /Jogando/);
  assert.match(markup, /<strong>9,5<\/strong>/);
  assert.match(markup, /Nota 9,5 de 10/); // a nota em discos tem leitura por voz
});

test("seguidos: favorito é dito por voz e quem não deu nota fica sem linha de nota", () => {
  const markup = view(data());
  assert.equal(count(markup, /, favorito/g), 1);
  assert.equal(count(markup, /class="following-rating"/g), 1);
});

test("seguidos: a média só aparece com pelo menos duas notas", () => {
  assert.doesNotMatch(view(data()), /Média entre quem você segue/);
  const markup = view(data({ rated: 3, average: 8.33 }));
  assert.match(markup, /Média entre quem você segue: <strong>8,33<\/strong> \(3 notas\)/);
});

test("seguidos: avisa de quem não coube na lista e de quem só quer jogar", () => {
  assert.doesNotMatch(view(data()), /following-more/);
  assert.match(view(data({ total: 15 })), /e mais 13 pessoas/);
  assert.match(view(data({ total: 3 })), /e mais 1 pessoa(?!s)/);
  assert.match(view(data({ want_to_play: 1 })), /1 pessoa quer jogar/);
  assert.match(view(data({ total: 14, want_to_play: 4 })), /e mais 12 pessoas · 4 pessoas querem jogar/);
});

test("seguidos: sem ninguém que jogou o bloco some", () => {
  assert.equal(view(data({ items: [], total: 0, rated: 0, average: null })), "");
  assert.equal(view(data({ items: [], total: 0, want_to_play: 3 })), ""); // só quem quer jogar não monta o bloco
});

test("seguidos: nota antiga sem o jogo no diário mostra só a nota, e perfil de exemplo leva a marca", () => {
  const legacy = person("duda", { status: null, rating: 7 });
  const demo = person("eva", { user: { username: "eva", display_name: "Eva", avatar_url: null, is_demo: true } });
  const markup = view(data({ items: [legacy, demo], total: 2, rated: 1, average: 7 }));
  assert.equal(count(markup, /class="following-status"/g), 1); // só a Eva tem status
  assert.match(markup, /<strong>7<\/strong>/);
  assert.match(markup, /demo-badge/);
});
