# Guia de desenvolvimento

A versão completa do passo a passo para rodar o DiscPlayer no seu computador, com todos os sistemas e terminais, a chave da RAWG, o modo sem chave e todas as variáveis de ambiente. O resumo em poucos comandos está no README.

[← Voltar ao README](../README.md)

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

## Ver a prévia de links

A prévia (título, descrição e imagem de jogos, perfis, listas e retrospectivas) é escrita pelo Flask no HTML, então **só aparece quando o Flask serve o site**, e não no `npm run dev`. Para ver o resultado, gere o build (`npm run build` em `frontend/`), rode o back-end e abra `http://127.0.0.1:5000`; o código-fonte da página (Ctrl+U) mostra as tags `og:` do endereço. A prévia de um jogo usa só o que o servidor já guarda: abra a página do jogo uma vez (isso enche o cache) antes de olhar o código-fonte. As imagens ficam em `/api/share/...png` e podem ser abertas direto no navegador. Aplicativos como o WhatsApp só leem endereços públicos da internet: para vê-las de verdade é preciso publicar o site (e guardam a prévia por um tempo, então uma mudança pode demorar a aparecer).

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
| `PUBLIC_URL` | vazio | Endereço público do site (por exemplo, `https://seu-site.exemplo`), usado nos links absolutos das prévias de links. Vazio usa o endereço da própria requisição. Só aceita `http` ou `https`, com domínio e sem caminho; qualquer outro valor é ignorado |
| `RATELIMIT_ENABLED` | `true` | Liga o limite de requisições por IP |
| `RAWG_BASE_URL` | `https://api.rawg.io/api` | Troque só para usar o servidor fictício |
| `ADULT_CONTENT_FILTER` | `explicit` | Esconde jogos 18+ da RAWG: `explicit`, `mature` ou `off` (veja [Conteúdo adulto](#conteúdo-adulto-18)). Qualquer outro valor vale como `explicit`; reinicie o Flask depois de mudar |
| `VITE_BACKEND_URL` (front-end) | `http://127.0.0.1:5000` | Destino do proxy `/api` no `npm run dev` |

## Conteúdo adulto (18+)

A RAWG lista jogos adultos junto com os outros, e não tem como pedir a ela que os exclua. Por isso o back-end filtra a resposta (`backend/app/services/adult.py`) olhando a classificação da ESRB (`esrb_rating`) e as tags de cada jogo. O mesmo filtro vale para a busca, o catálogo, a página inicial, "Mais em <gênero>" e a página do jogo, e também impede guardar um jogo escondido no diário, numa review ou numa lista. Escolha o nível em `backend/.env`:

| `ADULT_CONTENT_FILTER` | O que esconde |
| --- | --- |
| `explicit` (padrão) | O que a ESRB classifica como *Adults Only* (o 18+ de verdade) e o que a RAWG marca como explícito (tags `nsfw`, `hentai`, `eroge`, `erotic`) |
| `mature` | Tudo isso, mais jogos *Mature* (17+) e as tags `nudity` e `sexual-content`. É bem mais rígido: esconde, por exemplo, The Witcher 3 e Red Dead Redemption 2 |
| `off` | Nada |

Quem abre o endereço de um jogo escondido vê "Jogo indisponível". `GET /api/health` mostra o nível em uso (`adult_content_filter`).

**Limites.** A RAWG é editada pela comunidade e muitos jogos adultos não têm classificação nenhuma: o filtro só os pega se estiverem com as tags certas, então ele **reduz** o conteúdo adulto, não garante a ausência dele. A conta de "N jogos" no catálogo desconta só os escondidos da página atual (uma aproximação). Jogos que já estavam no diário, em listas ou em reviews antes de o filtro existir continuam aparecendo nesses lugares, mas a página deles passa a dizer "indisponível".

**Confira com a sua chave.** Os nomes das tags (slugs) e o fato de a RAWG mandá-las já na listagem vêm da documentação, e este projeto nunca foi testado contra a RAWG de verdade. No Prompt de Comando (troque `SUA_CHAVE`):

```
curl "https://api.rawg.io/api/tags?search=nsfw&key=SUA_CHAVE"
curl "https://api.rawg.io/api/games?search=witcher&page_size=1&key=SUA_CHAVE"
```

A primeira mostra o `slug` da tag; a segunda deve trazer `esrb_rating` e `tags` dentro de cada jogo. Se um slug for diferente, ajuste as listas `_TAGS_ALWAYS` e `_TAGS_MATURE_LEVEL` em `adult.py`.

## Colocar o projeto no GitHub

O projeto já traz um `.gitignore` que impede o envio do seu `.env` (com a chave da RAWG), do `.venv`, do `node_modules` e do banco de dados. O passo a passo completo, para Windows (PowerShell e Prompt de Comando), com login pelo navegador, token e os avisos que costumam assustar, está na **Parte 1** de [hospedagem-pythonanywhere.md](hospedagem-pythonanywhere.md#parte-1--colocar-o-código-no-github). O resumo:

```bash
git init -b main
git add .
git commit -m "DiscPlayer: primeira versão"
git remote add origin https://github.com/SEU-USUARIO/discplayer.git
git push -u origin main
```

Antes do `git commit`, confira que nenhum arquivo sensível entrou (nada deve aparecer): no PowerShell, `git ls-files | Select-String "node_modules|\.venv|instance|\.db|\.env$"`; no Prompt de Comando, `git ls-files | findstr /R "node_modules \.venv instance \.db \.env$"`.
