# DiscPlayer

[![CI](https://github.com/Murilo-Sousa/DiscPlayer/actions/workflows/ci.yml/badge.svg)](https://github.com/Murilo-Sousa/DiscPlayer/actions/workflows/ci.yml)

**O diário e a comunidade dos seus jogos.** Registre o que você joga, dê notas de 0 a 10, escreva reviews, monte listas e veja o que outras pessoas estão jogando. É a ideia do Letterboxd, só que para videogames.

Os dados dos jogos (nome, capa, gêneros, plataformas, datas) vêm da [RAWG](https://rawg.io). Todo o resto — contas, diário, notas, reviews, listas, seguidores — é da própria comunidade do DiscPlayer e fica no banco de dados do projeto. Nada na tela é inventado: um site novo mostra estados vazios que explicam como começar.

## Sumário

- [O que dá para fazer](#o-que-dá-para-fazer)
- [Tecnologias](#tecnologias)
- [Abrir no seu computador](#abrir-no-seu-computador)
- [Testes](#testes)
- [Como o projeto está organizado](#como-o-projeto-está-organizado)
- [Documentação](#documentação)
- [Limitações](#limitações)
- [Créditos e licenças](#créditos-e-licenças)

## O que dá para fazer

- **Explorar o catálogo** de jogos com busca por nome, filtros de gênero, plataforma e ano, e ordenação. Os filtros ficam no endereço, então dá para compartilhar a busca.
- **Manter um diário** com cinco status (*Quero jogar*, *Jogando*, *Zerado*, *Abandonado*, *Pausado*), datas de início e término, favoritos e histórico. **Jogar de novo** guarda a jogada anterior e começa outra.
- **Avaliar e escrever reviews** com nota de 0 a 10 em passos de 0,5. Quem escreve pode marcar **spoilers**: o texto fica escondido atrás de um aviso. Qualquer pessoa logada pode curtir reviews.
- **Montar listas**, públicas ou privadas, com os jogos na ordem que você quiser.
- **Ter um perfil público** com estatísticas calculadas dos seus registros reais, seguir outras pessoas e acompanhar o feed de quem você segue.
- **Buscar de tudo** no cabeçalho: jogos, pessoas, listas e reviews.
- **Gerenciar a conta**: foto de perfil enviada como imagem (o servidor valida, recorta e reduz) e exclusão da conta com confirmação por senha.
- **Usar no celular e pelo teclado**: interface responsiva e acessível.

Na página de cada jogo, a média das notas da comunidade DiscPlayer e a nota da RAWG aparecem em blocos separados, com a origem indicada. Elas nunca se misturam.

## Tecnologias

| Camada | O que usa |
| --- | --- |
| Front-end | React 19 e Vite 7, CSS próprio com variáveis, roteador sobre a History API |
| Back-end | Python 3.11+ e Flask 3.1 (API REST) |
| Banco de dados | SQLite com SQL puro e migrações em arquivos `.sql` |
| Dados de jogos | API da RAWG, sempre intermediada pelo back-end (a chave nunca chega ao navegador) |
| Testes | pytest, `node:test` e Playwright, rodando a cada alteração no GitHub Actions |

## Abrir no seu computador

O projeto tem duas partes que rodam ao mesmo tempo, cada uma no seu terminal: o **back-end** (a API, porta 5000) e o **front-end** (o site, porta 5173). Os comandos abaixo são do Windows com PowerShell; para o Prompt de Comando, macOS e Linux, veja os trechos recolhidos em cada passo.

### O que você precisa ter instalado

| Programa | Versão | Como conferir |
| --- | --- | --- |
| Python | 3.11 ou mais nova | `py --version` (Windows) ou `python3 --version` |
| Node.js (com npm) | 20.19 ou mais nova | `node --version` |
| Git (opcional) | qualquer | `git --version` |

Você também precisa de uma **chave gratuita da RAWG**: crie uma conta em <https://rawg.io/apidocs> e gere a chave. Ela fica só no seu computador.

> **Windows:** se você acabou de instalar o Python ou o Node.js, **feche o terminal (e o VS Code, se estiver usando) e abra de novo**. Terminais abertos antes da instalação não enxergam os programas novos.

### 1. Baixe o projeto

```powershell
git clone https://github.com/Murilo-Sousa/DiscPlayer.git
cd DiscPlayer
```

Sem o Git: na página do repositório no GitHub, clique em **Code** e depois em **Download ZIP**, extraia o arquivo e abra o terminal dentro da pasta extraída (a que tem as pastas `backend` e `frontend`).

### 2. Back-end (terminal 1)

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Quando o ambiente virtual está ativo, aparece `(.venv)` no começo da linha. Agora abra o arquivo `backend\.env` em um editor de texto e cole a sua chave depois do `=`, sem aspas nem espaços:

```
RAWG_API_KEY=cole-sua-chave-aqui
```

Depois suba a API:

```powershell
flask --app wsgi run --debug
```

Deve aparecer `Running on http://127.0.0.1:5000`. **Deixe esta janela aberta.** O banco de dados é criado sozinho na primeira vez, em `backend/instance/`.

<details>
<summary>Prompt de Comando (cmd), macOS ou Linux</summary>

Prompt de Comando:

```bat
cd backend
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
```

macOS ou Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Em todos os casos, edite o `.env` como acima e rode `flask --app wsgi run --debug`. No macOS, a porta 5000 costuma estar ocupada pelo AirPlay Receiver: veja o [guia de desenvolvimento](docs/desenvolvimento.md) para usar outra porta.

</details>

> **PowerShell:** se aparecer *"a execução de scripts foi desabilitada neste sistema"*, rode `Set-ExecutionPolicy -Scope Process Bypass` (vale só para aquela janela) e repita o comando.

### 3. Front-end (terminal 2)

Abra um **segundo terminal**, sem fechar o primeiro, na pasta `DiscPlayer`:

```powershell
cd frontend
npm install
npm run dev
```

O `npm install` demora um pouco na primeira vez. Quando aparecer `Local: http://localhost:5173/`, o site está no ar.

> **PowerShell:** se o `npm` reclamar de scripts desabilitados, rode `Set-ExecutionPolicy -Scope Process Bypass` e repita, ou use `npm.cmd install` e `npm.cmd run dev`.

### 4. Abra no navegador

Acesse **<http://localhost:5173>**. Para um primeiro passeio:

1. Clique em **Criar conta** (usuário com 3 a 24 letras minúsculas, números ou `_`; senha com pelo menos 8 caracteres).
2. Abra um jogo pelo catálogo, marque um status, dê uma nota e escreva uma review.
3. Crie uma lista e visite o seu perfil público (`/u/seu-usuario`).
4. Para ver o lado social, crie uma segunda conta em uma janela anônima, siga a primeira e curta a review dela.

Para encerrar, aperte **Ctrl+C** em cada terminal.

### Da próxima vez

Não precisa instalar nada de novo. Em cada terminal, na pasta `DiscPlayer`:

```powershell
# terminal 1
cd backend
.venv\Scripts\Activate.ps1
flask --app wsgi run --debug
```

```powershell
# terminal 2
cd frontend
npm run dev
```

Os seus dados ficam em `backend/instance/discplayer.db`, e continuam lá entre uma vez e outra.

### Depois de baixar novidades do projeto

Quando houver código novo (`git pull`), atualize as dependências e reinicie os dois terminais:

```powershell
git pull
cd backend
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Se o arquivo `frontend/package.json` mudou, rode também `npm install` na pasta `frontend`. As alterações no banco de dados são aplicadas sozinhas quando o back-end sobe.

### Sem chave da RAWG?

Dá para desenvolver sem chave usando um servidor local que imita a RAWG com **dados fictícios**, só para testar a interface. O passo a passo está no [guia de desenvolvimento](docs/desenvolvimento.md#desenvolver-sem-chave-da-rawg). Não use isso como catálogo de verdade.

### Deu algum erro?

| O que aparece | O que fazer |
| --- | --- |
| `flask: command not found` | O ambiente virtual não está ativo. Rode `.venv\Scripts\Activate.ps1` dentro de `backend` e tente de novo. |
| `npm` não é reconhecido | Instale o Node.js em [nodejs.org](https://nodejs.org), feche todos os terminais e abra outro. |
| `ModuleNotFoundError` | Com o ambiente virtual ativo, rode `pip install -r requirements.txt` dentro de `backend`. |
| O catálogo mostra que a RAWG não está configurada | Falta a chave em `backend/.env`. Salve o arquivo e reinicie o back-end. |
| O site abre, mas as chamadas à API falham | O back-end não está rodando. Confira o terminal 1. |
| Quero começar do zero | Pare o back-end e apague `backend/instance/discplayer.db*`. |

Outros casos, com mais detalhe, estão em [docs/solucao-de-problemas.md](docs/solucao-de-problemas.md).

## Testes

```powershell
# back-end (com o ambiente virtual ativo)
cd backend
pytest

# front-end
cd frontend
npm test
```

Os testes do back-end usam uma RAWG simulada e um banco temporário: não precisam de internet nem de chave. Há também testes de ponta a ponta que controlam um navegador de verdade (opcionais). O GitHub Actions roda tudo a cada alteração, e o resultado aparece no selo no topo desta página. Detalhes em [docs/testes.md](docs/testes.md).

## Como o projeto está organizado

```
DiscPlayer/
├── backend/                 # API em Flask
│   ├── app/                 # rotas, regras de negócio, segurança, cliente da RAWG
│   ├── migrations/          # alterações do banco, em arquivos .sql numerados
│   ├── tests/               # testes (pytest)
│   └── .env.example         # modelo das configurações
├── frontend/                # site em React + Vite
│   ├── src/                 # páginas, componentes, estilos
│   └── tests/               # testes
├── e2e/                     # testes de navegador (opcionais)
├── deploy/                  # modelo para hospedar na PythonAnywhere
└── docs/                    # documentação detalhada
```

## Documentação

| Documento | Do que trata |
| --- | --- |
| [Guia de desenvolvimento](docs/desenvolvimento.md) | Passo a passo completo para todos os sistemas, variáveis de ambiente, modo sem chave da RAWG |
| [Como funciona por dentro](docs/como-funciona.md) | Funcionalidades em detalhe, estrutura de pastas, banco de dados, rotas da API, segurança e as decisões de produto e de engenharia |
| [Testes](docs/testes.md) | As três suítes de testes e o que cada uma cobre |
| [Solução de problemas](docs/solucao-de-problemas.md) | Erros comuns e como resolver |
| [Produção e publicação](docs/producao.md) | Como rodar como servidor de verdade |
| [Hospedagem gratuita na PythonAnywhere](docs/hospedagem-pythonanywhere.md) | Colocar o código no GitHub e o site no ar, passo a passo |
| [Limitações e próximos passos](docs/limitacoes-e-proximos-passos.md) | O que ainda não existe e o que vem a seguir |

## Limitações

Em resumo, e com mais detalhe em [docs/limitacoes-e-proximos-passos.md](docs/limitacoes-e-proximos-passos.md):

- O projeto foi feito para **uma única instância** (SQLite, cache e limite de requisições na memória do processo).
- **Não há e-mails**: sem recuperação de senha, verificação de e-mail ou notificações.
- **Não há moderação** (denúncias, bloqueios). Planeje isso antes de abrir o cadastro ao público.
- A interface está **só em português do Brasil**.
- Se for publicar, leia os [Termos da RAWG](https://rawg.io/apidocs): o plano gratuito é para projetos pessoais, sem fins comerciais, e exige citar a RAWG como fonte.

## Créditos e licenças

- Código sob a licença **MIT** (arquivo `LICENSE`).
- Dados e imagens de jogos: [RAWG](https://rawg.io). O uso da API exige atribuição e respeito aos termos de uso deles.
- Fontes: **TeX Gyre Adventor** (GUST Font License) e **Lora** (SIL Open Font License). Autoria, licenças e links de origem estão em `frontend/src/assets/fonts/LICENSES.md`.
- Os jogos, capas e nomes do servidor fictício de desenvolvimento são inventados e existem só para testes.
