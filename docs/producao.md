# Produção e publicação

Como rodar o DiscPlayer como um servidor de verdade e como publicá-lo de graça na internet.

[← Voltar ao README](../README.md)

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
- Use **um único processo** do app por banco (ver [Limitações](limitacoes-e-proximos-passos.md#limitações-conhecidas)).

## Publicar de graça na internet (PythonAnywhere)

O GitHub guarda o código, mas **não executa** o DiscPlayer (o GitHub Pages só serve sites estáticos, e aqui há uma API Python e um banco SQLite). Para outras pessoas abrirem um link, o projeto precisa rodar em um servidor.

A opção gratuita que melhor combina com este projeto é a **PythonAnywhere**: ela roda Flask, guarda os arquivos (o banco SQLite não se perde), oferece HTTPS e libera o acesso a `api.rawg.io` no plano gratuito. O guia completo, com o código no GitHub e o passo a passo do painel, está em **[hospedagem-pythonanywhere.md](hospedagem-pythonanywhere.md)**, e o modelo do arquivo WSGI está em `deploy/pythonanywhere_wsgi.py`.

Limites do plano gratuito (conferidos em 17/10/2026; confirme na PythonAnywhere): 1 web app com 1 processo, 512 MiB de disco, endereço `seunome.pythonanywhere.com` e **validade de 1 mês, que você precisa estender manualmente**. Outras hospedagens gratuitas populares (como o plano grátis do Render) usam disco temporário e **apagariam o banco** a cada reinício, por isso não servem para este projeto sem trocar o SQLite por um banco externo.

Antes de abrir o site ao público, leia os [Termos da RAWG](https://rawg.io/apidocs) (o plano gratuito é para projetos pessoais e sem fins comerciais, com link de volta para a RAWG) e as [Limitações conhecidas](limitacoes-e-proximos-passos.md#limitações-conhecidas).
