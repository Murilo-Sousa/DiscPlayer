# DiscPlayer

[![CI](https://github.com/Murilo-Sousa/discplayer/actions/workflows/ci.yml/badge.svg)](https://github.com/Murilo-Sousa/discplayer/actions/workflows/ci.yml)

Diário e comunidade de videogames, no espírito do Letterboxd: registre o que você joga, avalie de 0 a 10, escreva reviews, monte listas e acompanhe o que outras pessoas estão jogando.

Os dados dos jogos (nome, capa, gêneros, plataformas, datas, nota agregada) vêm da [RAWG](https://rawg.io). Todo o resto — contas, diário, notas, reviews, listas, seguidores, atividade — é da própria comunidade do DiscPlayer e fica no seu banco SQLite. Nada na tela é inventado: sem dados, o site mostra um estado vazio explicando como começar.

## Sumário

- [O que tem](#o-que-tem)
- [Stack](#stack)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Requisitos](#requisitos)
- [Passo a passo: rodando em desenvolvimento](#passo-a-passo-rodando-em-desenvolvimento)
- [Colocar o projeto no GitHub](#colocar-o-projeto-no-github)
- [Desenvolver sem chave da RAWG](#desenvolver-sem-chave-da-rawg)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Testes](#testes)
- [Rodando em produção](#rodando-em-produção)
- [Publicar de graça na internet (PythonAnywhere)](#publicar-de-graça-na-internet-pythonanywhere)
- [Banco de dados](#banco-de-dados)
- [API](#api)
- [Segurança](#segurança)
- [Decisões de produto e design](#decisões-de-produto-e-design)
- [Decisões técnicas](#decisões-técnicas)
- [Solução de problemas](#solução-de-problemas)
- [Limitações conhecidas](#limitações-conhecidas)
- [Próximos passos](#próximos-passos)
- [Créditos e licenças](#créditos-e-licenças)

## O que tem

- **Início** com a atividade real da comunidade (últimos registros, reviews, jogos mais bem avaliados). Para quem está logado, abas "Comunidade" e "Quem eu sigo" e a seção "Jogando agora".
- **Catálogo** com busca por nome, filtros de gênero, plataforma e ano, ordenação e paginação. Os filtros ficam na URL, então dá para compartilhar e recarregar.
- **Página do jogo** com ficha técnica da RAWG e, separado e rotulado, o **resumo da comunidade DiscPlayer** (média e distribuição das notas dadas aqui). A nota agregada da RAWG aparece em outro bloco, com a origem indicada: as duas nunca se misturam.
- **Contas**: cadastro, login, logout, sessão persistente por cookie, edição de perfil (nome de exibição, bio e foto por endereço https).
- **Diário pessoal** com cinco status — *Quero jogar*, *Jogando*, *Zerado*, *Abandonado*, *Pausado* —, datas de início e término, favoritos e histórico de mudanças.
- **Reviews e notas** de 0 a 10 em passos de 0,5, com texto opcional. Só a pessoa autora edita ou apaga; qualquer pessoa logada pode curtir (uma vez por review).
- **Listas** personalizadas, públicas ou privadas, com reordenação, descrição e capa composta pelos primeiros jogos.
- **Perfis públicos** com estatísticas calculadas dos registros reais (jogos por status, nota média, distribuição das notas, jogos zerados em cada mês do ano), diário, reviews, listas, atividade, seguidores e quem a pessoa segue.
- **Social**: seguir e deixar de seguir (sem seguir a si mesmo), curtir reviews, feed de quem você segue.
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
│   │   ├── routes/              # blueprints: auth, games, library, reviews, lists, users, feed, search, health, spa
│   │   ├── services/            # regras de negócio e SQL; rawg.py é o cliente da RAWG (com cache)
│   │   └── utils/               # validação, cache TTL, escape de LIKE
│   ├── migrations/0001_initial.sql
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

## Requisitos

- **Python 3.11 ou mais novo** (`python --version`)
- **Node.js 20.19 ou mais novo** com npm (`node --version`)
- Uma **chave da API da RAWG** (gratuita) — ou use o [servidor de dados fictícios](#desenvolver-sem-chave-da-rawg) enquanto não tiver uma

> **Windows: depois de instalar o Python ou o Node.js, feche o terminal e abra outro.** Terminais abertos antes da instalação não enxergam os programas novos e mostram erros como *"npm não é reconhecido como nome de cmdlet"*. Se o terminal estiver dentro de um editor (como o VS Code), feche o editor inteiro e abra de novo. Para conferir: `node --version` e `npm --version` devem mostrar números de versão.

### Como conseguir a chave da RAWG

1. Crie uma conta em <https://rawg.io/apidocs> e gere uma chave gratuita.
2. Guarde-a em `backend/.env` como `RAWG_API_KEY=...` (passo a passo abaixo).

A chave **nunca vai para o navegador**: só o back-end fala com a RAWG. O plano gratuito exige citar a RAWG como fonte — o rodapé do site já faz isso com link.

## Passo a passo: rodando em desenvolvimento

São dois processos, cada um no seu terminal: a API (porta 5000) e o front-end (porta 5173). Os dois precisam ficar abertos ao mesmo tempo.

**No Windows, os comandos mudam conforme o terminal.** Olhe o começo da linha para saber qual você está usando:

| Começo da linha | Terminal | Ativar o ambiente virtual | Copiar o `.env` |
| --- | --- | --- | --- |
| `PS C:\...>` | PowerShell | `.venv\Scripts\Activate.ps1` | `Copy-Item .env.example .env` |
| `C:\...>` | Prompt de Comando (cmd) | `.venv\Scripts\activate.bat` | `copy .env.example .env` |

### 1. Back-end (terminal 1)

Linux ou macOS:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Windows (PowerShell):

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Windows (Prompt de Comando):

```bat
cd backend
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
```

Quando o ambiente virtual está ativo, aparece `(.venv)` no começo da linha. Se o PowerShell responder *"a execução de scripts foi desabilitada neste sistema"* no `Activate.ps1`, rode `Set-ExecutionPolicy -Scope Process Bypass` (vale só para aquela janela, não muda nada permanente) e repita o comando. Outra saída é usar o Prompt de Comando.

Abra `backend/.env` e preencha `RAWG_API_KEY=` com a sua chave. Não é preciso mexer no resto para desenvolver.

Crie o banco e rode as migrações (o app também faz isso sozinho ao iniciar, a menos que `AUTO_MIGRATE=false`):

```bash
flask --app wsgi init-db
```

Suba a API:

```bash
flask --app wsgi run --debug
```

Confira em <http://127.0.0.1:5000/api/health> — deve responder `{"status":"ok", ...}`.

> **macOS:** a porta 5000 costuma estar ocupada pelo AirPlay Receiver. Use `flask --app wsgi run --debug --port 5001` e, no terminal do front-end, `VITE_BACKEND_URL=http://127.0.0.1:5001 npm run dev`.

### 2. Front-end (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

O `npm install` demora na primeira vez. Linhas `WARN` costumam ser inofensivas; `ERR!` não. Quando o `npm run dev` mostrar `Local: http://localhost:5173/`, o site está no ar.

> **PowerShell:** se aparecer *"npm.ps1 não pode ser carregado porque a execução de scripts foi desabilitada"*, rode `Set-ExecutionPolicy -Scope Process Bypass` e repita, ou use `npm.cmd install` e `npm.cmd run dev`.

Abra <http://localhost:5173>. O Vite repassa tudo que começa com `/api` para o Flask, então o navegador enxerga uma única origem: o cookie de sessão funciona sem configurar CORS.

Para apontar o proxy para outra porta ou máquina: `VITE_BACKEND_URL=http://127.0.0.1:5001 npm run dev` (no PowerShell: `$env:VITE_BACKEND_URL="http://127.0.0.1:5001"; npm run dev`).

### 3. Primeiros passos no site

1. Clique em **Criar conta** (usuário com 3 a 24 letras minúsculas, números ou `_`; senha com pelo menos 8 caracteres).
2. Abra um jogo pelo catálogo, marque um status, dê uma nota e escreva uma review.
3. Crie uma lista, abra seu diário e seu perfil público (`/u/seu-usuario`).
4. Para ver o lado social, crie uma segunda conta em outra janela anônima, siga a primeira e curta a review dela.

## Colocar o projeto no GitHub

O projeto já traz um `.gitignore` que impede o envio do seu `.env` (com a chave da RAWG), do `.venv`, do `node_modules` e do banco de dados. O passo a passo completo, para Windows (PowerShell e Prompt de Comando), com login pelo navegador, token e os avisos que costumam assustar, está na **Parte 1** de [docs/hospedagem-pythonanywhere.md](docs/hospedagem-pythonanywhere.md#parte-1--colocar-o-código-no-github). O resumo:

```bash
git init -b main
git add .
git commit -m "DiscPlayer: primeira versão"
git remote add origin https://github.com/SEU-USUARIO/discplayer.git
git push -u origin main
```

Antes do `git commit`, confira que nenhum arquivo sensível entrou (nada deve aparecer): no PowerShell, `git ls-files | Select-String "node_modules|\.venv|instance|\.db|\.env$"`; no Prompt de Comando, `git ls-files | findstr /R "node_modules \.venv instance \.db \.env$"`.

## Desenvolver sem chave da RAWG

O projeto inclui um servidor local que imita a RAWG com **dados fictícios** (jogos, gêneros e plataformas de mentira, sem imagens reais). Serve para desenvolver e testar a interface sem internet e sem chave. Não use isso como catálogo de verdade.

No terminal do back-end, com o ambiente virtual ativo:

```bash
# Terminal A: a "RAWG de mentira", na porta 8765
python -m tests.fake_rawg_server
```

```bash
# Terminal B: a API apontando para ela (Linux/macOS)
RAWG_BASE_URL=http://127.0.0.1:8765/api RAWG_API_KEY=qualquer-coisa flask --app wsgi run --debug
```

No PowerShell: `$env:RAWG_BASE_URL="http://127.0.0.1:8765/api"; $env:RAWG_API_KEY="qualquer-coisa"; flask --app wsgi run --debug`.

As capas apontam para `media.rawg.io`; sem acesso a essa URL, o site mostra o espaço reservado da capa, sem quebrar o layout.

## Variáveis de ambiente

Todas são lidas de `backend/.env` (modelo em `backend/.env.example`) ou do ambiente do sistema. O front-end só tem uma, usada apenas pelo `npm run dev`.

| Variável | Padrão | Para quê |
| --- | --- | --- |
| `RAWG_API_KEY` | vazio | Chave da RAWG. Sem ela, as rotas de catálogo respondem `503` com uma mensagem clara; o resto do site funciona |
| `APP_ENV` | `development` | `production` torna `SECRET_KEY` obrigatória e liga o cookie `Secure` |
| `SECRET_KEY` | gerada em dev | Assina o cookie de sessão (mínimo de 32 caracteres em produção) |
| `DATABASE_PATH` | `backend/instance/discplayer.db` | Caminho do arquivo SQLite |
| `AUTO_MIGRATE` | `true` | Aplica migrações pendentes ao iniciar |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Origens extras autorizadas a chamar a API |
| `COOKIE_SECURE` | `true` em produção | Cookie só por HTTPS. Use `false` para testar o build em `http://localhost` |
| `TRUSTED_PROXY_COUNT` | `0` | Quantos proxies reversos existem à frente do app (para ver o IP real) |
| `RATELIMIT_ENABLED` | `true` | Liga o limite de requisições por IP |
| `RAWG_BASE_URL` | `https://api.rawg.io/api` | Troque só para usar o servidor fictício |
| `VITE_BACKEND_URL` (front-end) | `http://127.0.0.1:5000` | Destino do proxy `/api` no `npm run dev` |

## Testes

### Back-end (pytest)

```bash
cd backend
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pytest
```

Os testes usam um banco temporário por teste e **uma RAWG simulada** (`tests/fake_rawg.py`): não gastam cota da API, não precisam de internet nem de chave. Cobrem autenticação e sessão, CSRF, diário, reviews, listas, social, busca, o cliente da RAWG (cache, falhas, dados incompletos), integridade do banco e cabeçalhos de segurança.

### Front-end

```bash
cd frontend
npm test
```

A suíte usa o executor nativo do Node (`node:test`) com esbuild (que já vem junto do Vite) para compilar JSX, e renderiza os componentes no servidor com `react-dom/server`. Cobre formatação, roteador, cliente HTTP (CSRF, repetição, erros de rede), componentes (nota em discos, escape de texto, rótulos de formulário, paginação, abas, histograma) e a proteção contra redirecionamento aberto no login. Não usa Vitest nem jsdom; não há testes de interação de componentes além dos de navegador, abaixo.

### Ponta a ponta no navegador (opcional)

Sobem o Flask de verdade, com banco temporário e a RAWG fictícia, e controlam um Chromium real: cadastro, status, nota, review, lista, diário, perfil, seguir, curtir, feed, privacidade de lista, validação e CSRF no servidor, teclado, celular sem rolagem horizontal e as datas automáticas do diário no fuso de quem joga e o comportamento com a RAWG fora do ar.

```bash
# 1. gere o front-end
cd frontend && npm run build && cd ..

# 2. instale as dependências do teste (no mesmo ambiente virtual do back-end)
cd e2e
pip install -r requirements.txt ../backend/requirements.txt
playwright install chromium

# 3. rode
pytest
```

Para testar uma pasta de build diferente: `E2E_DIST=/caminho/do/dist pytest`. Sem `frontend/dist`, os testes são pulados com uma mensagem explicando o motivo.

### Integração contínua

O workflow `.github/workflows/ci.yml` roda a cada push na `main` e em todo Pull Request: o back-end em Python 3.11 e 3.13, o front-end (`npm ci`, `npm test` e `npm run build`) e o teste de ponta a ponta com Chromium, usando o build recém-gerado. O resultado aparece na aba **Actions** do repositório e no selo no topo deste README.

## Rodando em produção

Em produção o Flask serve a API e o front-end compilado no mesmo endereço (sem CORS).

```bash
# 1. compile o front-end
cd frontend
npm ci            # ou npm install
npm run build     # gera frontend/dist

# 2. configure o back-end
cd ../backend
source .venv/bin/activate
pip install -r requirements.txt
export APP_ENV=production
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"   # guarde este valor!
export RAWG_API_KEY="sua-chave"
export DATABASE_PATH=/var/lib/discplayer/discplayer.db

# 3. suba com um servidor de verdade (não use `flask run`)
waitress-serve --listen=127.0.0.1:8000 --call wsgi:create_app
```

Orientações:

- Coloque um proxy reverso com **HTTPS** (Caddy, nginx...) na frente e defina `TRUSTED_PROXY_COUNT=1`. Sem HTTPS, o cookie `Secure` não é enviado e o login não funciona (para um teste local em HTTP, use `COOKIE_SECURE=false`).
- Se trocar o `SECRET_KEY`, todas as sessões abertas deixam de valer.
- Faça backup do arquivo SQLite (`sqlite3 discplayer.db ".backup copia.db"` copia com o banco em uso). O modo WAL cria arquivos `-wal` e `-shm` ao lado; eles fazem parte do banco enquanto o app roda.
- Use **um único processo** do app por banco (ver [Limitações](#limitações-conhecidas)).

## Publicar de graça na internet (PythonAnywhere)

O GitHub guarda o código, mas **não executa** o DiscPlayer (o GitHub Pages só serve sites estáticos, e aqui há uma API Python e um banco SQLite). Para outras pessoas abrirem um link, o projeto precisa rodar em um servidor.

A opção gratuita que melhor combina com este projeto é a **PythonAnywhere**: ela roda Flask, guarda os arquivos (o banco SQLite não se perde), oferece HTTPS e libera o acesso a `api.rawg.io` no plano gratuito. O guia completo, com o código no GitHub e o passo a passo do painel, está em **[docs/hospedagem-pythonanywhere.md](docs/hospedagem-pythonanywhere.md)**, e o modelo do arquivo WSGI está em `deploy/pythonanywhere_wsgi.py`.

Limites do plano gratuito (conferidos em 17/10/2026; confirme na PythonAnywhere): 1 web app com 1 processo, 512 MiB de disco, endereço `seunome.pythonanywhere.com` e **validade de 1 mês, que você precisa estender manualmente**. Outras hospedagens gratuitas populares (como o plano grátis do Render) usam disco temporário e **apagariam o banco** a cada reinício, por isso não servem para este projeto sem trocar o SQLite por um banco externo.

Antes de abrir o site ao público, leia os [Termos da RAWG](https://rawg.io/apidocs) (o plano gratuito é para projetos pessoais e sem fins comerciais, com link de volta para a RAWG) e as [Limitações conhecidas](#limitações-conhecidas).

## Banco de dados

SQLite com `PRAGMA foreign_keys=ON`, modo WAL e `busy_timeout`. As migrações ficam em `backend/migrations/NNNN_nome.sql` e são aplicadas em ordem, cada uma numa transação, registradas na tabela `schema_migrations`. Para evoluir o esquema, crie `0002_algo.sql`; nunca edite uma migração já aplicada.

| Tabela | Conteúdo |
| --- | --- |
| `users` | Contas. `username` e `email` únicos (sem diferenciar maiúsculas), senha só como hash |
| `games` | Cópia local mínima de cada jogo usado pela comunidade (id da RAWG, nome, capa...), para que o diário continue funcionando se a RAWG falhar |
| `library_entries` | Diário: um registro por pessoa e jogo, com status, datas e favorito |
| `reviews` | A nota e o texto. **A nota mora só aqui**: o diário não guarda nota própria, então nunca há duas notas diferentes para o mesmo jogo |
| `review_likes` | Curtidas (única por pessoa e review) |
| `lists`, `list_games` | Listas e seus jogos, com posição |
| `follows` | Quem segue quem (sem auto-seguir, sem duplicata) |
| `activities` | Histórico do diário (mudanças de status, reviews, listas) que alimenta perfis e feeds |

Chaves estrangeiras com `ON DELETE CASCADE` onde faz sentido e índices nas colunas de filtro e ordenação. Apagar uma entrada do diário **não** apaga a review do jogo.

## API

Respostas em JSON. Erros sempre no formato `{"error": {"code": "...", "message": "...", "fields": {...}}}`, com mensagens em português. Rotas de escrita exigem sessão e o cabeçalho `X-CSRF-Token` (o valor vem de `GET /api/auth/me`).

| Grupo | Rotas |
| --- | --- |
| Conta | `GET /api/auth/me`, `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `PATCH /api/auth/me` (nome, bio, foto) |
| Jogos (RAWG) | `GET /api/games` (busca, filtros, ordem, página), `/api/games/featured`, `/api/games/top-rated`, `/api/games/<id>`, `/api/genres`, `/api/platforms` |
| Reviews | `GET /api/reviews` (recentes), `GET /api/games/<id>/reviews`, `POST /api/games/<id>/reviews`, `GET`/`PATCH`/`DELETE /api/reviews/<id>`, `PUT`/`DELETE /api/reviews/<id>/like` |
| Diário | `GET /api/library`, `PUT`/`DELETE /api/library/<id_do_jogo>` (o `PUT` aceita `today`, a data local de quem usa o site, usada ao preencher início e término automaticamente) |
| Listas | `GET`/`POST /api/lists`, `GET /api/me/lists`, `GET`/`PATCH`/`DELETE /api/lists/<id>`, `POST /api/lists/<id>/games`, `DELETE /api/lists/<id>/games/<jogo>`, `PUT /api/lists/<id>/order` |
| Pessoas | `GET /api/users/<usuario>` e `/library`, `/reviews`, `/lists`, `/activity`, `/followers`, `/following`; `PUT`/`DELETE /api/users/<usuario>/follow` |
| Feed e busca | `GET /api/activity`, `GET /api/feed`, `GET /api/search?q=` |
| Saúde | `GET /api/health` |

## Segurança

- **Senhas** com hash `scrypt` e sal individual; mínimo de 8 caracteres, máximo de 128, e rejeição de senhas comuns. A mensagem de login incorreto não revela se o e-mail existe.
- **Sessão** em cookie assinado `HttpOnly`, `SameSite=Lax` (e `Secure` em produção), com validade de 30 dias. Nada sensível vai para `localStorage` ou `sessionStorage`.
- **CSRF**: token por sessão enviado em `X-CSRF-Token` e comparado em tempo constante; além disso, o cabeçalho `Origin` é validado.
- **CORS** só para origens listadas; sem `*`.
- **SQL injection**: todas as consultas usam parâmetros (`?`). Os curingas de `LIKE` são escapados.
- **XSS**: o React escapa texto por padrão; nunca usamos `dangerouslySetInnerHTML`. A página é servida com Content-Security-Policy restritiva (`script-src 'self'`), `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'`.
- **Autorização**: cada rota de escrita confere se o recurso é da pessoa logada. Listas privadas respondem como "não encontrada" para outras pessoas.
- **Validação** sempre no servidor (e repetida no navegador só para dar feedback rápido): tamanho de textos, faixa e passo da nota, status permitidos, nomes de usuário, URLs de avatar (apenas https).
- **Limite de requisições** por IP em login, cadastro, busca, catálogo e escritas.
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
- **A nota mora só em `reviews.rating`.** O diário não guarda nota, então nunca existem duas notas divergentes para o mesmo jogo.
- **Cópia local mínima dos jogos, criada sob demanda.** Diário, listas e perfis continuam funcionando se a RAWG cair. A RAWG só é acessada pelo back-end (a chave nunca chega ao navegador), com cache com validade e cópia expirada servida em caso de falha.
- **Datas de calendário no fuso de quem joga.** O servidor trabalha em UTC, mas quem marca "Jogando" às 22h no Brasil já está no "amanhã" de UTC. O navegador envia o seu "hoje" (`today`) e o servidor só o aceita se estiver a no máximo um dia de UTC, o que cobre todos os fusos e impede forjar datas distantes.
- **Roteador próprio sobre a History API**, em vez de uma biblioteca: o app tem poucas rotas e o roteador cobre o que ele precisa (parâmetros de rota e de busca, links ativos, redirecionamento) sem dependência extra, e o foco e o título ao trocar de página ficam no layout.
- **CSS próprio com variáveis (tokens) e fontes hospedadas junto do site.** Sem framework de UI e sem scripts, estilos ou fontes de terceiros (só as capas vêm da CDN da RAWG): a política de segurança do servidor (`script-src 'self'`) vale para a página inteira.
- **Testes que não dependem de rede.** O back-end usa uma RAWG simulada, e o teste de navegador sobe o Flask real com um servidor RAWG fictício. Os testes de mutação feitos durante o desenvolvimento (quebrar o CSRF, a privacidade de listas, o passo da nota, a regra do avatar e a data local de propósito) confirmaram que a suíte pega essas regressões.

## Solução de problemas

**`flask: command not found`** — o ambiente virtual não está ativo. Rode `source .venv/bin/activate` (ou `.venv\Scripts\Activate.ps1`) dentro de `backend/`, ou use `python -m flask --app wsgi run --debug`.

**`'npm' não é reconhecido` (ou *"não é reconhecido como nome de cmdlet"*)** — o Node.js não está instalado ou o terminal foi aberto antes da instalação. Instale a versão LTS em nodejs.org, **feche todos os terminais** (e o editor, se for o VS Code), abra outro e teste `node --version` e `npm --version`. Para atualizar a lista de programas só na janela atual do PowerShell, sem reiniciar: `$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")`.

**"A execução de scripts foi desabilitada neste sistema" (PowerShell, no `Activate.ps1` ou no `npm`)** — rode `Set-ExecutionPolicy -Scope Process Bypass` na mesma janela e repita o comando, ou use o Prompt de Comando (`.venv\Scripts\activate.bat`, `npm.cmd`).

**`ModuleNotFoundError` ao rodar o back-end ou o pytest** — rode `pip install -r requirements.txt` com o ambiente virtual ativo, dentro de `backend/`.

**O catálogo mostra "A integração com a RAWG não está configurada" (erro 503)** — falta `RAWG_API_KEY` em `backend/.env` (reinicie o Flask depois de editar). Se a mensagem for "A RAWG recusou a chave", a chave está errada; "A RAWG está indisponível" ou "limite de consultas" indicam falha ou cota esgotada do lado deles. Veja o terminal do Flask: o motivo aparece no log. Para desenvolver sem chave, use o [servidor fictício](#desenvolver-sem-chave-da-rawg).

**"Sua sessão de segurança expirou" ao entrar ou salvar** — o token CSRF não bateu (por exemplo, o servidor foi reiniciado com outro `SECRET_KEY`). O site tenta de novo sozinho uma vez; se a mensagem aparecer, recarregue a página. Se persistir, apague os cookies do site.

**No front-end, requisições para `/api` falham com `ECONNREFUSED`/502** — o Flask não está rodando ou está em outra porta. Ajuste `VITE_BACKEND_URL`.

**Porta 5000 em uso (macOS)** — desligue o AirPlay Receiver ou use `--port 5001` e `VITE_BACKEND_URL`, como indicado acima.

**`database is locked`** — há outro processo segurando o arquivo (um segundo Flask, um editor de banco com transação aberta). Feche-o. Não rode vários processos do app sobre o mesmo banco.

**Quero começar do zero** — pare o Flask e apague `backend/instance/discplayer.db*` (e só isso: `backend/instance/secret_key` mantém as sessões válidas). Ao subir, o banco é recriado.

**`npm install` reclama da versão do Node** — o Vite 7 exige Node 20.19 ou superior. Atualize o Node.

**Em produção, o login "não pega"** — confira se o site é acessado por HTTPS (cookie `Secure`), se `TRUSTED_PROXY_COUNT` corresponde ao número de proxies e se o proxy repassa os cabeçalhos `X-Forwarded-Proto` e `X-Forwarded-Host`.

**`SECRET_KEY` ... pelo menos 32 caracteres** — em `APP_ENV=production` a chave é obrigatória. Gere uma com `python -c "import secrets; print(secrets.token_hex(32))"`.

## Limitações conhecidas

Estas são limitações reais do projeto como entregue, não promessas futuras.

- **Verificação parcial.** O código foi escrito num ambiente sem acesso à internet aberta. Por isso, **nunca foi testado contra a RAWG de verdade** (apenas contra simulações fiéis ao formato documentado: confira os formatos de campos como `results`, `rating`, `released` com sua chave antes de publicar) e o **waitress** não foi iniciado. O que já foi confirmado fora desse ambiente: o CI do GitHub executa `npm ci`, `npm test`, o build de produção do Vite e os testes de navegador sobre esse build (Ubuntu, Node 22), e o back-end passa em Python 3.11 e 3.13.
- **Cache da RAWG e limite de requisições ficam na memória do processo.** Reiniciar o app os esvazia, e **mais de um processo** (vários workers) teria contagens e caches separados. Para escalar além de um processo, troque por Redis ou similar.
- **SQLite** atende bem uma instância única; não é pensado para várias máquinas escrevendo no mesmo arquivo.
- **Avatar** é uma URL https informada pela pessoa (sem upload de imagem). O navegador a carrega diretamente.
- **Sem troca nem recuperação de senha, sem verificação de e-mail e sem notificações**: o projeto não envia e-mails e a tela de configurações só edita nome, bio e foto.
- **Sem moderação** (denunciar, bloquear, ocultar reviews). Antes de abrir o cadastro ao público, planeje isso.
- **Sem exclusão de conta** pela interface.
- **Capas e imagens** são carregadas da CDN da RAWG, que impõe a própria política de uso; o site não as copia nem as redimensiona.
- **Sem internacionalização**: a interface está só em português do Brasil.
- **Sem testes automatizados de acessibilidade completos**: a auditoria feita foi manual (teclado, leitor de tela em estrutura, contraste) e por inspeção do DOM. Faça uma revisão com tecnologias assistivas reais antes de publicar.

## Próximos passos

Ideias priorizadas para as próximas versões (nenhuma está implementada):

1. **Conta completa:** troca e recuperação de senha por e-mail, verificação de e-mail, exclusão de conta e exportação dos próprios dados.
2. **Moderação:** denunciar e ocultar reviews, bloquear usuários.
3. **Diário mais fiel ao hábito de jogar:** várias jogadas do mesmo jogo (com data, plataforma e horas) e aviso de spoiler nas reviews.
4. **Compartilhamento:** prévia (título e capa) ao colar links de jogos, perfis e listas, e uma retrospectiva do ano para compartilhar.
5. **Comunidade:** notificações, comentários em reviews e listas, importação da biblioteca da Steam.
6. **Escala:** cache e limite de requisições compartilhados entre processos, busca de texto nas reviews e, se necessário, outro banco no lugar do SQLite.

## Créditos e licenças

- Código sob a licença **MIT** (arquivo `LICENSE`).
- Dados e imagens de jogos: [RAWG](https://rawg.io) — o uso da API exige atribuição e respeito aos termos de uso deles.
- Fontes: **TeX Gyre Adventor** (GUST Font License) e **Lora** (SIL Open Font License). Autoria, licenças e links de origem estão em `frontend/src/assets/fonts/LICENSES.md`.
- Os jogos, capas e nomes do servidor fictício de desenvolvimento são inventados e existem só para testes.
