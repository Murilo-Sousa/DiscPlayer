// Cliente HTTP do front-end.
//
// - A sessão vive em um cookie HttpOnly: o JavaScript nunca vê nem guarda senha ou sessão.
// - O token de CSRF vem do servidor (GET /api/auth/me) e fica só em memória; ele é
//   enviado no cabeçalho X-CSRF-Token em toda requisição que altera dados.
// - Falhas viram ApiError, com mensagem pronta para mostrar ao usuário.
// - O corpo é JSON, exceto quando é um FormData (envio de arquivo): aí o navegador define o
//   Content-Type com o "boundary" do multipart, e nós não devemos mexer nele.

const API_ORIGIN = (import.meta.env?.VITE_API_URL ?? "").replace(/\/$/, "");
const BASE_URL = `${API_ORIGIN}/api`;
// Com a API em outra origem (VITE_API_URL), o cookie só viaja com "include".
const CREDENTIALS = API_ORIGIN ? "include" : "same-origin";

export class ApiError extends Error {
  constructor({ status = 0, code = "unknown", message = "Algo deu errado.", fields = null, retryAfter = null }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.retryAfter = retryAfter;
  }
}

const FALLBACK_MESSAGES = {
  0: "Não foi possível falar com o servidor. Verifique sua conexão e tente de novo.",
  401: "Entre na sua conta para continuar.",
  403: "Você não tem permissão para fazer isso.",
  404: "Não encontramos o que você procurou.",
  413: "O arquivo enviado é grande demais.",
  429: "Muitas tentativas em pouco tempo. Aguarde um instante e tente de novo.",
  500: "Algo deu errado do nosso lado. Tente novamente.",
  502: "O servidor está indisponível no momento. Tente novamente em instantes.",
  503: "O servidor está indisponível no momento. Tente novamente em instantes.",
  504: "O servidor demorou demais para responder. Tente novamente.",
};

let csrfToken = null;
let csrfRequest = null;

export function setCsrfToken(token) {
  csrfToken = token || null;
}

export function resetHttpState() {
  csrfToken = null;
  csrfRequest = null;
}

/** Endereço completo de um arquivo servido pela API (como a foto de perfil), que vem como "/api/...". */
export function assetUrl(path) {
  return `${API_ORIGIN}${path}`;
}

function buildUrl(path, params) {
  const url = `${BASE_URL}${path}`;
  if (!params) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `${url}?${query}` : url;
}

async function readBody(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null; // por exemplo, uma página HTML de erro de um proxy
  }
}

function toApiError(response, body) {
  const error = body?.error;
  return new ApiError({
    status: response.status,
    code: error?.code ?? "http_error",
    message: error?.message ?? FALLBACK_MESSAGES[response.status] ?? FALLBACK_MESSAGES[500],
    fields: error?.fields ?? null,
    retryAfter: Number(response.headers?.get?.("Retry-After")) || null,
  });
}

/** Garante que existe um token de CSRF (busca no servidor se preciso). */
export async function ensureCsrf(force = false) {
  if (csrfToken && !force) return csrfToken;
  if (!csrfRequest) {
    csrfRequest = fetch(buildUrl("/auth/me"), { credentials: CREDENTIALS, headers: { Accept: "application/json" } })
      .then(readBody)
      .then((body) => {
        if (body?.csrf_token) csrfToken = body.csrf_token;
        return csrfToken;
      })
      .finally(() => {
        csrfRequest = null;
      });
  }
  const token = await csrfRequest;
  if (!token) throw new ApiError({ status: 0, code: "network", message: FALLBACK_MESSAGES[0] });
  return token;
}

export async function request(method, path, { body, params, signal, retried = false } = {}) {
  const headers = { Accept: "application/json" };
  if (method !== "GET") headers["X-CSRF-Token"] = await ensureCsrf();
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
      credentials: CREDENTIALS,
      signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new ApiError({ status: 0, code: "network", message: FALLBACK_MESSAGES[0] });
  }

  const data = await readBody(response);
  if (!response.ok) {
    // Token vencido (por exemplo, a sessão expirou): pega um novo e tenta uma vez mais.
    if (response.status === 403 && data?.error?.code === "csrf_invalid" && !retried) {
      await ensureCsrf(true);
      return request(method, path, { body, params, signal, retried: true });
    }
    throw toApiError(response, data);
  }
  if (data?.csrf_token) csrfToken = data.csrf_token;
  return data;
}

export const http = {
  get: (path, options) => request("GET", path, options),
  post: (path, body, options) => request("POST", path, { ...options, body: body ?? {} }),
  put: (path, body, options) => request("PUT", path, { ...options, body: body ?? {} }),
  patch: (path, body, options) => request("PATCH", path, { ...options, body: body ?? {} }),
  delete: (path, options) => request("DELETE", path, options),
};
