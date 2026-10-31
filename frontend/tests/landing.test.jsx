import assert from "node:assert/strict";
import { test } from "node:test";
import { DemoBadge } from "../src/components/DemoBadge.jsx";
import { Disc } from "../src/components/Disc.jsx";
import { RankingList } from "../src/components/Ranking.jsx";
import { ReviewCard } from "../src/components/ReviewCard.jsx";
import { ABILITIES, DiscInstrument } from "../src/pages/landing/DiscInstrument.jsx";
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
