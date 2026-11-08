// O início de quem está logado: o que cada cartão de "jogando agora" e de "novidades" mostra, e os estados vazios.
import assert from "node:assert/strict";
import { test } from "node:test";
import { HighlightCard, Highlights } from "../src/pages/home/Highlights.jsx";
import { PlayerCard, PlayingRail, ScopeSwitch } from "../src/pages/home/PlayingRail.jsx";
import { count, html } from "./helpers.jsx";

const user = (username, extra = {}) => ({ username, display_name: username.toUpperCase(), avatar_url: null, is_demo: false, ...extra });
const game = (igdbId, name) => ({ igdb_id: igdbId, name, slug: name.toLowerCase().replace(/\W+/g, "-"), cover_url: null, cover_thumb_url: null });
const NOW = "2026-11-02T12:00:00Z";

// ----------------------------------------------------------------------------- seletor
test("seletor: dois botões, e só o escolhido está pressionado", () => {
  const markup = html(<ScopeSwitch scope="community" onChange={() => {}} />);
  assert.match(markup, /role="group"[^>]*aria-label="Mostrar a atividade de"/);
  assert.match(markup, /aria-pressed="false"[^>]*>Quem eu sigo</);
  assert.match(markup, /aria-pressed="true"[^>]*>Comunidade</);
});

// ----------------------------------------------------------------------------- jogando agora
const item = (extra = {}) => ({ user: user("bia"), game: game(1, "Hades"), started_at: "2026-10-10", since: NOW, also: 0, ...extra });

test("cartão: quem é, o jogo (com link) e há quanto tempo joga", () => {
  const markup = html(<PlayerCard item={item()} />);
  assert.match(markup, /href="\/u\/bia"/);
  assert.match(markup, /class="player-card-game"[^>]*>Hades</);
  assert.match(markup, /href="\/jogos\/1-hades"/);
  assert.match(markup, /dias? jogando/);
  assert.doesNotMatch(markup, /\+\d+ jogo/);
});

test("cartão: sem data de início diz quando o jogo foi marcado, e mostra os outros jogos", () => {
  const markup = html(<PlayerCard item={item({ started_at: null, since: "2020-01-01T00:00:00Z", also: 2 })} />);
  assert.match(markup, /Marcou /);
  assert.doesNotMatch(markup, /jogando<\/span>/);
  assert.match(markup, /\+2 jogos/);
  assert.match(html(<PlayerCard item={item({ also: 1 })} />), /\+1 jogo(?!s)/);
});

test("cartão: perfil de exemplo leva a marca", () => {
  assert.match(html(<PlayerCard item={item({ user: user("eva", { is_demo: true }) })} />), /demo-badge/);
  assert.doesNotMatch(html(<PlayerCard item={item()} />), /demo-badge/);
});

const rail = (data, scope = "following") => html(<PlayingRail data={data} scope={scope} error={null} onRetry={() => {}} onScope={() => {}} />);

test("fileira: um cartão por pessoa e o seletor no cabeçalho", () => {
  const markup = rail({ scope: "following", items: [item(), item({ user: user("caio"), game: game(2, "Celeste") })], total: 2, following: 2 });
  assert.equal(count(markup, /class="player-card"/g), 2);
  assert.match(markup, /Jogando agora/);
  assert.match(markup, /Quem eu sigo/);
});

test("fileira: enquanto carrega mostra o lugar dos cartões, também quando os dados são de outro escopo", () => {
  for (const data of [null, { scope: "community", items: [item()], total: 1, following: 1 }]) {
    const markup = rail(data);
    assert.equal(count(markup, /class="player-card"/g), 0);
    assert.match(markup, /skeleton/);
    assert.match(markup, /Quem eu sigo/); // o seletor não some
  }
});

test("fileira: avisos de vazio por escopo, e convite para quem não segue ninguém", () => {
  const empty = (scope, following) => rail({ scope, items: [], total: 0, following }, scope);
  assert.match(empty("following", 3), /Ninguém que você segue está jogando agora/);
  assert.match(empty("community", 3), /Ninguém está jogando agora/);
  const nobody = empty("following", 0);
  assert.match(nobody, /Você ainda não segue ninguém/);
  assert.match(nobody, /href="\/buscar"/);
  assert.match(nobody, /Ver a comunidade/);
  assert.equal(count(nobody, /class="player-card"/g), 0);
});

test("fileira: erro sem dados vira aviso com 'Tentar de novo'", () => {
  const markup = html(<PlayingRail data={null} scope="community" error={new Error("Falhou.")} onRetry={() => {}} onScope={() => {}} />);
  assert.match(markup, /Não foi possível carregar quem está jogando/);
  assert.match(markup, /Tentar de novo/);
});

