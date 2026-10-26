# Como o DiscPlayer funciona por dentro

As funcionalidades em detalhe, a stack, a estrutura de pastas, o banco de dados, a API, a segurança e as decisões de produto e de engenharia por trás do projeto.

[← Voltar ao README](../README.md)

## Funcionalidades em detalhe

- **Início** com a atividade real da comunidade (últimos registros, reviews, listas, jogos mais bem avaliados). Quem ainda não entrou vê uma prateleira com jogos em alta ao lado da apresentação e a legenda do disco; quem está logado vê "Jogando agora" (com a data de início e há quantos dias joga), "Na sua fila" (os jogos marcados como *Quero jogar*), as abas "Todos" e "Quem eu sigo" e uma seção "Descobrir" com *Em alta* e *Lançamentos recentes*.
- **Catálogo** com busca por nome, filtros de gênero, plataforma e ano, ordenação e paginação. Os filtros ficam na URL, então dá para compartilhar e recarregar.
- **Página do jogo** com ficha técnica da RAWG e, separado e rotulado, o **resumo da comunidade DiscPlayer** (média e distribuição das notas dadas aqui). A nota agregada da RAWG aparece em outro bloco, com a origem indicada: as duas nunca se misturam.
- **Contas**: cadastro, login, logout, sessão persistente por cookie, edição de perfil (nome de exibição, bio e **foto enviada como imagem**, que o servidor valida, recorta e reduz) e **exclusão da conta** com confirmação por senha.
- **Diário pessoal** com cinco status — *Quero jogar*, *Jogando*, *Zerado*, *Abandonado*, *Pausado* —, datas de início e término, favoritos e histórico de mudanças. **Jogar de novo**: a jogada atual vai para o histórico do jogo e outra começa, sem perder a anterior.
- **Reviews e notas** de 0 a 10 em passos de 0,5, com texto opcional. Só a pessoa autora edita ou apaga; qualquer pessoa logada pode curtir (uma vez por review). Quem escreve pode marcar **spoilers**: o texto fica escondido atrás de um aviso e o trecho nunca aparece no feed nem na busca.
- **Listas** personalizadas, públicas ou privadas, com reordenação, descrição e capa composta pelos primeiros jogos.
- **Perfis públicos** com estatísticas calculadas dos registros reais (jogos por status, nota média, distribuição das notas, zeradas em cada mês do ano, contando as jogadas anteriores), diário, reviews, listas, atividade, seguidores e quem a pessoa segue.
- **Social**: seguir e deixar de seguir (sem seguir a si mesmo), curtir reviews, feed de quem você segue.
- **Retrospectiva do ano** (`/u/<usuario>/retrospectiva/<ano>`): jogos zerados (contando as jogadas anteriores), começados, abandonados e jogados de novo; zerados por mês; o jogo do ano; ritmo (mais rápido, mais longo e média); notas dadas; curtidas, novos seguidores e listas públicas. Tudo calculado dos registros reais, com um seletor entre os anos que têm dados, um botão **Compartilhar** (menu do aparelho ou cópia do endereço) e uma imagem pronta para baixar.
- **Prévia de links**: ao colar o endereço de um jogo, perfil, lista pública ou retrospectiva no WhatsApp, Discord, LinkedIn e similares, aparecem título, descrição e imagem (a capa do jogo ou um cartão desenhado pelo servidor). Lista privada e endereço inexistente mostram só a prévia padrão do site, e um jogo que o servidor ainda não conhece (ninguém o registrou e a página dele não foi aberta) também.
- **Busca global** no cabeçalho (com debounce e navegação por teclado) e página de resultados: jogos, jogadores, listas e reviews.
- **Interface responsiva e acessível**: navegação por teclado, foco gerenciado entre páginas, rótulos ARIA, tabelas alternativas para gráficos, respeito a `prefers-reduced-motion`.

## Stack

