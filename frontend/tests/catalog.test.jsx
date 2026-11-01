import assert from "node:assert/strict";
import { test } from "node:test";
import { GameCard } from "../src/components/GameCard.jsx";
import { GameShelf, LibraryGameCard, ShelfItem } from "../src/components/GameShelf.jsx";
import { AuthContext } from "../src/context/AuthContext.jsx";
import { ToastProvider } from "../src/context/ToastContext.jsx";
import CatalogPage from "../src/pages/CatalogPage.jsx";
import { StatusDock } from "../src/pages/game/StatusDock.jsx";
import { count, html } from "./helpers.jsx";

const hades = {
  rawg_id: 5,
  name: "Hades",
  slug: "hades",
  released: "2020-09-17",
  genres: ["Action", "RPG"],
  cover_url: null,
  cover_thumb_url: null,
};

/** A página do catálogo por fora, sem ninguém logado. */
const catalogAt = (url) =>
  html(
    <AuthContext.Provider value={{ user: null, ready: true }}>
      <ToastProvider>
        <CatalogPage />
      </ToastProvider>
    </AuthContext.Provider>,
    url,
  );

// ----------------------------------------------------------------------------- o card
test("o card mostra o primeiro gênero ao lado do ano só quando pedem", () => {
  assert.match(html(<GameCard game={hades} showGenre />), /2020 · Action/);
  assert.doesNotMatch(html(<GameCard game={hades} />), /Action/);
  assert.match(html(<GameCard game={{ ...hades, genres: [] }} showGenre />), />2020</); // sem gênero, só o ano
});

test("o card mostra a média da comunidade sempre com o número de notas, e um texto próprio para leitor de tela", () => {
  const markup = html(<GameCard game={hades} community={{ average: 8.5, count: 4 }} />);
  assert.match(markup, /game-card-community/);
  assert.match(markup, /<strong aria-hidden="true">8,5<\/strong>/);
  assert.match(markup, /\(4\)/);
  assert.match(markup, /Média 8,5 em 4 notas no DiscPlayer/);
  assert.match(html(<GameCard game={hades} community={{ average: 10, count: 1 }} />), /Média 10 em 1 nota no DiscPlayer/);
  assert.doesNotMatch(html(<GameCard game={hades} community={{ average: null, count: 0 }} />), /game-card-community/);
  assert.doesNotMatch(html(<GameCard game={hades} community={null} />), /game-card-community/);
});

test("o botão de guardar na fila só aparece com o atalho ligado e o jogo fora do diário", () => {
  const add = () => {};
  const withButton = html(<GameCard game={hades} onQuickAdd={add} />);
  assert.match(withButton, /<button[^>]*class="game-card-add"/);
  assert.match(withButton, /aria-label="Guardar Hades em Quero jogar"/);
  assert.match(withButton, /<\/a><button/); // o botão fica ao lado do link, nunca dentro dele
  assert.doesNotMatch(html(<GameCard game={hades} />), /game-card-add/);
  assert.doesNotMatch(html(<GameCard game={hades} onQuickAdd={add} entry={{ status: "jogando", is_favorite: false }} />), /game-card-add/);
  const busy = html(<GameCard game={hades} onQuickAdd={add} quickAddPending />);
  assert.match(busy, /disabled=""/);
  assert.match(busy, /aria-busy="true"/);
});

// ----------------------------------------------------------------------------- card com o diário
const diary = (extra = {}) => ({ entries: {}, pending: {}, enabled: true, add: () => {}, ...extra });

test("o card com diário mostra o status de quem já tem o jogo e oferece o atalho a quem não tem", () => {
  const known = html(<LibraryGameCard game={hades} diary={diary({ entries: { 5: { status: "zerado", is_favorite: true } } })} />);
  assert.match(known, /game-card-flags/);
  assert.match(known, /Zerado/);
  assert.match(known, /Favorito/);
  assert.doesNotMatch(known, /game-card-add/);
  assert.match(html(<LibraryGameCard game={hades} diary={diary()} />), /game-card-add/);
});

test("sem login, ou antes de saber o que está no diário, o atalho não é oferecido", () => {
  assert.doesNotMatch(html(<LibraryGameCard game={hades} diary={diary({ enabled: false })} />), /game-card-add/);
});

test("o card com diário usa a média que vem no jogo, e a que vier de fora tem prioridade", () => {
  const withAverage = { ...hades, community: { average: 7, count: 2 } };
  assert.match(html(<LibraryGameCard game={withAverage} diary={diary()} />), /Média 7 em 2 notas/);
  assert.match(html(<LibraryGameCard game={withAverage} diary={diary()} community={{ average: 9, count: 3 }} />), /Média 9 em 3 notas/);
  assert.doesNotMatch(html(<LibraryGameCard game={withAverage} diary={diary()} community={null} />), /game-card-community/);
});