// ----------------------------------------------------------------------------- novidades
const card = (extra) => ({ user: user("bia"), created_at: "2026-11-02T10:00:00Z", ...extra });

test("novidade: zerou com nota e trecho da review", () => {
  const markup = html(<HighlightCard card={card({ kind: "finished", game: game(1, "Hades"), rating: 9.5, excerpt: "Uma obra-prima.", has_spoilers: false })} />);
  assert.match(markup, /data-kind="finished"/);
  assert.match(markup, /zerou/);
  assert.match(markup, /class="news-rating">9,5</);
  assert.match(markup, /Uma obra-prima\./);
});

test("novidade: zerou sem nota não desenha nota nem trecho; avaliou usa o outro verbo", () => {
  const finished = html(<HighlightCard card={card({ kind: "finished", game: game(1, "Hades"), rating: null, excerpt: null, has_spoilers: false })} />);
  assert.doesNotMatch(finished, /news-rating|news-excerpt/);
  const reviewed = html(<HighlightCard card={card({ kind: "reviewed", game: game(1, "Hades"), rating: 8, excerpt: null, has_spoilers: false })} />);
  assert.match(reviewed, /avaliou/);
});

test("novidade: review com spoilers mostra o aviso e nunca o trecho", () => {
  const markup = html(<HighlightCard card={card({ kind: "reviewed", game: game(1, "Hades"), rating: 8, excerpt: "O vilão é o pai.", has_spoilers: true })} />);
  assert.match(markup, /Contém spoilers/);
  assert.doesNotMatch(markup, /O vilão é o pai/);
});

test("novidade: abandonou e pausou são uma linha, sem capa", () => {
  const abandoned = html(<HighlightCard card={card({ kind: "status", status: "abandonado", game: game(1, "Hades") })} />);
  assert.match(abandoned, /abandonou/);
  assert.doesNotMatch(abandoned, /news-cover/);
  assert.match(html(<HighlightCard card={card({ kind: "status", status: "pausado", game: game(1, "Hades") })} />), /pausou/);
});

test("novidade: fila em lote mostra a contagem, as capas e quantos faltam", () => {
  const games = [game(1, "Hades"), game(2, "Celeste"), game(3, "Portal 2")];
  const markup = html(<HighlightCard card={card({ kind: "queued", games, count: 6 })} />);
  assert.match(markup, /guardou/);
  assert.match(markup, /6 jogos/);
  assert.equal(count(markup, /class="news-mini"/g), 3);
  assert.match(markup, /class="news-more">\+3</);
  const single = html(<HighlightCard card={card({ kind: "queued", games: [game(1, "Hades")], count: 1 })} />);
  assert.match(single, /guardou <a [^>]*>Hades</);
  assert.doesNotMatch(single, /news-more/);
});

test("novidade: lista com o título, o número de jogos e as capas", () => {
  const list = { id: 7, title: "Roguelikes", game_count: 3, covers: [{ name: "Hades", cover_url: null }] };
  const markup = html(<HighlightCard card={card({ kind: "list", list })} />);
  assert.match(markup, /criou a lista/);
  assert.match(markup, /href="\/listas\/7"/);
  assert.match(markup, />3 jogos</);
  assert.match(markup, /cover-stack/);
});

test("novidade: um tipo que o servidor passe a mandar e a tela não conhece não quebra a lista", () => {
  assert.equal(html(<HighlightCard card={card({ kind: "novo-tipo" })} />), "");
});

const news = (data, scope = "following") => html(<Highlights data={data} scope={scope} error={null} onRetry={() => {}} />);

test("novidades: lista, carregando, vazio por escopo e erro", () => {
  const items = [card({ kind: "status", status: "pausado", game: game(1, "Hades") }), card({ kind: "status", status: "abandonado", game: game(2, "Celeste") })];
  assert.equal(count(news({ scope: "following", items, following: 2 }), /class="news-item"/g), 2);
  assert.match(news(null), /skeleton/);
  assert.match(news({ scope: "community", items, following: 2 }), /skeleton/); // dados de outro escopo não aparecem
  assert.match(news({ scope: "following", items: [], following: 2 }), /Quando alguém que você segue zerar/);
  assert.match(news({ scope: "following", items: [], following: 0 }), /Siga outras pessoas/);
  assert.match(news({ scope: "community", items: [], following: 0 }, "community"), /Quando alguém zerar/);
  const failed = html(<Highlights data={null} scope="community" error={new Error("Falhou.")} onRetry={() => {}} />);
  assert.match(failed, /Não foi possível carregar as novidades/);
});