| Camada | Tecnologia |
| --- | --- |
| Front-end | React 19 + Vite 7, HTML5, CSS3 (variáveis CSS, sem framework de UI), JavaScript. Roteador próprio sobre a History API |
| Back-end | Python 3.11+ e Flask 3.1 (API REST, blueprints) |
| Banco | SQLite com SQL puro (módulo `sqlite3`), migrações em arquivos `.sql` |
| Dados de jogos | API da RAWG, sempre intermediada pelo back-end |
| Servidor de produção | waitress (funciona em Windows, macOS e Linux) |
| Testes | pytest (back-end), `node:test` (front-end), Playwright + pytest (ponta a ponta, opcional) |

## Estrutura do projeto

```
DiscPlayer/
├── backend/
│   ├── app/
│   │   ├── __init__.py          # create_app (fábrica da aplicação)
│   │   ├── config.py            # configuração lida do ambiente / .env
│   │   ├── db.py                # conexão SQLite, migrações, comando init-db
│   │   ├── security.py          # CSRF, checagem de Origin, CORS, limite de requisições, cabeçalhos
│   │   ├── errors.py            # formato único de erro da API
│   │   ├── auth/                # senhas (scrypt), sessão, decoradores
│   │   ├── routes/              # blueprints: auth, avatars, games, library, reviews, lists, users, feed, search, share, health, spa
│   │   ├── services/            # regras de negócio e SQL; rawg.py é o cliente da RAWG (com cache)
│   │   │                        #   retrospective.py (contas do ano), previews.py (prévia de links), cards.py (imagens PNG)
│   │   └── utils/               # validação, cache TTL, escape de LIKE
│   ├── migrations/              # 0001_initial.sql, 0002_jogadas_spoilers_foto_conta.sql
│   ├── tests/                   # pytest (RAWG simulada)
│   ├── wsgi.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/  pages/  layouts/  context/  hooks/  router/  services/  utils/
│   │   ├── styles/              # tokens.css (cores, tipografia, espaços), base, layout, components, pages
│   │   └── assets/fonts/        # fontes hospedadas junto do site
│   ├── tests/                   # testes do front-end
│   ├── public/favicon.svg
│   ├── index.html  vite.config.js  package.json
├── e2e/                         # testes de navegador (opcional)
├── deploy/pythonanywhere_wsgi.py  # modelo de arquivo WSGI para hospedar de graça
├── docs/hospedagem-pythonanywhere.md
├── .gitignore
└── README.md
```

## Banco de dados

SQLite com `PRAGMA foreign_keys=ON`, modo WAL e `busy_timeout`. As migrações ficam em `backend/migrations/NNNN_nome.sql` e são aplicadas em ordem, cada uma numa transação, registradas na tabela `schema_migrations`. Para evoluir o esquema, crie `0003_algo.sql`; nunca edite uma migração já aplicada. A `0002` não perde dados de quem já usava o app, com uma exceção deliberada: **fotos de perfil que eram links deixam de existir** (agora a foto é um arquivo enviado), e cada pessoa volta às iniciais até enviar a sua. A mesma migração cria a `session_key` de cada conta, e por isso **quem estava logado antes da atualização precisa entrar de novo uma vez** (os cookies antigos não têm a chave).

