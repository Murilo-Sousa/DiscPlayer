-- DiscPlayer — esquema inicial (SQLite).
--
-- Decisões de modelagem em relação ao esboço do projeto:
--  * A nota de um jogo vive somente em `reviews.rating` (fonte única). Uma
--    "avaliação sem texto" é uma review com `body` nulo. Assim a nota do diário
--    e a nota da review nunca divergem.
--  * `activities` registra o histórico do diário (mudanças de status, reviews
--    publicadas, listas criadas). Várias conclusões do mesmo jogo viram várias
--    atividades, sem duplicar a entrada principal em `library_entries`.
--  * Datas e horários são TEXT em ISO 8601 (UTC), que ordenam corretamente.
--  * Usuário e e-mail são únicos sem diferenciar maiúsculas (COLLATE NOCASE).

CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE
                  CHECK (length(username) BETWEEN 3 AND 24),
    display_name  TEXT NOT NULL CHECK (length(display_name) BETWEEN 1 AND 50),
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK (length(email) <= 254),
    password_hash TEXT NOT NULL,
    bio           TEXT CHECK (bio IS NULL OR length(bio) <= 280),
    avatar_url    TEXT CHECK (avatar_url IS NULL OR length(avatar_url) <= 500),
    created_at    TEXT NOT NULL
);

-- Cópia mínima dos metadados da RAWG, criada sob demanda quando um jogo
-- passa a ser referenciado por registros pessoais.
CREATE TABLE games (
    id           INTEGER PRIMARY KEY,
    rawg_id      INTEGER NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    slug         TEXT NOT NULL,
    cover_url    TEXT,
    release_date TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE library_entries (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id      INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    status       TEXT NOT NULL
                 CHECK (status IN ('quero_jogar', 'jogando', 'zerado', 'abandonado', 'pausado')),
    is_favorite  INTEGER NOT NULL DEFAULT 0 CHECK (is_favorite IN (0, 1)),
    started_at   TEXT,
    completed_at TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (user_id, game_id),
    CHECK (started_at IS NULL OR completed_at IS NULL OR completed_at >= started_at)
);
CREATE INDEX ix_library_user_status   ON library_entries (user_id, status);
CREATE INDEX ix_library_user_updated  ON library_entries (user_id, updated_at DESC);
CREATE INDEX ix_library_user_favorite ON library_entries (user_id, updated_at DESC) WHERE is_favorite = 1;
CREATE INDEX ix_library_game          ON library_entries (game_id);

CREATE TABLE reviews (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id    INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    rating     REAL NOT NULL
               CHECK (rating >= 0 AND rating <= 10 AND rating * 2 = CAST(rating * 2 AS INTEGER)),
    body       TEXT CHECK (body IS NULL OR length(body) <= 5000),
    created_at TEXT NOT NULL,
    updated_at TEXT,            -- nulo até a primeira edição
    UNIQUE (user_id, game_id)
);
CREATE INDEX ix_reviews_game_created ON reviews (game_id, created_at DESC);
CREATE INDEX ix_reviews_user_created ON reviews (user_id, created_at DESC);
CREATE INDEX ix_reviews_created      ON reviews (created_at DESC);

CREATE TABLE review_likes (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    review_id  INTEGER NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, review_id)
);
CREATE INDEX ix_review_likes_review ON review_likes (review_id);

CREATE TABLE lists (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 80),
    description TEXT CHECK (description IS NULL OR length(description) <= 500),
    is_public   INTEGER NOT NULL DEFAULT 1 CHECK (is_public IN (0, 1)),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX ix_lists_user   ON lists (user_id, updated_at DESC);
CREATE INDEX ix_lists_public ON lists (updated_at DESC) WHERE is_public = 1;

CREATE TABLE list_games (
    id       INTEGER PRIMARY KEY,
    list_id  INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
    game_id  INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position >= 0),
    added_at TEXT NOT NULL,
    UNIQUE (list_id, game_id)
);
-- Não é UNIQUE de propósito: a reordenação reescreve as posições em lote.
CREATE INDEX ix_list_games_order ON list_games (list_id, position);
CREATE INDEX ix_list_games_game  ON list_games (game_id);

CREATE TABLE follows (
    id          INTEGER PRIMARY KEY,
    follower_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followed_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    UNIQUE (follower_id, followed_id),
    CHECK (follower_id <> followed_id)
);
CREATE INDEX ix_follows_followed ON follows (followed_id);

CREATE TABLE activities (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type       TEXT NOT NULL CHECK (type IN ('logged', 'reviewed', 'list_created')),
    game_id    INTEGER REFERENCES games(id) ON DELETE CASCADE,
    status     TEXT CHECK (status IS NULL OR status IN
                   ('quero_jogar', 'jogando', 'zerado', 'abandonado', 'pausado')),
    review_id  INTEGER REFERENCES reviews(id) ON DELETE CASCADE,
    list_id    INTEGER REFERENCES lists(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    CHECK (
        (type = 'logged'       AND game_id IS NOT NULL AND status IS NOT NULL)
     OR (type = 'reviewed'     AND game_id IS NOT NULL AND review_id IS NOT NULL)
     OR (type = 'list_created' AND list_id IS NOT NULL)
    )
);
CREATE INDEX ix_activities_user    ON activities (user_id, created_at DESC);
CREATE INDEX ix_activities_created ON activities (created_at DESC);
CREATE INDEX ix_activities_game    ON activities (game_id);
