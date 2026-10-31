import assert from "node:assert/strict";
import { test } from "node:test";
import { DemoBadge } from "../src/components/DemoBadge.jsx";
import { Disc } from "../src/components/Disc.jsx";
import { RankingList } from "../src/components/Ranking.jsx";
import { ReviewCard } from "../src/components/ReviewCard.jsx";
import { ABILITIES, DiscInstrument } from "../src/pages/landing/DiscInstrument.jsx";
import { Landing, wallColumns, wallGames } from "../src/pages/landing/Landing.jsx";
import { STATUS_PROGRESS } from "../src/utils/format.js";
import { count, html } from "./helpers.jsx";

const allowedIn = (status) => ABILITIES.filter(({ allowed }) => allowed(status)).map(({ key }) => key);

// ----------------------------------------------------------------------------- o que o disco grande promete
test("o disco grande diz, para cada status, o que o diário libera (as mesmas regras do diário)", () => {
  assert.deepEqual(allowedIn("quero_jogar"), []);
  assert.deepEqual(allowedIn("jogando"), ["start", "favorite", "rating"]);
  assert.deepEqual(allowedIn("pausado"), ["start", "favorite", "rating"]);
  assert.deepEqual(allowedIn("abandonado"), ["start", "favorite", "rating", "replay"]);
  assert.deepEqual(allowedIn("zerado"), ["start", "end", "favorite", "rating", "replay"]);
  // só "zerado" tem data de término, e só quem já começou pode dar nota
  for (const status of STATUS_PROGRESS) {
    assert.equal(allowedIn(status).includes("end"), status === "zerado", status);
    assert.equal(allowedIn(status).includes("rating"), status !== "quero_jogar", status);
  }
});

