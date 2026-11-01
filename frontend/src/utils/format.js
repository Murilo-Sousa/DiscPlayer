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

/** "Começou a jogar" de quem recomeçou um jogo que já tinha terminado, largado ou pausado. */
export const REPLAY_VERB = "voltou a jogar";

/** Resumo das datas de uma jogada: "12 mar 2025 → 20 mar 2025", "Desde …", "Até …" ou "Sem datas". */
export function playSpan(play) {
  const start = play?.started_at ? formatDate(play.started_at) : "";
  const end = play?.completed_at ? formatDate(play.completed_at) : "";
  if (start && end) return `${start} → ${end}`;
  if (start) return `Desde ${start}`;
  if (end) return `Até ${end}`;
  return "Sem datas";
}

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

/**
 * A foto de perfil é um arquivo enviado e guardado no servidor, entregue em "/api/avatars/<código>".
 * Nada além disso vira <img>: nem endereço externo, nem esquemas como javascript: ou data:.
 */
export function isAvatarPath(value) {
  return typeof value === "string" && /^\/api\/avatars\/[A-Za-z0-9_-]{8,64}$/.test(value);
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

/** Retrospectiva de uma pessoa. Sem o ano, o servidor escolhe o último ano em que ela tem registros. */
export const retrospectivePath = (username, year) =>
  `${userPath(username)}/retrospectiva${year === undefined || year === null ? "" : `/${year}`}`;

/** A imagem de compartilhamento (PNG 1200 x 630) da retrospectiva, desenhada pelo servidor. */
export const retrospectiveImagePath = (username, year) =>
  `/api/share/retrospective/${encodeURIComponent(username)}/${year}.png`;

/** O ano na URL precisa ter quatro dígitos; o servidor decide quais anos têm retrospectiva. */
export const isYearParam = (value) => typeof value === "string" && /^\d{4}$/.test(value);

/** "no mesmo dia", "1 dia", "19 dias". */
export function daysText(days) {
  if (days === null || days === undefined) return "";
  if (days === 0) return "no mesmo dia";
  return plural(days, "dia", "dias");
}

// Meses e notas usados nos gráficos (perfil e retrospectiva).
export const MONTH_LETTERS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
export const MONTH_NAMES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
// Distribuição de notas: 11 barras (0 a 10). A barra n reúne a nota n e a n,5; a barra 10 é só a nota 10.
export const RATING_LABELS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"];
export const RATING_SR = RATING_LABELS.map((n) => (n === "10" ? "Nota 10" : `Notas de ${n} a ${n},5`));

/** Remove chaves vazias de um objeto de parâmetros de busca. */
export function cleanParams(params) {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== "" && v !== false),
  );
}
