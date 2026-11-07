# Solução de problemas

Os erros mais comuns ao instalar e rodar o DiscPlayer, e como resolver cada um.

[← Voltar ao README](../README.md)

**`flask: command not found`** — o ambiente virtual não está ativo. Rode `source .venv/bin/activate` (ou `.venv\Scripts\Activate.ps1`) dentro de `backend/`, ou use `python -m flask --app wsgi run --debug`.

**`'npm' não é reconhecido` (ou *"não é reconhecido como nome de cmdlet"*)** — o Node.js não está instalado ou o terminal foi aberto antes da instalação. Instale a versão LTS em nodejs.org, **feche todos os terminais** (e o editor, se for o VS Code), abra outro e teste `node --version` e `npm --version`. Para atualizar a lista de programas só na janela atual do PowerShell, sem reiniciar: `$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")`.

**"A execução de scripts foi desabilitada neste sistema" (PowerShell, no `Activate.ps1` ou no `npm`)** — rode `Set-ExecutionPolicy -Scope Process Bypass` na mesma janela e repita o comando, ou use o Prompt de Comando (`.venv\Scripts\activate.bat`, `npm.cmd`).

**`ModuleNotFoundError` ao rodar o back-end ou o pytest** — rode `pip install -r requirements.txt` com o ambiente virtual ativo, dentro de `backend/`.

**O catálogo mostra "A integração com o IGDB não está configurada" (erro 503)** — faltam `IGDB_CLIENT_ID` e `IGDB_CLIENT_SECRET` em `backend/.env` (reinicie o Flask depois de editar). Se a mensagem for "A Twitch recusou as credenciais" ou "O IGDB recusou as credenciais", o Client ID ou o Client Secret está errado (ou o segredo foi trocado no painel da Twitch); "O IGDB está indisponível" ou "limite de consultas" indicam falha ou excesso de consultas do lado deles (o limite é de 4 por segundo). Veja o terminal do Flask: o motivo aparece no log. **Rode `python -m app.igdb_check`** (na pasta `backend`, com o ambiente virtual ativo): ele aponta qual parte falhou e não mostra suas chaves. Para desenvolver sem credenciais, use o [servidor fictício](desenvolvimento.md#desenvolver-sem-credenciais-do-igdb).

**Um jogo não aparece na busca, ou a página dele diz "Jogo indisponível"** — o filtro de conteúdo adulto o escondeu (o IGDB o classifica como 18+ ou o marca com o tema *Erotic*). Não é erro. Para ver tudo, ponha `ADULT_CONTENT_FILTER=off` em `backend/.env` e reinicie o Flask; para ser mais rígido, `mature`. Detalhes em [Conteúdo adulto](desenvolvimento.md#conteúdo-adulto-18).

**"Sua sessão de segurança expirou" ao entrar ou salvar** — o token CSRF não bateu (por exemplo, o servidor foi reiniciado com outro `SECRET_KEY`). O site tenta de novo sozinho uma vez; se a mensagem aparecer, recarregue a página. Se persistir, apague os cookies do site.

**No front-end, requisições para `/api` falham com `ECONNREFUSED`/502** — o Flask não está rodando ou está em outra porta. Ajuste `VITE_BACKEND_URL`.

**Porta 5000 em uso (macOS)** — desligue o AirPlay Receiver ou use `--port 5001` e `VITE_BACKEND_URL`, como indicado acima.

**`database is locked`** — há outro processo segurando o arquivo (um segundo Flask, um editor de banco com transação aberta). Feche-o. Não rode vários processos do app sobre o mesmo banco.

**Quero começar do zero** — pare o Flask e apague `backend/instance/discplayer.db*` (e só isso: `backend/instance/secret_key` mantém as sessões válidas). Ao subir, o banco é recriado.

**`npm install` reclama da versão do Node** — o Vite 7 exige Node 20.19 ou superior. Atualize o Node.

**Em produção, o login "não pega"** — confira se o site é acessado por HTTPS (cookie `Secure`), se `TRUSTED_PROXY_COUNT` corresponde ao número de proxies e se o proxy repassa os cabeçalhos `X-Forwarded-Proto` e `X-Forwarded-Host`.

**Enviar a foto responde "falta instalar o Pillow"** (ou `No module named 'PIL'`) — com o ambiente virtual ativo, rode `pip install -r requirements.txt` dentro de `backend/` e reinicie o back-end.

**`SECRET_KEY` ... pelo menos 32 caracteres** — em `APP_ENV=production` a chave é obrigatória. Gere uma com `python -c "import secrets; print(secrets.token_hex(32))"`.
