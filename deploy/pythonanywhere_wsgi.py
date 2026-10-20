"""Conteúdo do arquivo WSGI da PythonAnywhere (aba "Web" > "WSGI configuration file").

Este arquivo NÃO é usado pelo projeto: ele é um modelo para colar no painel da
PythonAnywhere. Troque SEU_USUARIO pelo seu nome de usuário de lá e cole TUDO no
lugar do conteúdo original do arquivo. O passo a passo está em
docs/hospedagem-pythonanywhere.md.
"""
import os
import sys

PROJETO = "/home/SEU_USUARIO/DiscPlayer/backend"
if PROJETO not in sys.path:
    sys.path.insert(0, PROJETO)

# Modo produção sempre ligado aqui, mesmo que alguém esqueça de pôr no .env.
os.environ.setdefault("APP_ENV", "production")
# A PythonAnywhere fica atrás de um balanceador de carga: com 1, o app lê o IP real
# do visitante (usado no limite de tentativas) em vez do IP interno do balanceador.
os.environ.setdefault("TRUSTED_PROXY_COUNT", "1")

# SECRET_KEY e RAWG_API_KEY vêm do arquivo backend/.env (que não vai para o GitHub).
from app import create_app  # noqa: E402

application = create_app()
