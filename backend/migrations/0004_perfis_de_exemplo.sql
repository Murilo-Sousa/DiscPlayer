-- DiscPlayer — migração 0004: perfis de exemplo.
--
--  * `users.is_demo`: 1 para as contas fictícias criadas por `python -m app.demo seed`, que servem para mostrar como
--    o site fica com atividade. Elas aparecem marcadas como "perfil de exemplo" nas telas, não fazem login (a senha
--    é aleatória e descartada) e saem todas de uma vez com `python -m app.demo remove`. Contas reais ficam em 0.

ALTER TABLE users ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1));
