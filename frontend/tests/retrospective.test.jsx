import assert from "node:assert/strict";
import { test } from "node:test";
import { ToastProvider } from "../src/context/ToastContext.jsx";
import { RetrospectiveView, headline, shareText } from "../src/pages/RetrospectivePage.jsx";
import { shareLink } from "../src/utils/share.js";
import {
  daysText,
  isYearParam,
  retrospectiveImagePath,
  retrospectivePath,
} from "../src/utils/format.js";
import { count, html } from "./helpers.jsx";

const game = (id, name, slug = name.toLowerCase().replace(/\W+/g, "-")) => ({
  rawg_id: id,
  name,
  slug,
  cover_url: null,
  cover_thumb_url: null,
  released: "2020-09-17",
});

function sample(overrides = {}) {
  const hades = game(1, "Hades");
  const celeste = game(2, "Celeste");
  return {
    user: { username: "ana", display_name: "Ana Souza", avatar_url: null },
    year: 2025,
    partial: false,
    years: [2025, 2024],
    empty: false,
    totals: { completed: 3, completed_games: 2, started: 4, abandoned: 1, replays: 2 },
    by_month: [0, 0, 2, 0, 1, 0, 0, 0, 0, 0, 0, 0],
    busiest_month: 3,
    game_of_the_year: { game: hades, rating: 9.5, completed_at: "2025-03-20", times: 1, days: 19 },
    completed_games: [
      { game: hades, rating: 9.5, completed_at: "2025-03-20", times: 1, days: 19 },
      { game: celeste, rating: null, completed_at: "2025-05-04", times: 2, days: 3 },
    ],
    pace: {
      average_days: 11,
      fastest: { game: celeste, days: 3, completed_at: "2025-05-04" },
      longest: { game: hades, days: 19, completed_at: "2025-03-20" },
    },
    ratings: { count: 2, average: 8.75, with_text: 1, distribution: [0, 0, 0, 0, 0, 0, 0, 0, 1, 1] },
    social: { likes_received: 5, new_followers: 2, lists_created: 1 },
    ...overrides,
  };
}

const render = (data, { isSelf = false, url = "/u/ana/retrospectiva/2025", shareUrl = "https://exemplo.com/u/ana/retrospectiva/2025" } = {}) =>
  html(
    <ToastProvider>
      <RetrospectiveView data={data} isSelf={isSelf} shareUrl={shareUrl} />
    </ToastProvider>,
    url,
  );

