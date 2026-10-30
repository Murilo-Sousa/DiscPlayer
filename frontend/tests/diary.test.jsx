import assert from "node:assert/strict";
import { test } from "node:test";
import { StatusPicker } from "../src/components/StatusPicker.jsx";
import { AuthContext } from "../src/context/AuthContext.jsx";
import { ToastProvider } from "../src/context/ToastContext.jsx";
import { DiaryPanel } from "../src/pages/game/DiaryPanel.jsx";
import { ReviewPanel } from "../src/pages/game/ReviewPanel.jsx";
import {
  COMPLETABLE,
  REPLAYABLE,
  STARTED,
  canReplay,
  hasCompletionDate,
  hasStarted,
  isReleased,
  ratingAccess,
  statusBlockedReason,
} from "../src/utils/diary.js";
import { count, html } from "./helpers.jsx";

const out = { rawg_id: 5, name: "Hades", released: "2020-09-17" };
const upcoming = { rawg_id: 6, name: "Farol do Amanhã", released: "2999-01-01" };
const entry = (status, extra = {}) => ({
  status,
  is_favorite: false,
  started_at: status === "quero_jogar" ? null : "2025-01-10",
  completed_at: status === "zerado" ? "2025-02-10" : null,
  status_changed_at: "2025-02-10T10:00:00Z",
  created_at: "2025-01-10T10:00:00Z",
  updated_at: "2025-02-10T10:00:00Z",
  plays: 1,
  ...extra,
});
const ana = { username: "ana", display_name: "Ana", avatar_url: null };

/** Renderiza dentro de uma pessoa logada (sem chamar a API). */
function loggedIn(element) {
  return html(
    <AuthContext.Provider value={{ user: ana, ready: true }}>
      <ToastProvider>{element}</ToastProvider>
    </AuthContext.Provider>,
  );
}

const diary = (props) =>
  loggedIn(<DiaryPanel rawgId={5} game={out} playthroughs={[]} onSaved={() => {}} onRemoved={() => {}} {...props} />);
const rating = (props) => loggedIn(<ReviewPanel rawgId={5} game={out} onChanged={() => {}} {...props} />);

// ----------------------------------------------------------------------------- as regras
test("regras: quais status já foram começados, quais têm data de término e quais se jogam de novo", () => {
  assert.deepEqual(STARTED, ["jogando", "pausado", "abandonado", "zerado"]);
  assert.deepEqual(COMPLETABLE, ["zerado"]);
  assert.deepEqual(REPLAYABLE, ["zerado", "abandonado"]);
  assert.equal(hasStarted("quero_jogar"), false);
  assert.equal(hasStarted("pausado"), true);
  assert.equal(hasCompletionDate("abandonado"), false);
  assert.equal(hasCompletionDate("zerado"), true);
  assert.equal(canReplay("pausado"), false);
  assert.equal(canReplay("abandonado"), true);
});

test("isReleased: sem data de lançamento conhecida, ninguém é barrado; o dia do lançamento já vale", () => {
  assert.equal(isReleased(null, "2026-10-27"), true);
  assert.equal(isReleased("2026-10-27", "2026-10-27"), true);
  assert.equal(isReleased("2026-10-28", "2026-10-27"), false);
});

test("statusBlockedReason: a fila fecha para jogo avaliado ou já jogado; jogo não lançado só vai para a fila", () => {
  const now = { today: "2026-10-27" };
  assert.equal(statusBlockedReason("quero_jogar", { game: out, ...now }), null);
  assert.match(statusBlockedReason("quero_jogar", { game: out, hasRating: true, ...now }), /já avaliou/);
  assert.match(statusBlockedReason("quero_jogar", { game: out, playthroughs: 1, ...now }), /jogadas anteriores/);
  assert.equal(statusBlockedReason("jogando", { game: out, ...now }), null);
  assert.match(statusBlockedReason("jogando", { game: upcoming, ...now }), /Só sai em/);
  assert.equal(statusBlockedReason("quero_jogar", { game: upcoming, ...now }), null);
});

test("ratingAccess: só avalia quem já começou um jogo já lançado", () => {
  const now = { today: "2026-10-27" };
  assert.equal(ratingAccess({ entry: null, game: out, ...now }).allowed, false);
  assert.match(ratingAccess({ entry: null, game: out, ...now }).reason, /Registre o jogo no seu diário/);
  assert.match(ratingAccess({ entry: entry("quero_jogar"), game: out, ...now }).reason, /Quero jogar/);
  for (const status of STARTED) assert.deepEqual(ratingAccess({ entry: entry(status), game: out, ...now }), { allowed: true, reason: null });
  assert.match(ratingAccess({ entry: entry("quero_jogar"), game: upcoming, ...now }).reason, /só será lançado/);
});

// ----------------------------------------------------------------------------- seletor de status
test("StatusPicker: um status bloqueado fica desabilitado, com o motivo, e os outros continuam livres", () => {
  const markup = html(<StatusPicker value="zerado" onChange={() => {}} blocked={{ quero_jogar: "Você já avaliou este jogo." }} />);
  assert.equal(count(markup, /disabled=""/g), 1);
  assert.match(markup, /title="Você já avaliou este jogo\."/);
  assert.equal(count(html(<StatusPicker value="zerado" onChange={() => {}} />), /disabled=""/g), 0);
});

