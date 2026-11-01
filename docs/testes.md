# Testes

Como rodar as três suítes do projeto (back-end, front-end e navegador) e o que cada uma cobre.

[← Voltar ao README](../README.md)

## Back-end (pytest)

```bash
cd backend
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pytest
```

Os testes usam um banco temporário por teste e **uma RAWG simulada** (`tests/fake_rawg.py`): não gastam cota da API, não precisam de internet nem de chave. Cobrem autenticação e sessão, CSRF, diário, as regras de cada status (datas, favorito, nota, jogo não lançado, a migração dos dados antigos e mil ações sorteadas que nunca podem deixar uma combinação sem sentido no banco), jogar de novo, reviews e spoilers, listas, social, busca, envio e reprocessamento de fotos (arquivos falsos, bombas de descompressão, metadados), exclusão de conta (remoção completa e cookies de contas apagadas), os perfis de exemplo (marcação, login recusado, regras do diário, remoção sem tocar nas contas reais, recusa em produção sem `--sim`), o cliente da RAWG (cache, falhas, dados incompletos), integridade e migração do banco, cabeçalhos de segurança, a retrospectiva do ano (limites do ano, jogadas anteriores, jogo do ano, ritmo, privacidade), a prévia de links (tags por tipo de endereço, escape de HTML, listas privadas, falha da RAWG, `PUBLIC_URL`, limite de requisições) o ranking com mínimo de três notas, a média da comunidade nas listas (sem poluir o cache da RAWG), a consulta de status do diário por lista de jogos (login, formato e limite dos ids), o atalho de guardar na fila (`create_only` não muda jogo que já está no diário), os jogos do mesmo gênero (sem o próprio jogo, com a RAWG fora do ar) e as imagens de compartilhamento (PNG válido, cache pelos dados, nomes e bios em qualquer alfabeto, texto longo demais para a linha, foto corrompida, Pillow ausente, resposta sem cookie).

## Front-end

```bash
cd frontend
npm test
```

A suíte usa o executor nativo do Node (`node:test`) com esbuild (que já vem junto do Vite) para compilar JSX, e renderiza os componentes no servidor com `react-dom/server`. Cobre formatação, roteador, cliente HTTP (CSRF, repetição, erros de rede), componentes (nota em discos, escape de texto, rótulos de formulário, paginação, abas, histograma), as regras do diário (o que o painel mostra em cada status, a nota trancada, status bloqueados com o motivo), o disco interativo da página inicial (o que ele promete para cada status segue as mesmas regras) e a marca de perfil de exemplo a proteção contra redirecionamento aberto no login, a página da retrospectiva (números, anos, estados vazios, escape de texto) o compartilhamento do endereço (menu do aparelho, cópia e falhas) e o catálogo repaginado (prateleiras só sem filtro, chips de gênero com `aria-pressed`, painel de filtros e a contagem no botão, chips dos filtros ativos, média da comunidade e o botão "+" nos cards, a barra fixa de status e a prateleira de jogos do gênero). Não usa Vitest nem jsdom; não há testes de interação de componentes além dos de navegador, abaixo.

## Ponta a ponta no navegador (opcional)

Sobem o Flask de verdade, com banco temporário e a RAWG fictícia, e controlam um Chromium real: a página inicial de quem ainda não entrou (o disco interativo, a nota em discos, os perfis de exemplo e o celular sem rolagem lateral), cadastro, status (e o que cada um mostra e permite), nota, review, lista, diário, perfil, seguir, curtir, feed, privacidade de lista, validação e CSRF no servidor, teclado, celular sem rolagem horizontal as datas automáticas do diário no fuso de quem joga, o comportamento com a RAWG fora do ar, o visual das telas redesenhadas (a colagem de capas das listas dentro da caixa, a prateleira e a fila da página inicial, o ranking que só aparece com três notas, favoritos e última review lado a lado no perfil, a retrospectiva em duas colunas no computador e uma no celular, a imagem de fundo do jogo sem atrapalhar cliques, sem rolagem horizontal), a retrospectiva (navegação entre anos, compartilhar, imagem baixada e celular) o HTML que um robô lê (tags de prévia de jogo, perfil, lista e retrospectiva, sem vazar lista privada) e o catálogo repaginado (prateleiras e busca, chip de gênero na URL, painel de filtros, média da comunidade nos cards, o atalho "+" para a fila, inclusive quando o jogo entrou no diário em outra aba, a prateleira "Mais em <gênero>" na página do jogo e a barra fixa de status no celular, que não existe no computador).

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

## Integração contínua

O workflow `.github/workflows/ci.yml` roda a cada push na `main` e em todo Pull Request: o back-end em Python 3.11 e 3.13, o front-end (`npm ci`, `npm test` e `npm run build`) e o teste de ponta a ponta com Chromium, usando o build recém-gerado. O resultado aparece na aba **Actions** do repositório e no selo no topo do README.
