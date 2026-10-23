# Testes

Como rodar as três suítes do projeto (back-end, front-end e navegador) e o que cada uma cobre.

[← Voltar ao README](../README.md)

## Back-end (pytest)

```bash
cd backend
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pytest
```

Os testes usam um banco temporário por teste e **uma RAWG simulada** (`tests/fake_rawg.py`): não gastam cota da API, não precisam de internet nem de chave. Cobrem autenticação e sessão, CSRF, diário, jogar de novo, reviews e spoilers, listas, social, busca, envio e reprocessamento de fotos (arquivos falsos, bombas de descompressão, metadados), exclusão de conta (remoção completa e cookies de contas apagadas), o cliente da RAWG (cache, falhas, dados incompletos), integridade e migração do banco e cabeçalhos de segurança.

## Front-end

```bash
cd frontend
npm test
```

A suíte usa o executor nativo do Node (`node:test`) com esbuild (que já vem junto do Vite) para compilar JSX, e renderiza os componentes no servidor com `react-dom/server`. Cobre formatação, roteador, cliente HTTP (CSRF, repetição, erros de rede), componentes (nota em discos, escape de texto, rótulos de formulário, paginação, abas, histograma) e a proteção contra redirecionamento aberto no login. Não usa Vitest nem jsdom; não há testes de interação de componentes além dos de navegador, abaixo.

## Ponta a ponta no navegador (opcional)

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

## Integração contínua

O workflow `.github/workflows/ci.yml` roda a cada push na `main` e em todo Pull Request: o back-end em Python 3.11 e 3.13, o front-end (`npm ci`, `npm test` e `npm run build`) e o teste de ponta a ponta com Chromium, usando o build recém-gerado. O resultado aparece na aba **Actions** do repositório e no selo no topo do README.
