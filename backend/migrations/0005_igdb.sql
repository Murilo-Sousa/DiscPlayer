-- DiscPlayer — migração 0005: da RAWG para o IGDB.
--
--  * `games.rawg_id` vira `games.igdb_id`: o número do jogo no serviço que fornece os dados.
--  * Os números da RAWG e os do IGDB não têm relação: o mesmo número é outro jogo (ou nenhum). Para um jogo guardado
--    antes da troca nunca virar, por engano, outro jogo, os números antigos passam a ser NEGATIVOS. Nada é apagado:
--    o diário, as reviews e as listas continuam mostrando o nome e a capa que já estavam guardados, mas a página
--    desses jogos deixa de abrir e eles nunca colidem com um jogo novo (os do IGDB são sempre positivos).
--  * Num banco novo não há linhas, então a atualização não faz nada.

ALTER TABLE games RENAME COLUMN rawg_id TO igdb_id;
UPDATE games SET igdb_id = -igdb_id WHERE igdb_id > 0;
