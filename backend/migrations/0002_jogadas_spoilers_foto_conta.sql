-- DiscPlayer — migração 0002: várias jogadas, aviso de spoilers, foto enviada e exclusão de conta.
--
--  * `reviews.has_spoilers`: a pessoa marca que o texto da review conta partes da
--    história. A API devolve o texto normalmente; quem exibe esconde atrás de um aviso.
--    O feed e a busca nunca mostram trechos de reviews com spoilers.
--  * `playthroughs`: jogadas ANTERIORES de um jogo. A entrada do diário
--    (`library_entries`) continua sendo a jogada atual, uma por usuário e jogo;
--    "jogar de novo" copia o status e as datas dela para cá e recomeça a entrada.
--    A nota segue única por jogo (vive só em `reviews.rating`).
--  * `activities.is_replay`: marca a atividade "começou a jogar" que veio de um recomeço.
--  * `user_avatars`: a foto do perfil enviada pela pessoa, já reprocessada pelo servidor
--    (WebP quadrado, sem metadados). Fica fora de `users` para que `SELECT * FROM users`
--    (feito a cada requisição autenticada) não carregue a imagem. `users.avatar_url`
--    passa a guardar o endereço interno da foto (/api/avatars/<token>) e é mantido
--    junto com esta tabela, na mesma transação.
--  * `users.session_key`: valor aleatório por conta, copiado para o cookie de sessão.
--    O SQLite reaproveita o maior id depois que uma conta é excluída; sem esta chave,
--    um cookie antigo da conta excluída passaria a valer para a próxima conta criada.

ALTER TABLE reviews ADD COLUMN has_spoilers INTEGER NOT NULL DEFAULT 0 CHECK (has_spoilers IN (0, 1));

CREATE TABLE playthroughs (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id      INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    status       TEXT NOT NULL CHECK (status IN ('zerado', 'abandonado', 'pausado')),
    started_at   TEXT,
    completed_at TEXT,
    created_at   TEXT NOT NULL,
    CHECK (started_at IS NULL OR completed_at IS NULL OR completed_at >= started_at)
);
CREATE INDEX ix_playthroughs_user_game ON playthroughs (user_id, game_id, id);
CREATE INDEX ix_playthroughs_game      ON playthroughs (game_id);

ALTER TABLE activities ADD COLUMN is_replay INTEGER NOT NULL DEFAULT 0 CHECK (is_replay IN (0, 1));

CREATE TABLE user_avatars (
    user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    token      TEXT NOT NULL UNIQUE,
    data       BLOB NOT NULL CHECK (length(data) BETWEEN 1 AND 262144),
    updated_at TEXT NOT NULL
);

-- A foto agora é um arquivo enviado, não um link: endereços externos antigos deixam de valer.
UPDATE users SET avatar_url = NULL WHERE avatar_url IS NOT NULL;

ALTER TABLE users ADD COLUMN session_key TEXT;
UPDATE users SET session_key = lower(hex(randomblob(16))) WHERE session_key IS NULL;
