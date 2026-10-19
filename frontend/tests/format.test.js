import assert from "node:assert/strict";
import { test } from "node:test";
import {
  cleanParams,
  daysBetween,
  formatAverage,
  formatDate,
  formatMonthYear,
  formatRating,
  formatYear,
  gamePath,
  hueFrom,
  initials,
  isImageUrl,
  paragraphs,
  parseGameParam,
  plural,
  statusLabel,
  timeAgo,
} from "../src/utils/format.js";

test("formatRating usa vírgula e omite o zero decimal", () => {
  assert.equal(formatRating(8.5), "8,5");
  assert.equal(formatRating(10), "10");
  assert.equal(formatRating(0), "0");
  assert.equal(formatRating(0.5), "0,5");
  assert.equal(formatRating(null), "—");
  assert.equal(formatRating(undefined), "—");
});

test("formatAverage mostra até duas casas, sem zeros à direita", () => {
  assert.equal(formatAverage(8.3333), "8,33");
  assert.equal(formatAverage(7.75), "7,75");
  assert.equal(formatAverage(8), "8");
  assert.equal(formatAverage(null), "—");
});

test("datas AAAA-MM-DD são datas de calendário, sem deslocamento de fuso", () => {
  assert.equal(formatYear("2020-01-01"), "2020");
  assert.equal(formatYear("2020-12-31"), "2020");
  assert.equal(formatDate("2024-03-05"), "5 de mar de 2024");
  assert.equal(formatDate(null), "");
  assert.equal(formatDate("lixo"), "");
  assert.match(formatMonthYear("2026-10-17"), /outubro de 2026/);
});

test("timeAgo", () => {
  const now = new Date("2026-10-17T12:00:00Z").getTime();
  assert.equal(timeAgo("2026-10-17T11:59:50Z", now), "agora");
  assert.equal(timeAgo("2026-10-17T11:55:00Z", now), "há 5 min");
  assert.equal(timeAgo("2026-10-17T09:00:00Z", now), "há 3 h");
  assert.equal(timeAgo("2026-10-16T12:00:00Z", now), "há 1 dia");
  assert.equal(timeAgo("2026-10-14T12:00:00Z", now), "há 3 dias");
  assert.equal(timeAgo("2026-09-01T12:00:00Z", now), "1 de set de 2026");
  assert.equal(timeAgo("", now), "");
});

test("daysBetween", () => {
  assert.equal(daysBetween("2026-01-01", "2026-01-11"), 10);
  assert.equal(daysBetween("2026-01-01", "2026-01-01"), 0);
  assert.equal(daysBetween("2026-01-01", null), null);
});

test("plural", () => {
  assert.equal(plural(1, "nota", "notas"), "1 nota");
  assert.equal(plural(0, "nota", "notas"), "0 notas");
  assert.equal(plural(2, "nota", "notas"), "2 notas");
});

test("initials e hueFrom são estáveis", () => {
  assert.equal(initials("Ana Souza"), "AS");
  assert.equal(initials("ana"), "AN");
  assert.equal(initials("  "), "?");
  assert.equal(initials(null), "?");
  assert.equal(initials("Maria de Lourdes Silva"), "MS");
  assert.equal(hueFrom("ana"), hueFrom("ana"));
  assert.ok(hueFrom("ana") >= 0 && hueFrom("ana") < 360);
  assert.notEqual(hueFrom("ana"), hueFrom("bruno"));
});

test("paragraphs separa por linha em branco e descarta vazios", () => {
  assert.deepEqual(paragraphs("um\n\ndois\n\n\n\ntrês"), ["um", "dois", "três"]);
  assert.deepEqual(paragraphs("  \n\n "), []);
  assert.deepEqual(paragraphs(null), []);
  assert.deepEqual(paragraphs("linha 1\nlinha 2"), ["linha 1\nlinha 2"]);
});

test("gamePath e parseGameParam", () => {
  assert.equal(gamePath({ rawg_id: 3498, slug: "gta-v" }), "/jogos/3498-gta-v");
  assert.equal(gamePath({ rawg_id: 7 }), "/jogos/7");
  assert.equal(parseGameParam("3498-gta-v"), 3498);
  assert.equal(parseGameParam("3498"), 3498);
  assert.equal(parseGameParam("abc"), null);
  assert.equal(parseGameParam("-5"), null);
  assert.equal(parseGameParam(undefined), null);
  assert.equal(parseGameParam("12abc"), null);
});

test("statusLabel cobre os cinco status", () => {
  assert.deepEqual(
    ["quero_jogar", "jogando", "zerado", "abandonado", "pausado"].map(statusLabel),
    ["Quero jogar", "Jogando", "Zerado", "Abandonado", "Pausado"],
  );
  assert.equal(statusLabel("inventado"), "Sem status");
});

test("cleanParams remove vazios mas mantém zero", () => {
  assert.deepEqual(cleanParams({ a: "x", b: "", c: null, d: undefined, e: 0, f: false }), { a: "x", e: 0 });
});

test("isImageUrl aceita só endereços https completos", () => {
  assert.equal(isImageUrl("https://media.rawg.io/a.png"), true);
  assert.equal(isImageUrl("  https://exemplo.com/foto.jpg  "), true);
  for (const bad of ["http://exemplo.com/a.png", "javascript:alert(1)", "data:image/png;base64,AAAA", "//exemplo.com/a.png", "https://", "https://localhost", "exemplo.com/a.png", "", null, undefined, 42]) {
    assert.equal(isImageUrl(bad), false, String(bad));
  }
});