// ----------------------------------------------------------------------------- a prateleira
test("a prateleira tem título, ação e uma lista de jogos", () => {
  const markup = html(
    <GameShelf title="Em alta" action={<a href="/jogos?ordem=popular">Ver todos</a>}>
      <ShelfItem>
        <GameCard game={hades} />
      </ShelfItem>
      <ShelfItem>
        <GameCard game={{ ...hades, rawg_id: 6, name: "Celeste" }} />
      </ShelfItem>
    </GameShelf>,
  );
  assert.match(markup, /<section class="shelf" aria-labelledby=/);
  assert.match(markup, /<h2[^>]*>Em alta<\/h2>/);
  assert.equal(count(markup, /class="shelf-item"/g), 2);
  assert.match(markup, /Ver todos/);
  assert.equal(count(markup, /shelf-buttons/g), 0); // os botões só aparecem quando a fileira rola de verdade
});

// ----------------------------------------------------------------------------- a página do catálogo
test("o catálogo abre enxuto: título, busca, botão de filtros fechado e as prateleiras carregando", () => {
  const markup = catalogAt("/jogos");
  assert.match(markup, /<h1[^>]*>Jogos<\/h1>/);
  assert.match(markup, /type="search"[^>]*aria-label="Nome do jogo"|aria-label="Nome do jogo"[^>]*type="search"/);
  assert.match(markup, /aria-expanded="false"[^>]*aria-controls="catalog-filters"|aria-controls="catalog-filters"[^>]*aria-expanded="false"/);
  assert.match(markup, /id="catalog-filters"[^>]*hidden=""/);
  for (const label of ["Plataforma", "Ano de lançamento", "Ordenar por"]) assert.match(markup, new RegExp(`>${label}<`));
  assert.match(markup, /class="shelf" aria-hidden="true"/); // a prateleira "Em alta" carregando
  assert.doesNotMatch(markup, /filter-chips/); // sem filtro, sem chips
  assert.doesNotMatch(markup, /count-badge/);
  assert.doesNotMatch(markup, /Ver todos/); // as prateleiras só aparecem depois que os jogos chegam
});

test("com filtros na URL, o catálogo mostra chips para tirá-los, a contagem no botão e não abre prateleiras", () => {
  const markup = catalogAt("/jogos?genero=rpg&plataforma=1&ano=2020&ordem=released");
  assert.match(markup, /aria-label="Filtros ativos"/);
  assert.match(markup, /Plataforma: 1/); // enquanto a lista de plataformas não chega, aparece o número
  assert.match(markup, /Ano: 2020/);
  assert.match(markup, /Ordem: Lançamento mais recente/);
  assert.match(markup, /aria-label="Remover o filtro Ano: 2020"/);
  assert.match(markup, /Limpar tudo/);
  assert.match(markup, /class="count-badge">3</); // plataforma, ano e ordem (o gênero tem os chips dele)
  assert.doesNotMatch(markup, /class="shelf"/);
});

test("uma busca por nome não conta como filtro do botão, mas libera 'Limpar tudo'", () => {
  const markup = catalogAt("/jogos?q=zelda");
  assert.doesNotMatch(markup, /count-badge/);
  assert.match(markup, /Limpar tudo/);
  assert.match(markup, /value="zelda"/);
  assert.doesNotMatch(markup, /class="shelf"/);
});

test("da segunda página em diante o catálogo não abre as prateleiras", () => {
  assert.match(catalogAt("/jogos"), /class="shelf"/);
  assert.doesNotMatch(catalogAt("/jogos?pagina=2"), /class="shelf"/);
});

// ----------------------------------------------------------------------------- a barra de status do celular
test("a barra de status do celular só aparece quando o painel do diário sai da tela", () => {
  const markup = html(<StatusDock anchorRef={{ current: null }} ready signedIn entry={null} />);
  assert.equal(markup, ""); // ao abrir a página o painel está na tela (ou ainda não se sabe): nada de barra
});

// ----------------------------------------------------------------------------- o que a tela pede ao servidor
test("a API pede os status do diário, o atalho da fila só cria e as relacionadas vêm do jogo", async () => {
  const { gamesApi, libraryApi } = await import("../src/services/api.js");
  const realFetch = globalThis.fetch;
  const sent = [];
  globalThis.fetch = async (url, options = {}) => {
    const isMe = String(url).endsWith("/auth/me");
    if (!isMe) sent.push({ method: options.method ?? "GET", url: String(url), body: options.body });
    return new Response(JSON.stringify(isMe ? { csrf_token: "t" } : {}), { status: 200, headers: { "Content-Type": "application/json" } });
  };
  try {
    await libraryApi.statuses([5, 7, 9]);
    await libraryApi.queue(5);
    await gamesApi.related(5);
  } finally {
    globalThis.fetch = realFetch;
  }
  assert.deepEqual(sent[0], { method: "GET", url: "/api/library/status?ids=5%2C7%2C9", body: undefined });
  assert.equal(sent[1].method, "PUT");
  assert.equal(sent[1].url, "/api/library/5");
  const body = JSON.parse(sent[1].body);
  assert.equal(body.status, "quero_jogar");
  assert.equal(body.create_only, true); // o servidor recusa se o jogo já estiver no diário
  assert.match(body.today, /^\d{4}-\d{2}-\d{2}$/);
  assert.deepEqual(sent[2], { method: "GET", url: "/api/games/5/related", body: undefined });
});