// ----------------------------------------------------------------------------- painel do diário
test("diário em 'Quero jogar': sem datas e sem favorito, só a explicação da fila", () => {
  const markup = diary({ entry: entry("quero_jogar") });
  assert.doesNotMatch(markup, /Comecei em/);
  assert.doesNotMatch(markup, /Terminei em/);
  assert.doesNotMatch(markup, /Salvar datas/);
  assert.doesNotMatch(markup, /Favoritar/);
  assert.match(markup, /Na fila\./);
  assert.doesNotMatch(markup, /Jogar de novo/);
});

for (const status of ["jogando", "pausado"]) {
  test(`diário em '${status}': só a data de início, com favorito e sem 'jogar de novo'`, () => {
    const markup = diary({ entry: entry(status) });
    assert.match(markup, /Comecei em/);
    assert.doesNotMatch(markup, /Terminei em/);
    assert.match(markup, /Favoritar/);
    assert.doesNotMatch(markup, /Jogar de novo/);
  });
}

test("diário em 'Abandonado': início e favorito, sem data de término, e dá para jogar de novo", () => {
  const markup = diary({ entry: entry("abandonado") });
  assert.match(markup, /Comecei em/);
  assert.doesNotMatch(markup, /Terminei em/);
  assert.match(markup, /Jogar de novo/);
});

test("diário em 'Zerado': as duas datas, o intervalo entre elas e 'jogar de novo'", () => {
  const markup = diary({ entry: entry("zerado") });
  assert.match(markup, /Comecei em/);
  assert.match(markup, /Terminei em/);
  assert.match(markup, /31 dias entre começar e terminar/);
  assert.match(markup, /Jogar de novo/);
});

test("diário: com nota, a fila fica bloqueada e o motivo aparece por escrito", () => {
  const markup = diary({ entry: entry("zerado"), hasRating: true });
  assert.match(markup, /Você já avaliou este jogo, então ele não volta para a fila/);
  assert.equal(count(markup, /data-status="quero_jogar"[^>]*disabled=""/g), 1);
  assert.equal(count(markup, /status-option"[^>]*disabled=""/g), 1); // só a fila
});

test("diário: jogo ainda não lançado só deixa escolher a fila", () => {
  const markup = diary({ game: upcoming, entry: null });
  assert.match(markup, /Lança em/);
  assert.equal(count(markup, /status-option"[^>]*disabled=""/g), 4); // jogando, pausado, abandonado e zerado
  assert.doesNotMatch(markup, /data-status="quero_jogar"[^>]*disabled=""/);
  // o seletor aponta para a frase que explica por que quase tudo está apagado (leitores de tela leem o motivo)
  assert.match(markup, /id="diary-hint"/);
  assert.match(markup, /class="status-picker"[^>]*aria-describedby="diary-hint"/);
});

// ----------------------------------------------------------------------------- painel da nota
test("nota: fora do diário o painel explica o que falta, sem formulário", () => {
  const markup = rating({ entry: null, review: null });
  assert.match(markup, /Registre o jogo no seu diário/);
  assert.doesNotMatch(markup, /type="range"/);
  assert.doesNotMatch(markup, /Publicar/);
});

test("nota: na fila o painel também fica trancado", () => {
  const markup = rating({ entry: entry("quero_jogar"), review: null });
  assert.match(markup, /Você marcou este jogo como “Quero jogar”/);
  assert.doesNotMatch(markup, /type="range"/);
});

test("nota: jogo ainda não lançado fica trancado mesmo com o jogo no diário", () => {
  const markup = rating({ game: upcoming, entry: entry("quero_jogar"), review: null });
  assert.match(markup, /só será lançado em/);
});

for (const status of STARTED) {
  test(`nota: em '${status}' o formulário aparece`, () => {
    const markup = rating({ entry: entry(status), review: null });
    assert.match(markup, /type="range"/);
    assert.match(markup, /Publicar/);
  });
}

test("nota: uma review que já existe continua visível e editável mesmo sem o jogo estar jogado", () => {
  const review = { id: 1, rating: 8, body: "Boa.", has_spoilers: false, created_at: "2025-02-02T10:00:00Z", updated_at: null, like_count: 0, liked: false };
  const markup = rating({ entry: null, review });
  assert.match(markup, /Sua review/);
  assert.match(markup, /Editar/);
  assert.match(markup, /Excluir/);
});

// ----------------------------------------------------------------------------- o que a tela envia ao servidor
test("a API manda a confirmação da nota só quando há nota, e o 'hoje' de quem avalia", async () => {
  const { libraryApi, reviewsApi } = await import("../src/services/api.js");
  const realFetch = globalThis.fetch;
  const sent = [];
  globalThis.fetch = async (url, options = {}) => {
    const body = String(url).endsWith("/auth/me") ? { csrf_token: "t" } : {};
    if (!String(url).endsWith("/auth/me")) sent.push({ method: options.method, url: String(url), body: options.body });
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  };
  try {
    await libraryApi.remove(1234);
    await libraryApi.remove(1234, { withReview: true });
    await reviewsApi.create(1234, { rating: 8 });
  } finally {
    globalThis.fetch = realFetch;
  }
  assert.deepEqual(sent[0], { method: "DELETE", url: "/api/library/1234", body: undefined });
  assert.deepEqual(sent[1], { method: "DELETE", url: "/api/library/1234", body: JSON.stringify({ with_review: true }) });
  const review = JSON.parse(sent[2].body);
  assert.equal(review.rating, 8);
  assert.match(review.today, /^\d{4}-\d{2}-\d{2}$/);
});
