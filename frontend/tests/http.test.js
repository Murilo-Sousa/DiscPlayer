import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { ApiError, http, resetHttpState, setCsrfToken } from "../src/services/http.js";

const realFetch = globalThis.fetch;
let calls;

const json = (body, init = {}) =>
  new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" }, ...init });

/** Substitui o fetch por uma fila de respostas (ou funções) e registra cada chamada. */
function mockFetch(...queue) {
  calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, ...options });
    const next = queue.length > 1 ? queue.shift() : queue[0];
    const value = typeof next === "function" ? await next(url, options) : next;
    if (value instanceof Error) throw value;
    return value;
  };
}

beforeEach(() => resetHttpState());
afterEach(() => {
  globalThis.fetch = realFetch;
});

test("GET não envia CSRF nem consulta /auth/me", async () => {
  mockFetch(json({ ok: true }));
  const data = await http.get("/games", { params: { q: "hades", page: 2, genre: "", year: null } });
  assert.deepEqual(data, { ok: true });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/games?q=hades&page=2");
  assert.equal(calls[0].method, "GET");
  assert.equal(calls[0].headers["X-CSRF-Token"], undefined);
  assert.equal(calls[0].credentials, "same-origin");
});

test("POST busca o token uma vez e o envia no cabeçalho, com o corpo em JSON", async () => {
  mockFetch(
    json({ user: null, csrf_token: "tok-1" }), // GET /auth/me
    json({ created: true }, { status: 201 }),
    json({ created: true }, { status: 201 }),
  );
  await http.post("/lists", { title: "A" });
  await http.post("/lists", { title: "B" });
  assert.equal(calls[0].url, "/api/auth/me");
  assert.equal(calls.length, 3, "o token é reaproveitado na segunda requisição");
  assert.equal(calls[1].headers["X-CSRF-Token"], "tok-1");
  assert.equal(calls[1].headers["Content-Type"], "application/json");
  assert.equal(calls[1].body, JSON.stringify({ title: "A" }));
});

test("token já conhecido evita a consulta extra", async () => {
  setCsrfToken("abc");
  mockFetch(json({ ok: true }));
  await http.delete("/reviews/3");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].headers["X-CSRF-Token"], "abc");
});

test("csrf_invalid: renova o token e tenta de novo uma única vez", async () => {
  setCsrfToken("velho");
  mockFetch(
    json({ error: { code: "csrf_invalid", message: "Sessão expirada." } }, { status: 403 }),
    json({ user: null, csrf_token: "novo" }),
    json({ saved: true }),
  );
  const data = await http.put("/library/1", { status: "jogando" });
  assert.deepEqual(data, { saved: true });
  assert.equal(calls[0].headers["X-CSRF-Token"], "velho");
  assert.equal(calls[2].headers["X-CSRF-Token"], "novo");
});

test("csrf_invalid persistente vira erro depois de uma tentativa", async () => {
  setCsrfToken("velho");
  mockFetch(
    json({ error: { code: "csrf_invalid", message: "Token inválido." } }, { status: 403 }),
    json({ user: null, csrf_token: "outro" }),
    json({ error: { code: "csrf_invalid", message: "Token inválido." } }, { status: 403 }),
  );
  await assert.rejects(http.post("/x", {}), (error) => error instanceof ApiError && error.code === "csrf_invalid");
  assert.equal(calls.length, 3);
});

test("erros da API viram ApiError com código, mensagem e campos", async () => {
  mockFetch(
    json(
      { error: { code: "validation_error", message: "Revise os campos destacados.", fields: { rating: "A nota deve ficar entre 0 e 10." } } },
      { status: 422 },
    ),
  );
  await assert.rejects(http.get("/x"), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 422);
    assert.equal(error.code, "validation_error");
    assert.equal(error.message, "Revise os campos destacados.");
    assert.deepEqual(error.fields, { rating: "A nota deve ficar entre 0 e 10." });
    return true;
  });
});

test("resposta que não é JSON (proxy) usa a mensagem padrão do status", async () => {
  mockFetch(new Response("<html>Bad gateway</html>", { status: 502 }));
  await assert.rejects(http.get("/x"), (error) => {
    assert.equal(error.status, 502);
    assert.match(error.message, /indisponível/);
    return true;
  });
});

test("429 guarda o Retry-After", async () => {
  mockFetch(json({ error: { code: "rate_limited", message: "Muitas tentativas." } }, { status: 429, headers: { "Retry-After": "30", "Content-Type": "application/json" } }));
  await assert.rejects(http.get("/x"), (error) => error.status === 429 && error.retryAfter === 30);
});

test("falha de rede vira ApiError 'network' com texto para o usuário", async () => {
  mockFetch(new TypeError("Failed to fetch"));
  await assert.rejects(http.get("/x"), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.code, "network");
    assert.equal(error.status, 0);
    assert.match(error.message, /conexão/);
    return true;
  });
});

test("AbortError é repassado como está (a tela cancelou de propósito)", async () => {
  mockFetch(Object.assign(new Error("aborted"), { name: "AbortError" }));
  await assert.rejects(http.get("/x"), (error) => error.name === "AbortError");
});
