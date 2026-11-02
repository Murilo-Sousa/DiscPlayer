// Funções da API REST do DiscPlayer. Cada uma devolve o JSON já decodificado.
import { localToday } from "../utils/format.js";
import { http } from "./http.js";

export const authApi = {
  me: (options) => http.get("/auth/me", options),
  register: (data) => http.post("/auth/register", data),
  login: (data) => http.post("/auth/login", data),
  logout: () => http.post("/auth/logout"),
  updateProfile: (data) => http.patch("/auth/me", data),
  // A foto vai como arquivo (multipart): o servidor valida, recorta e reprocessa a imagem.
  uploadAvatar: (file) => {
    const form = new FormData();
    form.append("file", file);
    return http.post("/auth/me/avatar", form);
  },
  removeAvatar: () => http.delete("/auth/me/avatar"),
  // Exclui a conta e tudo o que é dela. Pede a senha de novo.
  deleteAccount: (password) => http.delete("/auth/me", { body: { password } }),
};

export const gamesApi = {
  catalog: (params, options) => http.get("/games", { ...options, params }),
  featured: (options) => http.get("/games/featured", options),
  topRated: (params, options) => http.get("/games/top-rated", { ...options, params }),
  genres: (options) => http.get("/genres", options),
  platforms: (options) => http.get("/platforms", options),
  detail: (rawgId, options) => http.get(`/games/${rawgId}`, options),
  // Mais jogos do primeiro gênero do jogo (sem ele). Se a RAWG falhar, vem uma lista vazia.
  related: (rawgId, options) => http.get(`/games/${rawgId}/related`, options),
  // Quem o usuário logado segue e já jogou o jogo (status, favorito e nota de cada pessoa).
  following: (rawgId, options) => http.get(`/games/${rawgId}/following`, options),
  reviews: (rawgId, params, options) => http.get(`/games/${rawgId}/reviews`, { ...options, params }),
};

export const libraryApi = {
  mine: (params, options) => http.get("/library", { ...options, params }),
  // Quais destes jogos já estão no diário de quem está logado, e com que status (para os cards).
  statuses: (rawgIds, options) => http.get("/library/status", { ...options, params: { ids: rawgIds.join(",") } }),
  // "Guardar na fila" a partir de um card: só cria. Se o jogo já estiver no diário, o servidor recusa (409) e não muda nada.
  queue: (rawgId) => http.put(`/library/${rawgId}`, { today: localToday(), status: "quero_jogar", create_only: true }),
  // `today` é a data local de quem usa o site: o servidor a usa ao preencher início/término automaticamente.
  save: (rawgId, data) => http.put(`/library/${rawgId}`, { today: localToday(), ...data }),
  // Se o jogo tem nota, a nota sai junto: o servidor só aceita isso com `withReview` (a pessoa já viu o aviso).
  remove: (rawgId, { withReview = false } = {}) =>
    http.delete(`/library/${rawgId}`, withReview ? { body: { with_review: true } } : undefined),
  // "Jogar de novo": a jogada atual vai para o histórico do jogo e começa outra (início em hoje, no fuso de quem usa).
  replay: (rawgId) => http.post(`/library/${rawgId}/replay`, { today: localToday() }),
  removePlaythrough: (rawgId, id) => http.delete(`/library/${rawgId}/playthroughs/${id}`),
};

export const reviewsApi = {
  recent: (params, options) => http.get("/reviews", { ...options, params }),
  // `today` é a data local de quem usa o site: o servidor a usa para saber se o jogo já saiu.
  create: (rawgId, data) => http.post(`/games/${rawgId}/reviews`, { today: localToday(), ...data }),
  update: (id, data) => http.patch(`/reviews/${id}`, data),
  remove: (id) => http.delete(`/reviews/${id}`),
  like: (id) => http.put(`/reviews/${id}/like`),
  unlike: (id) => http.delete(`/reviews/${id}/like`),
};

export const listsApi = {
  community: (params, options) => http.get("/lists", { ...options, params }),
  mine: (options) => http.get("/me/lists", options),
  get: (id, options) => http.get(`/lists/${id}`, options),
  create: (data) => http.post("/lists", data),
  update: (id, data) => http.patch(`/lists/${id}`, data),
  remove: (id) => http.delete(`/lists/${id}`),
  addGame: (id, rawgId) => http.post(`/lists/${id}/games`, { rawg_id: rawgId }),
  removeGame: (id, rawgId) => http.delete(`/lists/${id}/games/${rawgId}`),
  reorder: (id, rawgIds) => http.put(`/lists/${id}/order`, { rawg_ids: rawgIds }),
};

export const usersApi = {
  profile: (username, options) => http.get(`/users/${encodeURIComponent(username)}`, options),
  library: (username, params, options) =>
    http.get(`/users/${encodeURIComponent(username)}/library`, { ...options, params }),
  reviews: (username, params, options) =>
    http.get(`/users/${encodeURIComponent(username)}/reviews`, { ...options, params }),
  lists: (username, options) => http.get(`/users/${encodeURIComponent(username)}/lists`, options),
  activity: (username, params, options) =>
    http.get(`/users/${encodeURIComponent(username)}/activity`, { ...options, params }),
  followers: (username, params, options) =>
    http.get(`/users/${encodeURIComponent(username)}/followers`, { ...options, params }),
  following: (username, params, options) =>
    http.get(`/users/${encodeURIComponent(username)}/following`, { ...options, params }),
  // Sem `year`, o servidor responde com o último ano em que a pessoa tem registros.
  retrospective: (username, year, options) =>
    http.get(
      `/users/${encodeURIComponent(username)}/retrospective${year === undefined || year === null ? "" : `/${year}`}`,
      options,
    ),
  follow: (username) => http.put(`/users/${encodeURIComponent(username)}/follow`),
  unfollow: (username) => http.delete(`/users/${encodeURIComponent(username)}/follow`),
};

export const feedApi = {
  community: (params, options) => http.get("/activity", { ...options, params }),
  following: (params, options) => http.get("/feed", { ...options, params }),
};

export const searchApi = {
  search: (q, options) => http.get("/search", { ...options, params: { q } }),
};
