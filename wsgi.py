"""Point d'entrée WSGI de production : gunicorn wsgi:app"""
from app import create_app

app = create_app()
