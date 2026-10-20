# Publicar o DiscPlayer de graça na PythonAnywhere

Este guia leva o projeto do seu computador até um endereço público do tipo `https://seunome.pythonanywhere.com`, usando o **plano gratuito** da [PythonAnywhere](https://www.pythonanywhere.com) e o **GitHub** para guardar o código.

> **Antes de começar, três avisos honestos**
>
> 1. As informações sobre o plano gratuito foram conferidas nas páginas oficiais em **17/10/2026**. Planos e limites mudam: se algo na tela da PythonAnywhere for diferente do que está aqui, vale a tela deles.
> 2. O guia **não foi executado de ponta a ponta na PythonAnywhere** (o ambiente onde o projeto foi escrito não alcança o site deles). O que foi testado: o arquivo `deploy/pythonanywhere_wsgi.py` em modo produção, atrás de um balanceador de carga simulado (cookie `Secure`, limite de cadastros por IP real). O resto segue a documentação da PythonAnywhere.
> 3. O comando `npm run build` (parte 2) roda no CI do GitHub (Ubuntu, Node 22) a cada envio de código, mas ainda não foi visto no Windows. Se ele mostrar um erro, copie a mensagem e peça ajuda antes de seguir.

## O que esperar do plano gratuito

| Item | Plano gratuito |
| --- | --- |
| Endereço | `seunome.pythonanywhere.com` (com HTTPS) |
| Aplicações web | 1, com 1 processo (worker) |
| Disco | 512 MiB (o banco SQLite fica nele e **não se perde** entre atualizações) |
| Validade | O web app **expira em 1 mês** se você não o estender: é preciso clicar em um botão no painel todo mês |
| Suporte | Sem suporte direto para contas gratuitas (só fóruns e documentação) |
| Acesso à internet de dentro do app | Só a sites de uma lista. `api.rawg.io` **está** na lista |

Consequência do processo único: se a RAWG demorar para responder, outras pessoas podem esperar um pouco junto. O cache do projeto reduz isso, mas não elimina.

---

## Parte 1 — Colocar o código no GitHub

**O que você precisa:** uma conta no [github.com](https://github.com) e o Git instalado ([git-scm.com](https://git-scm.com)). Se preferir uma interface gráfica, o **GitHub Desktop** faz o mesmo (adicione a pasta e clique em "Publish repository").

1. No GitHub, clique em **New repository**. Dê o nome `discplayer`, deixe **Public** (a PythonAnywhere vai baixar o código sem senha) e **não** marque nenhuma opção de criar README/.gitignore. Clique em **Create repository**.
2. No terminal (PowerShell ou Prompt de Comando), entre na pasta do projeto, **a que tem `backend`, `frontend` e `README.md`**, e não dentro de `frontend`:

   ```powershell
   cd caminho\para\DiscPlayer
   git init -b main
   git add .
   ```

3. **Confira que nenhum segredo vai junto.** Este comando lista, entre os arquivos que serão enviados, qualquer um que seja `.env`, banco de dados, `node_modules` ou `.venv`. **Não deve aparecer nenhuma linha.**

   No PowerShell (a linha começa com `PS C:\...>`):

   ```powershell
   git ls-files | Select-String "node_modules|\.venv|instance|\.db|\.env$"
   ```

   No Prompt de Comando (a linha começa só com `C:\...>`; o `Select-String` não existe lá e dá "não é reconhecido"):

   ```bat
   git ls-files | findstr /R "node_modules \.venv instance \.db \.env$"
   ```

   Se aparecer alguma linha, **pare**: sua chave da RAWG ou seu banco iriam para a internet. O `.gitignore` do projeto já impede isso, então só aconteceria se ele fosse apagado ou alterado.

   O arquivo `frontend/package-lock.json`, criado pelo `npm install`, **deve** ir para o GitHub: ele garante que todo mundo instale as mesmas versões das bibliotecas.

4. Envie:

   ```powershell
   git commit -m "DiscPlayer: primeira versão"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO_GITHUB/discplayer.git
   git push -u origin main
   ```

   Se o Git reclamar que não sabe quem você é, rode antes `git config --global user.name "Seu Nome"` e `git config --global user.email "seu@email.com"`.

### Entrar no GitHub (login do `git push`)

O GitHub **não aceita mais a senha da conta** no Git. Se aparecer `Invalid username or token. Password authentication is not supported`, é isso.

- **Caminho mais simples:** no primeiro `git push`, o Git for Windows abre uma janela **"Sign in to GitHub"**. Escolha **Sign in with your browser**, entre na sua conta e autorize. Uma aba do navegador pode abrir em branco; **não atualize essa página**. Ela só recebe a resposta do GitHub uma vez e depois se fecha, e atualizá-la mostra "não é possível acessar o site", o que é normal. Volte ao terminal e veja se o envio terminou.
- **Se o terminal pedir `Username` e `Password`:** digite seu usuário e, no lugar da senha, cole um **token**. Para criar: GitHub → sua foto → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**, marque só a caixa **`repo`**, gere e copie o token na hora (ele não é mostrado de novo). Enquanto você cola, nada aparece na tela, o que é normal; no Prompt de Comando, colar é clicar com o botão direito.
- Trate o token como uma senha: não o envie a ninguém nem o guarde em arquivos do projeto. Se vazar, apague-o na mesma tela do GitHub.
- Se o login ficar preso a uma credencial antiga, `cmdkey /delete:git:https://github.com` a apaga ("Elemento não encontrado" quer dizer que não havia nada para apagar).

Avisos que **não** são problema:

- `LF will be replaced by CRLF`: normal no Windows, pode ignorar.
- `Deletion of directory '.git/objects/xx' failed. Should I try again? (y/n)`: o Windows (antivírus, OneDrive ou indexador) estava usando uma pasta temporária do Git. Responda `n`. Seus arquivos e o commit não são afetados. Se acontecer sempre, mova o projeto para uma pasta fora do OneDrive (por exemplo `C:\Projetos\DiscPlayer`).

Quando o envio terminar, abra `github.com/SEU_USUARIO_GITHUB/discplayer`: devem aparecer as pastas do projeto e o README embaixo.

### Depois, no dia a dia

```powershell
git add .
git commit -m "descrição do que mudou"
git push
```

---

## Parte 2 — Compilar o site (no seu computador)

O site (React) precisa ser compilado em arquivos prontos, e essa pasta (`dist`) não vai para o GitHub. Você a envia direto para a PythonAnywhere.

```powershell
cd caminho\para\DiscPlayer\frontend
npm install
npm run build
```

Ao terminar, existe a pasta `frontend\dist` com um `index.html` e uma pasta `assets`.

Agora compacte a pasta `dist`: clique nela com o botão direito e escolha **Compactar em arquivo ZIP** (Windows 11) ou **Enviar para > Pasta compactada** (Windows 10). Use o próprio Explorer, não o comando `Compress-Archive`: em versões antigas do PowerShell ele gera um ZIP que se abre errado no Linux. O resultado é um `dist.zip`.

---

## Parte 3 — Montar o site na PythonAnywhere

Nos exemplos, **`SEU_USUARIO`** é o nome que você escolher ao criar a conta na PythonAnywhere (ele também vira o endereço do site). Troque em todos os lugares.

### 3.1 Criar a conta

Entre em [pythonanywhere.com](https://www.pythonanywhere.com), clique em **Start for free** (ou **Pricing & signup > Create a Beginner account**) e crie a conta gratuita.

### 3.2 Baixar o código

Menu **Consoles** > **Bash**. No terminal que abrir:

```bash
git clone https://github.com/SEU_USUARIO_GITHUB/discplayer.git DiscPlayer
```

A pasta fica em `/home/SEU_USUARIO/DiscPlayer`.

> Se o `git clone` for recusado por falta de acesso ao GitHub, use o plano B: compacte o projeto no seu computador (sem `node_modules`, sem `.venv` e sem `.env`), envie o ZIP pela aba **Files** e rode `unzip` no console Bash. Para ZIPs maiores que 100 MiB o envio é feito em partes (veja a ajuda da PythonAnywhere sobre upload de arquivos), mas o projeto sem `node_modules` é bem menor que isso.

### 3.3 Criar o ambiente virtual e instalar as dependências

No mesmo console Bash:

```bash
mkvirtualenv --python=/usr/bin/python3.13 discplayer-venv
cd ~/DiscPlayer/backend
pip install -r requirements.txt
```

Se `python3.13` não existir lá, use a versão mais nova que a PythonAnywhere oferecer (o projeto precisa de **3.11 ou superior**). Depois que o `mkvirtualenv` termina, o ambiente já fica ativo (você vê `(discplayer-venv)` no começo da linha).

### 3.4 Criar o arquivo `.env` com os segredos

Ainda no Bash:

```bash
cd ~/DiscPlayer/backend
python -c "import secrets; print(secrets.token_hex(32))"
```

Copie o texto longo que aparecer: é a sua `SECRET_KEY`. Agora crie o arquivo:

```bash
nano .env
```

Digite estas duas linhas (trocando pelos seus valores, sem aspas e sem espaços ao redor do `=`):

```
SECRET_KEY=cole-aqui-o-texto-longo-gerado
RAWG_API_KEY=cole-aqui-a-sua-chave-da-rawg
```

Salve com `Ctrl+O`, `Enter`, e saia com `Ctrl+X`. (Se preferir, abra a aba **Files**, vá em `DiscPlayer/backend`, crie o arquivo `.env` e edite pelo navegador.)

Guarde a `SECRET_KEY` em um lugar seguro. Se ela mudar, todo mundo é desconectado.

### 3.5 Enviar o site compilado

1. Aba **Files** > navegue até `/home/SEU_USUARIO/DiscPlayer/frontend/`.
2. Clique em **Upload a file** e envie o `dist.zip` da Parte 2.
3. No console Bash:

   ```bash
   cd ~/DiscPlayer/frontend
   unzip -o dist.zip
   rm dist.zip
   ls dist
   ```

   O `ls dist` deve mostrar `index.html` e `assets`. Se aparecer só outra pasta `dist`, os arquivos ficaram um nível abaixo: mova-os com `mv dist/dist/* dist/`.

### 3.6 Criar o web app

1. Aba **Web** > **Add a new web app**.
2. Aceite o domínio `SEU_USUARIO.pythonanywhere.com` e clique em **Next**.
3. Escolha **Manual configuration**. **Não** escolha a opção "Flask": ela é para projetos novos.
4. Escolha a **mesma versão do Python** do ambiente virtual (3.13 no exemplo) e conclua.

### 3.7 Configurar o web app

Na página do web app (aba **Web**), preencha:

| Campo | Valor |
| --- | --- |
| **Source code** | `/home/SEU_USUARIO/DiscPlayer/backend` |
| **Working directory** | `/home/SEU_USUARIO/DiscPlayer/backend` |
| **Virtualenv** | `discplayer-venv` (ao dar Enter, ele vira o caminho completo) |
| **Force HTTPS** | **Enabled** (obrigatório: o cookie de login só funciona em HTTPS) |

### 3.8 Colar o arquivo WSGI

1. Ainda na aba **Web**, clique no link do **WSGI configuration file** (algo como `/var/www/SEU_USUARIO_pythonanywhere_com_wsgi.py`).
2. **Apague todo o conteúdo** e cole o conteúdo de [`deploy/pythonanywhere_wsgi.py`](../deploy/pythonanywhere_wsgi.py), trocando `SEU_USUARIO` na linha `PROJETO = ...`.
3. Clique em **Save**.

### 3.9 Ligar

Volte à aba **Web** e clique no botão verde **Reload SEU_USUARIO.pythonanywhere.com**. Pronto.

---

## Parte 4 — Conferir

1. Abra `https://SEU_USUARIO.pythonanywhere.com/api/health`. Deve mostrar algo como `{"status":"ok", ...}`.
2. Abra `https://SEU_USUARIO.pythonanywhere.com`: o site deve carregar.
3. Crie uma conta, abra um jogo, marque um status e escreva uma review.
4. Abra o site em outro aparelho (ou janela anônima), crie uma segunda conta e teste seguir e curtir.

Se algo falhar, veja a seção **Problemas comuns** abaixo.

---

## Atualizar o site depois

**Mudou o código do back-end ou do front-end?**

1. No seu computador: `git add .`, `git commit -m "descrição"` e `git push`.
2. Na PythonAnywhere (console Bash): `cd ~/DiscPlayer && git pull`.
3. Mudou o front-end? Rode `npm run build` de novo, compacte a `dist`, envie e rode `unzip -o dist.zip` (Parte 3.5).
4. Mudou `requirements.txt`? Rode `pip install -r requirements.txt` com o ambiente ativo (`workon discplayer-venv`).
5. Aba **Web** > **Reload**.

O banco (`backend/instance/discplayer.db`) e o `.env` não são afetados pelo `git pull`, porque não estão no GitHub.

## Renovar todo mês

O plano gratuito derruba o web app depois de **1 mês** sem renovação. Entre na aba **Web** da PythonAnywhere uma vez por mês e use o botão de estender a validade (a página de limites deles não descreve o nome exato do botão; ele fica perto do topo da aba). Coloque um lembrete no calendário.

## Backup do banco

No console Bash, com o ambiente ativo:

```bash
cd ~/DiscPlayer/backend/instance
sqlite3 discplayer.db ".backup copia-discplayer.db"
```

Depois baixe `copia-discplayer.db` pela aba **Files** (ícone de download ao lado do arquivo). Faça isso de tempos em tempos: o plano gratuito não inclui backups.

---

## Problemas comuns

Primeiro de tudo, na aba **Web**, abra o **Error log** (e o **Server log**): quase sempre a causa aparece nas últimas linhas.

| Sintoma | Causa provável | O que fazer |
| --- | --- | --- |
| Página "Something went wrong :-(" | Erro ao iniciar o app | Leia o **Error log** |
| `ModuleNotFoundError` no log | Ambiente virtual não configurado ou dependências não instaladas | Confira o campo **Virtualenv** (3.7) e rode `pip install -r requirements.txt` (3.3) |
| `RuntimeError: Em produção, defina SECRET_KEY ...` | `.env` ausente, no lugar errado ou com a chave curta | O arquivo deve ser `/home/SEU_USUARIO/DiscPlayer/backend/.env`, com `SECRET_KEY=` de 32 caracteres ou mais. Depois, **Reload** |
| Site mostra texto "O front-end ainda não foi compilado" | A pasta `frontend/dist` não está no lugar | Confira `ls ~/DiscPlayer/frontend/dist/index.html` (3.5) |
| Tela em branco | `dist` incompleto (falta `assets`) | Reenvie o `dist.zip` e rode `unzip -o` de novo |
| Cria conta ou entra, mas "não pega" | Acesso por `http://` em vez de `https://`, ou **Force HTTPS** desligado | Ative **Force HTTPS** (3.7) e use sempre `https://` |
| Catálogo mostra "A integração com a RAWG não está configurada" | `RAWG_API_KEY` ausente ou não lida | Confira o `.env` e clique em **Reload** (o `.env` só é lido ao iniciar) |
| Catálogo mostra "A RAWG recusou a chave" | Chave errada | Corrija o `.env` e **Reload** |
| Catálogo mostra "A RAWG está indisponível" | Falha de rede ou da RAWG | Veja o **Error log**; tente de novo em alguns minutos. `api.rawg.io` está na lista de sites liberados do plano gratuito |
| "Muitas tentativas" com pouquíssimas pessoas | O IP real do visitante não está chegando ao app (todos parecem o mesmo) | Confira que o arquivo WSGI define `TRUSTED_PROXY_COUNT` como `1` (já vem no modelo). Como último recurso temporário, ponha `RATELIMIT_ENABLED=false` no `.env` e **Reload**: isso desliga a proteção contra tentativas em massa |
| O site sumiu depois de um tempo | O web app expirou (1 mês) | Aba **Web**: estenda a validade e clique em **Reload** |

Se travar, copie as últimas linhas do **Error log** e peça ajuda.