| Tabela | Conteúdo |
| --- | --- |
| `users` | Contas. `username` e `email` únicos (sem diferenciar maiúsculas), senha só como hash; `session_key` é uma chave por conta, copiada para o cookie de sessão (veja [Segurança](#segurança)) |
| `user_avatars` | A foto de perfil já reprocessada (WebP quadrado, no máximo 256 KB, em geral uns 15 KB), guardada no próprio SQLite. `users.avatar_url` aponta para ela |
| `games` | Cópia local mínima de cada jogo usado pela comunidade (id da RAWG, nome, capa...), para que o diário continue funcionando se a RAWG falhar |
| `library_entries` | Diário: um registro por pessoa e jogo (a jogada **atual**), com status, datas e favorito |
| `playthroughs` | Jogadas **anteriores** do mesmo jogo (status e datas de cada uma). "Jogar de novo" copia a jogada atual para cá e recomeça a entrada |
| `reviews` | A nota, o texto e o aviso de spoilers (`has_spoilers`). **A nota mora só aqui**: o diário não guarda nota própria, então nunca há duas notas diferentes para o mesmo jogo, mesmo jogando várias vezes |
| `review_likes` | Curtidas (única por pessoa e review) |
| `lists`, `list_games` | Listas e seus jogos, com posição |
| `follows` | Quem segue quem (sem auto-seguir, sem duplicata) |
| `activities` | Histórico do diário (mudanças de status, recomeços, reviews, listas) que alimenta perfis e feeds |

Chaves estrangeiras com `ON DELETE CASCADE` onde faz sentido e índices nas colunas de filtro e ordenação. Apagar uma entrada do diário **não** apaga a review do jogo (mas apaga as jogadas anteriores dela). Excluir uma conta apaga tudo o que aponta para ela, em cascata, numa única transação.

## API

Respostas em JSON. Erros sempre no formato `{"error": {"code": "...", "message": "...", "fields": {...}}}`, com mensagens em português. Rotas de escrita exigem sessão e o cabeçalho `X-CSRF-Token` (o valor vem de `GET /api/auth/me`).

| Grupo | Rotas |
| --- | --- |
| Conta | `GET /api/auth/me`, `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `PATCH /api/auth/me` (nome e bio), `POST`/`DELETE /api/auth/me/avatar` (foto: envio `multipart/form-data` com o campo `file`, ou remoção), `DELETE /api/auth/me` (exclui a conta; exige a senha no corpo), `GET /api/avatars/<código>` (entrega a foto) |
| Jogos (RAWG) | `GET /api/games` (busca, filtros, ordem, página), `/api/games/featured`, `/api/games/top-rated` (só jogos com notas de pelo menos 3 pessoas; a resposta traz `min_notes`), `/api/games/<id>`, `/api/genres`, `/api/platforms` |
| Reviews | `GET /api/reviews` (recentes), `GET /api/games/<id>/reviews`, `POST /api/games/<id>/reviews` (aceita `has_spoilers`), `GET`/`PATCH`/`DELETE /api/reviews/<id>`, `PUT`/`DELETE /api/reviews/<id>/like` |
| Diário | `GET /api/library`, `PUT`/`DELETE /api/library/<id_do_jogo>` (o `PUT` aceita `today`, a data local de quem usa o site, usada ao preencher início e término automaticamente), `POST /api/library/<id_do_jogo>/replay` (jogar de novo), `DELETE /api/library/<id_do_jogo>/playthroughs/<id>` (exclui uma jogada anterior) |
| Listas | `GET`/`POST /api/lists`, `GET /api/me/lists`, `GET`/`PATCH`/`DELETE /api/lists/<id>`, `POST /api/lists/<id>/games`, `DELETE /api/lists/<id>/games/<jogo>`, `PUT /api/lists/<id>/order` |
| Pessoas | `GET /api/users/<usuario>` e `/library`, `/reviews`, `/lists`, `/activity`, `/followers`, `/following`; `PUT`/`DELETE /api/users/<usuario>/follow` |
| Retrospectiva | `GET /api/users/<usuario>/retrospective` (o último ano com registros) e `GET /api/users/<usuario>/retrospective/<ano>` (de 2000 até o ano seguinte ao atual; fora disso, 404). Pública, só com dados públicos |
| Imagens de compartilhamento | `GET /api/share/default.png`, `/api/share/profile/<usuario>.png` e `/api/share/retrospective/<usuario>/<ano>.png`: PNG de 1200 x 630, públicas e com cache de 10 minutos. A da retrospectiva responde 404 para um ano sem registros |
| Feed e busca | `GET /api/activity`, `GET /api/feed`, `GET /api/search?q=` |
| Saúde | `GET /api/health` |

## Segurança

- **Senhas** com hash `scrypt` e sal individual; mínimo de 8 caracteres, máximo de 128, e rejeição de senhas comuns. A mensagem de login incorreto não revela se o e-mail existe.
- **Sessão** em cookie assinado `HttpOnly`, `SameSite=Lax` (e `Secure` em produção), com validade de 30 dias. Nada sensível vai para `localStorage` ou `sessionStorage`.
- **CSRF**: token por sessão enviado em `X-CSRF-Token` e comparado em tempo constante; além disso, o cabeçalho `Origin` é validado.
- **CORS** só para origens listadas; sem `*`.
- **SQL injection**: todas as consultas usam parâmetros (`?`). Os curingas de `LIKE` são escapados.
- **XSS**: o React escapa texto por padrão; nunca usamos `dangerouslySetInnerHTML`. A página é servida com Content-Security-Policy restritiva (`script-src 'self'`; imagens só do próprio site, da RAWG em https e `blob:`, que é a prévia da foto escolhida, criada pelo próprio navegador), `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'`.
- **Autorização**: cada rota de escrita confere se o recurso é da pessoa logada. Listas privadas respondem como "não encontrada" para outras pessoas.
- **Validação** sempre no servidor (e repetida no navegador só para dar feedback rápido): tamanho de textos, faixa e passo da nota, status permitidos, nomes de usuário e o envio da foto (abaixo).
- **Foto enviada**: o arquivo nunca é guardado nem servido como veio. O servidor identifica o formato pelo **conteúdo** (JPG, PNG ou WebP; o nome e o tipo declarados pelo navegador são ignorados), recusa imagens com mais de 25 megapixels antes de decodificá-las (bombas de descompressão) e com menos de 64 px, aplica a rotação do EXIF, recorta um quadrado central e **grava uma imagem nova em WebP**: localização, modelo da câmera e qualquer dado escondido no arquivo original não sobrevivem. O limite de 5 MB vale só nessa rota; todas as outras continuam com 64 KB. A foto é entregue com um código aleatório que muda a cada troca (cache eterno seguro), `nosniff` e uma política que impede qualquer execução se alguém abrir o endereço direto.
- **Exclusão de conta**: exige a senha de novo (um cookie roubado não basta), tem limite de tentativas e apaga tudo numa transação. Como o SQLite reaproveita o maior id depois de uma exclusão, cada conta tem uma `session_key` aleatória copiada para o cookie: o cookie de uma conta excluída **nunca** passa a valer para a próxima conta criada com o mesmo id (há teste para isso).
- **Spoilers**: texto de review marcada com spoilers não entra em trechos de feed nem na busca (a busca nem o considera), e o navegador só coloca o texto na página depois do clique.
- **Limite de requisições** por IP em login, cadastro, busca, catálogo, escritas, envio de foto, exclusão de conta, retrospectiva, imagens de compartilhamento e prévias de links (600 por minuto por IP; se o limite das prévias estoura, a página abre normalmente com a prévia padrão).
- **Prévia de links**: o servidor escreve título, descrição e imagem no `index.html` de cada endereço, e **todo texto vindo de pessoas (nome, bio, título de lista ou de jogo) é escapado** antes de entrar no HTML. Só entram dados que já são públicos: nenhuma lista privada, e-mail ou texto de review; quem pede o endereço de uma lista privada recebe a prévia padrão, **inclusive a própria dona** (o robô não tem cookie, e o comportamento é o mesmo para todos). A prévia de um jogo usa só a cópia que o servidor já guarda (o diário ou o cache da RAWG, preenchido quando alguém abre a página do jogo) e **nunca chama a RAWG**: um robô que pede milhares de endereços não gasta a cota da chave. Capas só são usadas se forem `https`. Se montar a prévia falhar por qualquer motivo, a página abre com a prévia padrão. Os links absolutos usam `PUBLIC_URL` (ou o endereço da requisição quando a variável está vazia), então um cabeçalho `Host` forjado não vira link na página quando `PUBLIC_URL` está definida.
- **Respostas públicas não carregam cookie.** A sessão é renovada a cada requisição de quem está logado; numa resposta `Cache-Control: public` (foto de perfil, imagens de compartilhamento) isso faria um proxy ou CDN guardar o `Set-Cookie` de uma pessoa e entregá-lo a outras. Essas respostas agora saem sem o cookie (há teste para a foto e para as imagens).
- **Chave da RAWG** só existe no servidor. O navegador nunca a vê, e erros da RAWG são traduzidos antes de chegar à tela (a exceção de rede não é registrada em log porque costuma conter a URL com a chave).
- **Segredos fora do Git**: `.env`, `instance/` e bancos estão no `.gitignore`.

## Decisões de produto e design

- **Uma nota por pessoa e jogo**, guardada na review. A média "DiscPlayer" é calculada só com essas notas e sempre aparece junto da contagem de avaliações; a média da RAWG é outro número, em outro bloco, com a fonte à vista.
- **O disco** é o motivo visual do projeto. O logotipo, o status do jogo e a nota usam a mesma geometria: um disco dividido em quartos. Cada quarto preenchido vale 0,5 ponto de nota (cinco discos = 10) ou um quarto do caminho no jogo (*Jogando* = 1/4, *Pausado* = 2/4, *Zerado* = completo, *Quero jogar* = tracejado, *Abandonado* = riscado).
- **Visual**: fundo grafite neutro, superfícies sutis, texto de alto contraste, tipografia própria (TeX Gyre Adventor nos títulos e Lora no texto, ambas hospedadas junto do site) e **uma única cor de destaque**, o amarelo-marcador, usada só para o que está "preenchido". Tudo parametrizado em variáveis CSS (`frontend/src/styles/tokens.css`).
- **Estados vazios que convidam**: o site novo e vazio mostra como começar, não números inventados.
- **Falhas da RAWG não derrubam o site**: há cache com validade, uma cópia local dos jogos já usados pela comunidade e mensagens que explicam o que faltou, com botão "Tentar de novo".

## Decisões técnicas

- **Flask com `sqlite3` e SQL puro, sem ORM.** As consultas são explícitas e parametrizadas, fáceis de auditar. As migrações são arquivos `.sql` numerados, aplicados em transação e registrados em `schema_migrations`; as escritas usam `BEGIN IMMEDIATE` para não disputar o banco.
- **Sessão em cookie assinado e `HttpOnly` + CSRF por token sincronizado, em vez de JWT no `localStorage`.** Nada sensível fica ao alcance do JavaScript da página. O token CSRF vem de `GET /api/auth/me`, é comparado em tempo constante e o cabeçalho `Origin` também é conferido.
- **"Jogar de novo" arquiva, não duplica.** A entrada do diário continua sendo a jogada atual (uma por pessoa e jogo, então status, favoritos, listas e telas existentes seguem iguais); recomeçar copia status e datas para `playthroughs` e reinicia a entrada em "Jogando". Só vale para jogos zerados, abandonados ou pausados, e a estatística "zeradas no ano" soma as jogadas atuais e as anteriores, então recomeçar um jogo não apaga a conclusão que já aconteceu. A nota continua única por jogo.
- **Foto no SQLite, não em arquivos.** A imagem reprocessada (uns 15 KB) fica numa tabela própria: não há pasta de uploads para configurar, perder ou deixar sem backup, e um backup do banco leva as fotos junto. Em hospedagens de disco efêmero isso também funciona, porque o banco é o único estado.
- **A nota mora só em `reviews.rating`.** O diário não guarda nota, então nunca existem duas notas divergentes para o mesmo jogo.
- **Cópia local mínima dos jogos, criada sob demanda.** Diário, listas e perfis continuam funcionando se a RAWG cair. A RAWG só é acessada pelo back-end (a chave nunca chega ao navegador), com cache com validade e cópia expirada servida em caso de falha.
- **Datas de calendário no fuso de quem joga.** O servidor trabalha em UTC, mas quem marca "Jogando" às 22h no Brasil já está no "amanhã" de UTC. O navegador envia o seu "hoje" (`today`) e o servidor só o aceita se estiver a no máximo um dia de UTC, o que cobre todos os fusos e impede forjar datas distantes.
- **Roteador próprio sobre a History API**, em vez de uma biblioteca: o app tem poucas rotas e o roteador cobre o que ele precisa (parâmetros de rota e de busca, links ativos, redirecionamento) sem dependência extra, e o foco e o título ao trocar de página ficam no layout.
- **CSS próprio com variáveis (tokens) e fontes hospedadas junto do site.** Sem framework de UI e sem scripts, estilos ou fontes de terceiros (só as capas vêm da CDN da RAWG): a política de segurança do servidor (`script-src 'self'`) vale para a página inteira.
- **Ranking com mínimo de notas.** "Mais bem avaliados" só lista jogos com notas de pelo menos três pessoas diferentes (há uma nota por pessoa e jogo): um 10 dado por uma única pessoa não faz de um jogo o melhor da comunidade. Enquanto nenhum jogo chega a três notas, a página explica a regra em vez de mostrar um ranking de uma nota só.
- **Imagem de fundo da página do jogo.** A imagem que a RAWG envia para o jogo aparece bem apagada atrás do topo da página, sem competir com o texto, escondida dos leitores de tela e sem capturar cliques; se não carregar, a página fica como antes.
- **Prévia de links feita no servidor.** Os robôs que geram a prévia não executam JavaScript, então um `<meta>` colocado pelo React nunca seria visto. O Flask, que já entrega o `index.html` compilado, troca o título e a descrição e acrescenta as tags Open Graph e Twitter conforme o endereço. Isso só acontece quando o Flask serve o site (o build, em produção); no `npm run dev` o Vite entrega o HTML e a prévia não aparece.
- **Imagens de compartilhamento desenhadas com o Pillow**, que o projeto já usa nas fotos de perfil: PNG 1200 x 630 desenhado em dobro e reduzido (bordas suaves), com as mesmas cores e fontes do site. O cache fica na memória, com chave calculada **sobre os dados desenhados** (e a foto): mudar o perfil gera uma imagem nova sem esperar o cache vencer, e uma lista privada nunca influencia a chave. Antes de desenhar, o servidor confere se as fontes embutidas têm cada caractere (emoji, outros alfabetos e até letras latinas raras ficam de fora): nome sem cobertura vira o `@usuario` e a bio é omitida, em vez de sair com quadradinhos. Palavras maiores que a linha são cortadas com reticências, então nada ultrapassa a borda da imagem.
- **Retrospectiva calculada, nunca estimada.** Cada número vem de uma consulta aos registros: zerados pela data de término (jogada atual e anteriores, então zerar duas vezes no ano conta duas), começados pela data de início, abandonados e recomeços pelo histórico do diário, notas e curtidas pela data em que aconteceram. O **jogo do ano** é o zerado do ano com a maior nota, acima de zero (empate: o zerado mais recentemente; sem nenhuma nota, não há jogo do ano) e o **ritmo** só aparece com pelo menos dois zerados que tenham as duas datas. Sem gêneros nem horas jogadas, porque o app não guarda esses dados.
- **Testes que não dependem de rede.** O back-end usa uma RAWG simulada, e o teste de navegador sobe o Flask real com um servidor RAWG fictício. Os testes de mutação feitos durante o desenvolvimento (quebrar o CSRF, a privacidade de listas, o passo da nota, a data local, a validação das fotos, o vazamento de spoilers, a regra de jogar de novo, a chave de sessão, o vazamento de listas privadas nas prévias, o escape do HTML, o fim do ano nas contas da retrospectiva, cada fonte de dados da lista de anos, o ano mínimo, os limites de tamanho e de requisições das prévias e das imagens, a regra de nunca chamar a RAWG numa prévia, a conferência de caracteres e o texto estourando a borda dos cartões, o cookie em respostas públicas, o mínimo de notas do ranking, a colagem de capas fora da caixa e as colunas da retrospectiva e do perfil de propósito) confirmaram que a suíte pega essas regressões.
