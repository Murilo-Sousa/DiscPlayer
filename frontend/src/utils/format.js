// Formatação de textos, datas e notas (pt-BR). Funções puras, fáceis de testar.

// Ordem das abas do diário.
export const STATUS_ORDER = ["jogando", "quero_jogar", "pausado", "zerado", "abandonado"];
// Ordem do seletor de status: do jogo que ainda não começou até o que foi largado.
export const STATUS_PROGRESS = ["quero_jogar", "jogando", "pausado", "zerado", "abandonado"];

export const STATUS_LABELS = {
  quero_jogar: "Quero jogar",
  jogando: "Jogando",
  zerado: "Zerado",
  abandonado: "Abandonado",
  pausado: "Pausado",
};

export function statusLabel(status) {
  return STATUS_LABELS[status] ?? "Sem status";
}

// Frase usada no histórico: "ana começou a jogar Hades".
export const STATUS_VERBS = {
  quero_jogar: "quer jogar",
  jogando: "começou a jogar",
  zerado: "zerou",
  abandonado: "abandonou",
  pausado: "pausou",
};

/** Nota de 0 a 10 com vírgula decimal: 8.5 -> "8,5"; 10 -> "10"; null -> "—". */
export function formatRating(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const n = Number(value);
  return Number.isInteger(n) ? String(n) : n.toFixed(1).replace(".", ",");
}

/** Média com até duas casas ("8,33"), sem zeros à direita. */
export function formatAverage(value) {
  if (value === null || value === undefined) return "—";
  return String(Math.round(Number(value) * 100) / 100).replace(".", ",");
}

const dateFormat = new Intl.DateTimeFormat("pt-BR", { day: "numeric", month: "short", year: "numeric" });
const monthYearFormat = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" });

/** "Hoje" no fuso de quem usa o site, como "AAAA-MM-DD". O servidor usa isso (e não a data UTC) ao preencher datas. */
export function localToday(now = new Date()) {
  const pad = (number) => String(number).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** Datas "AAAA-MM-DD" são datas de calendário: não passam por fuso horário. */
export function parseDate(value) {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (match) return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value) {
  const date = parseDate(value);
  return date ? dateFormat.format(date).replace(/\./g, "") : "";
}

export function formatMonthYear(value) {
  const date = parseDate(value);
  return date ? monthYearFormat.format(date) : "";
}

export function formatYear(value) {
  const date = parseDate(value);
  return date ? String(date.getFullYear()) : "";
}

/** "agora", "há 5 min", "há 3 h", "há 2 dias" e, depois de uma semana, a data. */
export function timeAgo(iso, now = Date.now()) {
  const date = parseDate(iso);
  if (!date) return "";
  const seconds = Math.max(0, Math.round((now - date.getTime()) / 1000));
  if (seconds < 45) return "agora";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `há ${hours} h`;
  const days = Math.round(hours / 24);
  if (days < 7) return days === 1 ? "há 1 dia" : `há ${days} dias`;
  return formatDate(iso);
}

/** Dias entre duas datas "AAAA-MM-DD" (inclusive nos dois extremos não: diferença simples). */
export function daysBetween(from, to) {
  const a = parseDate(from);
  const b = parseDate(to);
  if (!a || !b) return null;
  return Math.round((b.getTime() - a.getTime()) / 86400000);
}

export function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

export function initials(name) {
  const words = String(name ?? "").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return Array.from(words[0]).slice(0, 2).join("").toUpperCase();
  return (Array.from(words[0])[0] + Array.from(words[words.length - 1])[0]).toUpperCase();
}

/** Endereço de imagem que o site aceita carregar: só https (a política de segurança bloqueia o resto). */
export function isImageUrl(value) {
  if (typeof value !== "string") return false;
  try {
    const url = new URL(value.trim());
    return url.protocol === "https:" && url.hostname.includes(".");
  } catch {
    return false;
  }
}

/** Matiz estável (0-359) derivado de um texto, para avatares e capas sem imagem. */
export function hueFrom(text) {
  let hash = 0;
  for (const char of String(text ?? "")) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
  return hash % 360;
}

export function paragraphs(text) {
  return String(text ?? "")
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);
}

/** Caminho da página de um jogo. O trecho do slug só embeleza a URL. */
export function gamePath(game) {
  const id = game.rawg_id ?? game.id;
  return game.slug ? `/jogos/${id}-${game.slug}` : `/jogos/${id}`;
}

export function parseGameParam(param) {
  const match = /^(\d+)(?:-.*)?$/.exec(param ?? "");
  return match ? Number(match[1]) : null;
}

export const userPath = (username) => `/u/${encodeURIComponent(username)}`;
export const listPath = (id) => `/listas/${id}`;

/** Remove chaves vazias de um objeto de parâmetros de busca. */
export function cleanParams(params) {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== "" && v !== false),
  );
}
