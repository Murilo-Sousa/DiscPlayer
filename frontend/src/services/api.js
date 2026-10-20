// Funções da API REST do DiscPlayer. Cada uma devolve o JSON já decodificado.
import { localToday } from "../utils/format.js";
import { http } from "./http.js";

export const authApi = {
  me: (options) => http.get("/auth/me", options),
  register: (data) => http.post("/auth/register", data),
  login: (data) => http.post("/auth/login", data),
  logout: () => http.post("/auth/logout"),
  updateProfile: (data) => http.patch("/auth/me", data),
};

export const gamesApi = {
  catalog: (params, options) => http.get("/games", { ...options, params }),
  featured: (options) => http.get("/games/featured", options),
  topRated: (params, options) => http.get("/games/top-rated", { ...options, params }),
  genres: (options) => http.get("/genres", options),
  platforms: (options) => http.get("/platforms", options),
  detail: (rawgId, options) => http.get(`/games/${rawgId}`, options),
  reviews: (rawgId, params, options) => http.get(`/games/${rawgId}/reviews`, { ...options, params }),
};

export const libraryApi = {
  mine: (params, options) => http.get("/library", { ...options, params }),
  // `today` é a data local de quem usa o site: o servidor a usa ao preencher início/término automaticamente.
  save: (rawgId, data) => http.put(`/library/${rawgId}`, { today: localToday(), ...data }),
  remove: (rawgId) => http.delete(`/library/${rawgId}`),
};

export const reviewsApi = {
  recent: (params, options) => http.get("/reviews", { ...options, params }),
  create: (rawgId, data) => http.post(`/games/${rawgId}/reviews`, data),
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