// --------------------------------------------------------------------------- página
test("retrospectiva completa: título, número grande, números e jogo do ano", () => {
  const markup = render(sample());
  assert.match(markup, /<h1[^>]*>Retrospectiva <span[^>]*>2025<\/span><\/h1>/);
  assert.match(markup, /retro-big-number">3</);
  assert.match(markup, />jogos zerados</);
  assert.match(markup, /2 jogos diferentes: alguns foram zerados mais de uma vez/);
  for (const label of ["Começados", "Abandonados", "Jogados de novo"]) assert.match(markup, new RegExp(label));
  assert.match(markup, /Jogo de 2025/);
  assert.match(markup, /href="\/jogos\/1-hades"/);
  assert.match(markup, /Zerado em 20 de mar de 2025 \(19 dias\)/);
  assert.match(markup, /Mês mais cheio: março, com 2 zerados/);
});

test("um único zerado usa o singular", () => {
  const markup = render(sample({ totals: { completed: 1, completed_games: 1, started: 0, abandoned: 0, replays: 0 } }));
  assert.match(markup, />jogo zerado</);
  assert.doesNotMatch(markup, /jogos diferentes|jogo diferente/);
});

test("a lista de zerados mostra nota, data e duração, e avisa quando está cortada", () => {
  const markup = render(sample({ totals: { completed: 3, completed_games: 18, started: 0, abandoned: 0, replays: 0 } }));
  assert.match(markup, /<span class="retro-cap">Nota 9,5<\/span><span class="retro-cap">20 de mar de 2025 · 19 dias<\/span>/);
  assert.match(markup, /<span class="retro-cap">4 de mai de 2025 · 2 vezes<\/span>/); // zerado duas vezes: sem duração, que seria de uma jogada só
  assert.equal(count(markup, /retro-cap">Nota /g), 1); // sem nota, não há linha de nota
  assert.doesNotMatch(markup, /Nota null|Nota undefined/);
  assert.match(markup, /Mostrando 2 de 18 jogos, dos de maior nota para os sem nota/);
});

test("sem corte, a lista não diz 'mostrando'", () => {
  assert.doesNotMatch(render(sample()), /Mostrando \d+ de/);
});

test("ritmo: só aparece com dados e mostra os dois jogos", () => {
  const markup = render(sample());
  assert.match(markup, /Ritmo/);
  assert.match(markup, />11 dias</);
  assert.match(markup, /Mais rápido/);
  assert.match(markup, /Mais longo/);
  assert.doesNotMatch(render(sample({ pace: null })), /Ritmo|Mais rápido/);
});

test("notas: seção, média e distribuição só com notas no ano", () => {
  const markup = render(sample());
  assert.match(markup, /Notas dadas/);
  assert.match(markup, />8,75</);
  assert.match(markup, /Notas de 9 a 10/);
  const none = render(sample({ ratings: { count: 0, average: null, with_text: 0, distribution: Array(10).fill(0) } }));
  assert.doesNotMatch(none, /Notas dadas/);
});

test("comunidade: só aparece quando há algo e usa o singular", () => {
  assert.match(render(sample()), /Curtidas recebidas/);
  assert.match(render(sample()), /Novos seguidores/);
  const one = render(sample({ social: { likes_received: 1, new_followers: 1, lists_created: 1 } }));
  assert.match(one, /Curtida recebida/);
  assert.match(one, /Novo seguidor/);
  assert.match(one, /Lista pública criada/);
  assert.doesNotMatch(render(sample({ social: { likes_received: 0, new_followers: 0, lists_created: 0 } })), /Na comunidade/);
});

test("sem jogo zerado: nenhuma invenção (sem gráfico, jogo do ano nem lista)", () => {
  const markup = render(
    sample({
      totals: { completed: 0, completed_games: 0, started: 2, abandoned: 0, replays: 0 },
      by_month: Array(12).fill(0),
      busiest_month: null,
      game_of_the_year: null,
      completed_games: [],
      pace: null,
    }),
  );
  assert.match(markup, /Nenhum jogo zerado em 2025/);
  assert.doesNotMatch(markup, /retro-big-number|Zerados por mês|Jogo de 2025|Zerados em 2025|Mês mais cheio/);
});

test("jogo do ano repetido no ano diz quantas vezes, sem duração", () => {
  const celeste = game(2, "Celeste");
  const markup = render(sample({ game_of_the_year: { game: celeste, rating: 10, completed_at: "2025-05-04", times: 2, days: 3 } }));
  assert.match(markup, /Zerado em 4 de mai de 2025, 2 vezes no ano/);
  assert.doesNotMatch(markup, /\(3 dias\)/); // a duração é de uma jogada só: com duas, não vale para o jogo
});

test("ano em andamento avisa que os números vão até hoje", () => {
  assert.match(render(sample({ partial: true })), /2025 ainda está em andamento/);
  assert.doesNotMatch(render(sample()), /ainda está em andamento/);
});

test("ano vazio: estado vazio, sem botão de compartilhar nem imagem", () => {
  const empty = sample({ empty: true, year: 2023 });
  const other = render(empty, { url: "/u/ana/retrospectiva/2023" });
  assert.match(other, /<h2 class="state-title">Nada registrado em 2023<\/h2>/); // logo depois do h1: sem pular nível
  assert.match(other, /Ana Souza não registrou nada em 2023/);
  assert.doesNotMatch(other, /Compartilhar|retro-card|retro-big-number|Adicionar jogos/);
  const self = render(empty, { isSelf: true, url: "/u/ana/retrospectiva/2023" });
  assert.match(self, /Quando você registrar jogos/);
  assert.match(self, /href="\/jogos"/);
});

test("navegação entre anos: link por ano e o atual marcado", () => {
  const markup = render(sample());
  assert.match(markup, /aria-label="Anos com registros"/);
  assert.match(markup, /href="\/u\/ana\/retrospectiva\/2024"/);
  assert.match(markup, /href="\/u\/ana\/retrospectiva\/2025"[^>]*aria-current="page"|aria-current="page"[^>]*href="\/u\/ana\/retrospectiva\/2025"/);
  assert.equal(count(markup, /aria-current="page"/g), 1);
});

test("com um só ano, e ele aberto, não há navegação", () => {
  assert.doesNotMatch(render(sample({ years: [2025] })), /Anos com registros/);
  assert.doesNotMatch(render(sample({ years: [] })), /Anos com registros/);
});

test("um ano sem dados entra na navegação para a pessoa poder voltar", () => {
  const markup = render(sample({ empty: true, year: 2019, years: [2025, 2024] }), { url: "/u/ana/retrospectiva/2019" });
  assert.match(markup, /href="\/u\/ana\/retrospectiva\/2019"/);
  assert.match(markup, /href="\/u\/ana\/retrospectiva\/2025"/);
});

test("a imagem de compartilhamento aponta para o servidor, com texto alternativo e download", () => {
  const markup = render(sample());
  assert.match(markup, /src="\/api\/share\/retrospective\/ana\/2025\.png"/);
  assert.match(markup, /width="1200" height="630"/);
  assert.match(markup, /alt="Imagem de compartilhamento: Retrospectiva 2025 de Ana Souza, 3 jogos zerados"/);
  assert.match(markup, /href="\/api\/share\/retrospective\/ana\/2025\.png" download="retrospectiva-2025-ana\.png"/);
  assert.match(markup, /Compartilhar<\/button>/);
});

test("texto de pessoas e jogos é escapado (nunca vira marcação)", () => {
  const evil = '<img src=x onerror="alert(1)">';
  const data = sample({
    user: { username: "ana", display_name: evil, avatar_url: null },
    game_of_the_year: { game: game(1, evil, "slug"), rating: 9, completed_at: "2025-03-20", times: 1, days: 1 },
    completed_games: [{ game: game(1, evil, "slug"), rating: 9, completed_at: "2025-03-20", times: 1, days: 1 }],
  });
  const markup = render(data);
  assert.doesNotMatch(markup, /<img src=x/);
  assert.match(markup, /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
});

test("explica como os números são calculados e o que não existe", () => {
  const markup = render(sample());
  assert.match(markup, /Como esses números são calculados/);
  assert.match(markup, /não guarda gêneros nem horas jogadas/);
  assert.match(markup, /listas privadas ficam de fora/);
});

test("o avatar e o nome levam ao perfil", () => {
  assert.match(render(sample()), /class="retro-owner"[^>]*>|href="\/u\/ana"[^>]*class="retro-owner"/);
  assert.match(render(sample()), /href="\/u\/ana"/);
});

test("o texto da imagem diz o mesmo número que o cartão desenha (jogos zerados, começados, notas...)", () => {
  const base = sample();
  const none = { completed: 0, completed_games: 0, started: 0, abandoned: 0, replays: 0 };
  const noRatings = { count: 0, average: null, with_text: 0, distribution: Array(10).fill(0) };
  assert.equal(headline(base), "3 jogos zerados");
  assert.equal(headline({ ...base, totals: { ...none, started: 3 } }), "3 jogos começados");
  assert.equal(headline({ ...base, totals: { ...none, started: 1 } }), "1 jogo começado");
  assert.equal(headline({ ...base, totals: none, ratings: { ...noRatings, count: 2 } }), "2 notas dadas");
  assert.equal(headline({ ...base, totals: { ...none, abandoned: 1 }, ratings: noRatings }), "1 jogo abandonado");
  assert.equal(headline({ ...base, totals: { ...none, replays: 2 }, ratings: noRatings }), "2 recomeços");
  const markup = render(sample({ totals: { ...none, started: 3 }, by_month: Array(12).fill(0), busiest_month: null, game_of_the_year: null, completed_games: [], pace: null }));
  assert.match(markup, /Retrospectiva 2025 de Ana Souza, 3 jogos começados"/);
  assert.doesNotMatch(markup, /0 jogos zerados"/);
});

test("compartilhar não usa disabled: o foco do teclado não se perde", () => {
  const markup = render(sample());
  assert.match(markup, /<button type="button" class="btn btn-primary">Compartilhar<\/button>/);
  assert.doesNotMatch(markup, /Compartilhar<\/button>[^]*disabled/);
});

// --------------------------------------------------------------------------- textos e caminhos
test("shareText fala em primeira pessoa só para a dona e usa só números reais", () => {
  assert.equal(shareText(sample(), true), "Minha retrospectiva 2025 no DiscPlayer: 3 jogos zerados.");
  assert.equal(shareText(sample(), false), "Retrospectiva de Ana Souza 2025 no DiscPlayer: 3 jogos zerados.");
  const none = sample({ totals: { completed: 0, completed_games: 0, started: 1, abandoned: 0, replays: 0 } });
  assert.equal(shareText(none, true), "Minha retrospectiva 2025 no DiscPlayer.");
  const one = sample({ totals: { completed: 1, completed_games: 1, started: 0, abandoned: 0, replays: 0 } });
  assert.equal(shareText(one, true), "Minha retrospectiva 2025 no DiscPlayer: 1 jogo zerado.");
});

test("caminhos da retrospectiva e da imagem", () => {
  assert.equal(retrospectivePath("ana"), "/u/ana/retrospectiva");
  assert.equal(retrospectivePath("ana", 2025), "/u/ana/retrospectiva/2025");
  assert.equal(retrospectivePath("a b", 2025), "/u/a%20b/retrospectiva/2025");
  assert.equal(retrospectiveImagePath("ana", 2025), "/api/share/retrospective/ana/2025.png");
});

test("isYearParam aceita só quatro dígitos", () => {
  for (const ok of ["2025", "2000", "1999"]) assert.equal(isYearParam(ok), true);
  for (const bad of ["25", "20255", "abcd", "2025a", "", " 2025", undefined, null, 2025]) assert.equal(isYearParam(bad), false);
});

test("daysText", () => {
  assert.equal(daysText(0), "no mesmo dia");
  assert.equal(daysText(1), "1 dia");
  assert.equal(daysText(19), "19 dias");
  assert.equal(daysText(null), "");
  assert.equal(daysText(undefined), "");
});

// --------------------------------------------------------------------------- compartilhar
const abort = () => Object.assign(new Error("fechou"), { name: "AbortError" });
const payload = { url: "https://exemplo.com/u/ana/retrospectiva/2025", title: "Título", text: "Texto" };

test("shareLink usa o menu do aparelho quando existe", async () => {
  const sent = [];
  const nav = { share: async (data) => sent.push(data), clipboard: { writeText: async () => assert.fail("não deveria copiar") } };
  assert.equal(await shareLink(payload, nav), "shared");
  assert.deepEqual(sent, [{ title: "Título", text: "Texto", url: payload.url }]);
});

test("fechar o menu de compartilhar não é erro e não copia nada", async () => {
  const nav = { share: async () => { throw abort(); }, clipboard: { writeText: async () => assert.fail("não deveria copiar") } };
  assert.equal(await shareLink(payload, nav), "cancelled");
});

test("se o menu falhar por outro motivo, copia o endereço", async () => {
  const copied = [];
  const nav = { share: async () => { throw new Error("indisponível"); }, clipboard: { writeText: async (text) => copied.push(text) } };
  assert.equal(await shareLink(payload, nav), "copied");
  assert.deepEqual(copied, [payload.url]);
});

test("sem menu de compartilhar, copia o endereço", async () => {
  const copied = [];
  assert.equal(await shareLink(payload, { clipboard: { writeText: async (text) => copied.push(text) } }), "copied");
  assert.deepEqual(copied, [payload.url]);
});

test("se copiar falhar (ou não existir), o resultado é 'failed'", async () => {
  assert.equal(await shareLink(payload, { clipboard: { writeText: async () => { throw new Error("negado"); } } }), "failed");
  assert.equal(await shareLink(payload, {}), "failed");
  assert.equal(await shareLink(payload, undefined), "failed");
  assert.equal(await shareLink(payload, null), "failed");
});

// --------------------------------------------------------------------------- chamada da API
test("usersApi.retrospective monta o endereço com e sem ano e codifica o usuário", async () => {
  const { usersApi } = await import("../src/services/api.js");
  const realFetch = globalThis.fetch;
  const urls = [];
  globalThis.fetch = async (url) => {
    urls.push(url);
    return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
  };
  try {
    await usersApi.retrospective("ana");
    await usersApi.retrospective("ana", 2025);
    await usersApi.retrospective("a/b", 2024);
  } finally {
    globalThis.fetch = realFetch;
  }
  assert.deepEqual(urls, [
    "/api/users/ana/retrospective",
    "/api/users/ana/retrospective/2025",
    "/api/users/a%2Fb/retrospective/2024",
  ]);
});
