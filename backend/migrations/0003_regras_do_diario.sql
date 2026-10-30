-- DiscPlayer — migração 0003: regras do diário (o que cada status permite).
--
--  * `library_entries.status_changed_at`: quando o status mudou pela última vez. O diário
--    mostrava "Largado em ..." com `updated_at`, que também muda ao favoritar ou editar datas.
--    Para os registros que já existem, vale a última atividade de "mudou de status" do jogo
--    (ou `updated_at`, se ela não existir).
--  * Dados antigos que as regras novas não aceitam:
--      - "Quero jogar" é um jogo que a pessoa ainda não começou: sem data de início, sem data
--        de término e sem favorito;
--      - só um jogo ZERADO tem data de término (nos demais status ela não significa nada).
--    As regras agora são impostas pela API; esta migração só deixa o que já estava salvo de
--    acordo com elas. Isso APAGA essas datas e o favorito da fila (sem cópia): é o único jeito de
--    uma data velha não voltar a valer quando o jogo mudar de status.
--  * O que a migração NÃO faz, de propósito: notas e reviews antigas não são tocadas (nem apagadas, nem
--    "corrigidas" para um status que ninguém informou), e as datas das jogadas anteriores (`playthroughs`)
--    ficam como estão. Uma nota antiga de um jogo que não está no diário (ou está na fila) continua
--    existindo e pode ser editada ou excluída; as regras novas só impedem criar outras assim.

ALTER TABLE library_entries ADD COLUMN status_changed_at TEXT;

UPDATE library_entries
   SET status_changed_at = COALESCE(
       (SELECT MAX(a.created_at) FROM activities a
         WHERE a.user_id = library_entries.user_id
           AND a.game_id = library_entries.game_id
           AND a.type = 'logged'),
       updated_at);

UPDATE library_entries
   SET started_at = NULL, completed_at = NULL, is_favorite = 0
 WHERE status = 'quero_jogar';

UPDATE library_entries SET completed_at = NULL WHERE status <> 'zerado' AND completed_at IS NOT NULL;

