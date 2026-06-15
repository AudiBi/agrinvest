# app/utils/security.py
"""
Fonctions de sécurité pour AgriInvest Haïti
"""

import hashlib
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from flask import current_app
from datetime import datetime, timedelta


def hash_password(password):
    """
    Hash un mot de passe
    
    Args:
        password: Mot de passe en clair
    
    Returns:
        Hash du mot de passe
    """
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password(password, password_hash):
    """
    Vérifie un mot de passe
    
    Args:
        password: Mot de passe en clair
        password_hash: Hash stocké
    
    Returns:
        bool: True si correct
    """
    return check_password_hash(password_hash, password)


def generate_jwt_token(user_id, expires_in_hours=24):
    """
    Génère un token JWT
    
    Args:
        user_id: ID de l'utilisateur
        expires_in_hours: Durée de validité en heures
    
    Returns:
        Token JWT
    """
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=expires_in_hours),
        'iat': datetime.utcnow(),
        'jti': secrets.token_urlsafe(16)
    }
    
    secret_key = current_app.config.get('JWT_SECRET_KEY', current_app.config['SECRET_KEY'])
    return jwt.encode(payload, secret_key, algorithm='HS256')


def decode_jwt_token(token):
    """
    Décode un token JWT
    
    Args:
        token: Token JWT
    
    Returns:
        Payload du token ou None
    """
    try:
        secret_key = current_app.config.get('JWT_SECRET_KEY', current_app.config['SECRET_KEY'])
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def generate_csrf_token():
    """
    Génère un token CSRF
    
    Returns:
        Token CSRF
    """
    return secrets.token_urlsafe(32)


def sanitize_input(text):
    """
    Nettoie une entrée utilisateur
    
    Args:
        text: Texte à nettoyer
    
    Returns:
        Texte nettoyé
    """
    if not text:
        return text
    
    # Échapper les caractères dangereux
    import html
    text = html.escape(text)
    
    # Supprimer les caractères invisibles
    text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
    
    return text