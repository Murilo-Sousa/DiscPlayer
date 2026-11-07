# Guia de desenvolvimento

A versão completa do passo a passo para rodar o DiscPlayer no seu computador, com todos os sistemas e terminais, as credenciais do IGDB, o modo sem credenciais e todas as variáveis de ambiente. O resumo em poucos comandos está no README.

[← Voltar ao README](../README.md)

## Requisitos

- **Python 3.11 ou mais novo** (`python --version`)
- **Node.js 20.19 ou mais novo** com npm (`node --version`)
- **Credenciais do IGDB** (gratuitas, vêm da Twitch) — ou use o [servidor de dados fictícios](#desenvolver-sem-credenciais-do-igdb) enquanto não tiver uma

> **Windows: depois de instalar o Python ou o Node.js, feche o terminal e abra outro.** Terminais abertos antes da instalação não enxergam os programas novos e mostram erros como *"npm não é reconhecido como nome de cmdlet"*. Se o terminal estiver dentro de um editor (como o VS Code), feche o editor inteiro e abra de novo. Para conferir: `node --version` e `npm --version` devem mostrar números de versão.

### Como conseguir as credenciais do IGDB

O IGDB é o banco de jogos da Twitch, e o acesso é feito com um aplicativo cadastrado na conta da Twitch. É gratuito para projetos sem fins comerciais.

1. Entre (ou crie uma conta) em <https://dev.twitch.tv/console>. A Twitch exige **verificação em duas etapas** (2FA) para criar aplicativos: se ela pedir, ative em *Configurações → Segurança e privacidade*.
2. Clique em **Registrar seu aplicativo** e preencha:
   - **Nome**: único na Twitch (por exemplo, `DiscPlayer-seunome`);
   - **URLs de redirecionamento OAuth**: `http://localhost` (o projeto não usa, mas o campo é obrigatório);
   - **Categoria**: *Website Integration*;
   - **Tipo de cliente**: *Confidential*.
3. Depois de criar, abra **Gerenciar** no aplicativo. Copie o **ID de cliente** e clique em **Novo segredo** para gerar o **segredo do cliente** (ele só aparece uma vez: copie na hora).
4. Guarde os dois em `backend/.env` como `IGDB_CLIENT_ID=...` e `IGDB_CLIENT_SECRET=...` (passo a passo abaixo).

As credenciais **nunca vão para o navegador**: só o back-end fala com a Twitch e com o IGDB, e o segredo vai no corpo do pedido (nunca na URL). Não as cole em conversas, prints nem no GitHub; se uma vazar, gere um novo segredo no mesmo painel e o antigo deixa de valer. O uso do IGDB exige citá-lo como fonte, e o rodapé do site já faz isso com link.

**Limites do IGDB:** 4 consultas por segundo (o back-end espera a vez sozinho) e, no máximo, 8 consultas abertas ao mesmo tempo. O cache do projeto mantém o uso muito abaixo disso.

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

Abra `backend/.env` e preencha `IGDB_CLIENT_ID=` e `IGDB_CLIENT_SECRET=` com as suas credenciais. Não é preciso mexer no resto para desenvolver. Para conferir se funcionam, e se o IGDB ainda responde do jeito que o projeto espera, rode `python -m app.igdb_check` (veja [Conferir a integração](#conferir-a-integração-com-o-igdb)).

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

## Desenvolver sem credenciais do IGDB

O projeto inclui um servidor local que imita o IGDB **e o login da Twitch** com **dados fictícios** (jogos, gêneros e plataformas de mentira, sem imagens reais). Serve para desenvolver e testar a interface sem internet e sem credenciais. Não use isso como catálogo de verdade.

No terminal do back-end, com o ambiente virtual ativo:

```bash
# Terminal A: o "IGDB de mentira", na porta 8765
python -m tests.fake_igdb_server
```

```bash
# Terminal B: a API apontando para ele (Linux/macOS)
IGDB_BASE_URL=http://127.0.0.1:8765/v4 IGDB_TOKEN_URL=http://127.0.0.1:8765/oauth2/token IGDB_CLIENT_ID=qualquer IGDB_CLIENT_SECRET=qualquer flask --app wsgi run --debug
```

No PowerShell: `$env:IGDB_BASE_URL="http://127.0.0.1:8765/v4"; $env:IGDB_TOKEN_URL="http://127.0.0.1:8765/oauth2/token"; $env:IGDB_CLIENT_ID="qualquer"; $env:IGDB_CLIENT_SECRET="qualquer"; flask --app wsgi run --debug`. No Prompt de Comando, use `set NOME=valor` em uma linha para cada variável e depois `flask --app wsgi run --debug`.

As capas apontam para `images.igdb.com`; sem acesso a esse endereço, o site mostra o espaço reservado da capa, sem quebrar o layout.

## Conferir a integração com o IGDB

O projeto foi escrito seguindo a documentação do IGDB, e o IGDB muda com o tempo (campos antigos saem, novos entram). Com as credenciais no `backend/.env`, rode, na pasta `backend` e com o ambiente virtual ativo:

```bash
python -m app.igdb_check
```

O comando conversa com o IGDB de verdade e confere, numa lista curta, cada coisa de que o site depende: login na Twitch, gêneros, plataformas, listas da página inicial, busca, filtros e ordens do catálogo, a página de um jogo, as classificações etárias, o filtro de conteúdo adulto e as imagens (`--sem-imagens` pula essa última). Cada linha é `✔` (ok), `⚠` (informação ou aviso, não é erro) ou `✖` (falhou). **A saída nunca mostra as credenciais nem o token** (e nomes de jogos adultos também não aparecem, só contagens), então dá para copiá-la inteira numa conversa ou num relatório de problema. O código de saída é 0 sem falhas, 1 com falhas e 2 se faltam as credenciais.

## Ver a prévia de links

A prévia (título, descrição e imagem de jogos, perfis, listas e retrospectivas) é escrita pelo Flask no HTML, então **só aparece quando o Flask serve o site**, e não no `npm run dev`. Para ver o resultado, gere o build (`npm run build` em `frontend/`), rode o back-end e abra `http://127.0.0.1:5000`; o código-fonte da página (Ctrl+U) mostra as tags `og:` do endereço. A prévia de um jogo usa só o que o servidor já guarda: abra a página do jogo uma vez (isso enche o cache) antes de olhar o código-fonte. As imagens ficam em `/api/share/...png` e podem ser abertas direto no navegador. Aplicativos como o WhatsApp só leem endereços públicos da internet: para vê-las de verdade é preciso publicar o site (e guardam a prévia por um tempo, então uma mudança pode demorar a aparecer).

## Variáveis de ambiente

Todas são lidas de `backend/.env` (modelo em `backend/.env.example`) ou do ambiente do sistema. O front-end só tem uma, usada apenas pelo `npm run dev`.

| Variável | Padrão | Para quê |
| --- | --- | --- |
| `IGDB_CLIENT_ID` e `IGDB_CLIENT_SECRET` | vazios | Credenciais do aplicativo da Twitch. Sem elas, as rotas de catálogo respondem `503` com uma mensagem clara; o resto do site funciona |
| `APP_ENV` | `development` | `production` torna `SECRET_KEY` obrigatória e liga o cookie `Secure` |
| `SECRET_KEY` | gerada em dev | Assina o cookie de sessão (mínimo de 32 caracteres em produção) |
| `DATABASE_PATH` | `backend/instance/discplayer.db` | Caminho do arquivo SQLite |
| `AUTO_MIGRATE` | `true` | Aplica migrações pendentes ao iniciar |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Origens extras autorizadas a chamar a API |
| `COOKIE_SECURE` | `true` em produção | Cookie só por HTTPS. Use `false` para testar o build em `http://localhost` |
| `TRUSTED_PROXY_COUNT` | `0` | Quantos proxies reversos existem à frente do app (para ver o IP real) |
| `PUBLIC_URL` | vazio | Endereço público do site (por exemplo, `https://seu-site.exemplo`), usado nos links absolutos das prévias de links. Vazio usa o endereço da própria requisição. Só aceita `http` ou `https`, com domínio e sem caminho; qualquer outro valor é ignorado |
| `RATELIMIT_ENABLED` | `true` | Liga o limite de requisições por IP |
| `IGDB_BASE_URL` | `https://api.igdb.com/v4` | Troque só para usar o servidor fictício |
| `IGDB_TOKEN_URL` | `https://id.twitch.tv/oauth2/token` | Onde o back-end pede o token da Twitch. Troque só para usar o servidor fictício |
| `ADULT_CONTENT_FILTER` | `explicit` | Esconde jogos 18+ do IGDB: `explicit`, `mature` ou `off` (veja [Conteúdo adulto](#conteúdo-adulto-18)). Qualquer outro valor vale como `explicit`; reinicie o Flask depois de mudar |
| `VITE_BACKEND_URL` (front-end) | `http://127.0.0.1:5000` | Destino do proxy `/api` no `npm run dev` |

## Conteúdo adulto (18+)

O IGDB lista jogos adultos junto com os outros e não tem como pedir que ele os exclua. Por isso o back-end filtra a resposta (`backend/app/services/adult.py`) olhando dois campos que o IGDB manda em cada jogo: as **classificações etárias** (`age_ratings`, cada uma com a organização, como ESRB, PEGI, USK ou ClassInd, e a nota) e os **temas** (`themes`, onde o tema *Erotic* marca conteúdo sexual explícito). O mesmo filtro vale para a busca, o catálogo, a página inicial, "Mais em <gênero>" e a página do jogo, e também impede guardar um jogo escondido no diário, numa review ou numa lista. Escolha o nível em `backend/.env`:

| `ADULT_CONTENT_FILTER` | O que esconde |
| --- | --- |
| `explicit` (padrão) | O que a ESRB classifica como *Adults Only* (o 18+ de verdade) e os jogos com o tema *Erotic* |
| `mature` | Tudo isso, mais o que alguma organização põe em 17+/18+: ESRB *Mature*, PEGI 18, USK 18, ClassInd 18, CERO Z, GRAC 18+ e ACB R18+. É bem mais rígido: esconde, por exemplo, The Witcher 3 e Red Dead Redemption 2 |
| `off` | Nada |

A nota "18" só vale junto da organização que a usa (o filtro confere o par organização + nota). Quem abre o endereço de um jogo escondido vê "Jogo indisponível". `GET /api/health` mostra o nível em uso (`adult_content_filter`).

**Limites.** O IGDB é editado pela comunidade e muitos jogos adultos não têm classificação nem tema: o filtro só os pega se estiverem preenchidos, então ele **reduz** o conteúdo adulto, não garante a ausência dele. A conta de "N jogos" no catálogo desconta só os escondidos da página atual (uma aproximação). Jogos que já estavam no diário, em listas ou em reviews antes de o filtro existir continuam aparecendo nesses lugares, mas a página deles passa a dizer "indisponível".

**Confira com as suas credenciais.** O `python -m app.igdb_check` (acima) testa o filtro contra o IGDB de verdade: confirma que o tema número 42 ainda é *Erotic*, que as classificações chegam no formato esperado e que um jogo adulto de verdade some da busca e da página. Se alguma organização nova aparecer, inclua-a em `_RATINGS_MATURE_LEVEL` em `adult.py`.

## Colocar o projeto no GitHub

O projeto já traz um `.gitignore` que impede o envio do seu `.env` (com as credenciais do IGDB), do `.venv`, do `node_modules` e do banco de dados. O passo a passo completo, para Windows (PowerShell e Prompt de Comando), com login pelo navegador, token e os avisos que costumam assustar, está na **Parte 1** de [hospedagem-pythonanywhere.md](hospedagem-pythonanywhere.md#parte-1--colocar-o-código-no-github). O resumo:

```bash
git init -b main
git add .
git commit -m "DiscPlayer: primeira versão"
git remote add origin https://github.com/SEU-USUARIO/discplayer.git
git push -u origin main
```

Antes do `git commit`, confira que nenhum arquivo sensível entrou (nada deve aparecer): no PowerShell, `git ls-files | Select-String "node_modules|\.venv|instance|\.db|\.env$"`; no Prompt de Comando, `git ls-files | findstr /R "node_modules \.venv instance \.db \.env$"`.
