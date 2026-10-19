"""Ponto de entrada.

Desenvolvimento:  flask --app wsgi run --debug
Produção:         waitress-serve --call wsgi:create_app
"""
from app import create_app

app = create_app()