test("o disco grande abre na fila (vazio) e mostra os cinco status do seletor de verdade", () => {
  const markup = html(<DiscInstrument />);
  assert.match(markup, /Como esse jogo está para você\?/);
  assert.equal(count(markup, /class="status-option"/g), 5);
  assert.match(markup, /aria-pressed="true"[^>]*data-status="quero_jogar"|data-status="quero_jogar"[^>]*aria-pressed="true"/);
  assert.match(markup, /Na fila, ainda sem começar\./);
  assert.equal(count(markup, /instrument-ability"/g) + count(markup, /instrument-ability data-allowed/g), 5);
  assert.equal(count(markup, /data-allowed/g), 0); // na fila, nada é liberado
  assert.match(markup, /nada aqui é salvo/);
});

test("o disco grande desenha os quatro quartos e deixa a transição acender cada um", () => {
  const markup = html(<Disc size={200} quarters={2} animate />);
  assert.equal(count(markup, /class="disc-quarter"/g), 4);
  assert.equal(count(markup, /data-on=""/g), 2);
  const plain = html(<Disc size={20} quarters={2} />);
  assert.equal(count(plain, /<path/g), 2); // o disco comum continua desenhando só os quartos preenchidos
});

test("a espessura do traço acompanha strokeScale (o anel do disco grande não engrossa)", () => {
  assert.match(html(<Disc size={20} />), /stroke-width="1\.3"/);
  assert.match(html(<Disc size={300} strokeScale={0.5} />), /stroke-width="0\.65"/);
});

// ----------------------------------------------------------------------------- perfis de exemplo
test("a marca de exemplo só aparece em conta marcada como exemplo", () => {
  assert.match(html(<DemoBadge user={{ is_demo: true }} />), /Exemplo/);
  assert.equal(html(<DemoBadge user={{ is_demo: false }} />), "");
  assert.equal(html(<DemoBadge user={{}} />), "");
  assert.equal(html(<DemoBadge user={null} />), "");
});

test("a review de um perfil de exemplo leva a marca ao lado do nome", () => {
  const review = {
    id: 1,
    rating: 9,
    body: "Gostei muito.",
    has_spoilers: false,
    created_at: "2026-10-01T10:00:00Z",
    like_count: 0,
    liked: false,
    user: { username: "marina_rpg", display_name: "Marina Lopes", avatar_url: null, is_demo: true },
    game: { rawg_id: 1, name: "Hades", slug: "hades", cover_url: null, cover_thumb_url: null, released: "2020-09-17" },
  };
  assert.match(html(<ReviewCard review={review} showGame />), /Marina Lopes[\s\S]*demo-badge/);
  const real = { ...review, user: { ...review.user, is_demo: false } };
  assert.doesNotMatch(html(<ReviewCard review={real} showGame />), /demo-badge/);
});

// ----------------------------------------------------------------------------- ranking compartilhado
test("a lista do ranking numera, mostra o número de notas e a média", () => {
  const items = [
    { game: { rawg_id: 1, name: "Outer Wilds", slug: "outer-wilds", cover_url: null, cover_thumb_url: null }, count: 3, average: 9.5 },
    { game: { rawg_id: 2, name: "Celeste", slug: "celeste", cover_url: null, cover_thumb_url: null }, count: 4, average: 9 },
  ];
  const markup = html(<RankingList items={items} />);
  assert.equal(count(markup, /ranking-item/g), 2);
  assert.match(markup, /Outer Wilds/);
  assert.match(markup, /3 notas/);
  assert.match(markup, /4 notas/);
  assert.match(markup, /9,5/);
});

// ----------------------------------------------------------------------------- mural de capas
const game = (id, extra = {}) => ({
  rawg_id: id,
  name: `Jogo ${id}`,
  cover_thumb_url: `https://media.rawg.io/${id}-t.jpg`,
  cover_url: `https://media.rawg.io/${id}.jpg`,
  ...extra,
});
const ids = (games) => games.map((item) => item.rawg_id);

test("o mural mostra os jogos em alta primeiro, depois os lançamentos, sem repetir e só com capa", () => {
  const featured = {
    popular: [1, 2, 3, 4, 5, 6].map((id) => game(id)),
    new: [game(6), game(7), game(8, { cover_thumb_url: null, cover_url: null }), game(9, { cover_thumb_url: null })],
  };
  assert.deepEqual(ids(wallGames(featured)), [1, 2, 3, 4, 5, 6, 7, 9]); // 6 não repete, 8 não tem capa, 9 tem só a original
});

test("o mural tem no máximo 15 capas e some quando há poucas", () => {
  assert.equal(wallGames({ popular: Array.from({ length: 12 }, (_, i) => game(i + 1)), new: Array.from({ length: 12 }, (_, i) => game(i + 50)) }).length, 15);
  assert.deepEqual(wallGames({ popular: [1, 2, 3, 4, 5].map((id) => game(id)), new: [] }), []);
  assert.deepEqual(wallGames({ popular: null, new: null }), []); // a RAWG pode falhar numa das listas ou nas duas
  assert.deepEqual(wallGames(null), []);
  assert.equal(wallGames({ popular: null, new: [1, 2, 3, 4, 5, 6].map((id) => game(id)) }).length, 6); // basta uma lista boa
});

test("o mural reparte as capas pelas colunas, uma de cada vez", () => {
  const columns = wallColumns([1, 2, 3, 4, 5, 6, 7].map((id) => game(id)));
  assert.deepEqual(columns.map(ids), [[1, 4, 7], [2, 5], [3, 6]]);
});

test("a landing ainda carregando abre com o título e o esqueleto do mural, e o disco vem depois da jornada", () => {
  const markup = html(<Landing />);
  assert.match(markup, /<h1[^>]*>O diário de quem joga\.<\/h1>/);
  assert.match(markup, /data-wall="on"/);
  assert.equal(count(markup, /class="cover-wall-col"/g), 3);
  assert.equal(count(markup, /cover-wall-link/g), 0); // enquanto a RAWG não responde, só o esqueleto (sem links)
  const titles = [
    "O diário de quem joga.",
    "Do “quero jogar” ao “zerei”",
    "Veja como o diário funciona",
    "Dez pontos, cinco discos",
    "Listas para dividir o que você ama",
    "Seu ano em jogos",
    "Um diário que não faz de conta",
    "Qual foi o último jogo que você terminou?",
  ];
  const positions = titles.map((title) => markup.indexOf(title));
  assert.ok(positions.every((position) => position >= 0), `faltou algum título: ${positions}`);
  assert.deepEqual(positions, [...positions].sort((a, b) => a - b));
  assert.equal(count(markup, /class="instrument"/g), 1); // o disco aparece uma vez só, na própria seção
});
