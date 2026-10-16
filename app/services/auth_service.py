"""
Service d'authentification unifié pour API et Web
"""

from flask_login import login_user
from app.models import User
from app.extensions import db
from app.utils.validators import *
from datetime import datetime, timezone
import re


def utc_now():
    return datetime.now(timezone.utc)


class AuthService:
    """Service centralisé d'authentification"""
    
    @staticmethod
    def authenticate_user(email: str, password: str, remember: bool = False) -> dict:
        """
        Authentifie un utilisateur
        Retourne: {'success': bool, 'user': User, 'error': str}
        """
        # Validation email
        if not validate_email(email):
            return {'success': False, 'error': 'Email invalide', 'user': None}
        
        # Validation password (format)
        if not password or len(password) < 1:
            return {'success': False, 'error': 'Mot de passe requis', 'user': None}
        
        # Recherche utilisateur
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            # Mesure anti-bruteforce (logging)
            AuthService._log_failed_attempt(email)
            return {'success': False, 'error': 'Email ou mot de passe invalide', 'user': None}
        
        # Vérification compte actif
        if not user.is_active:
            return {'success': False, 'error': 'Compte désactivé. Contactez l\'administrateur.', 'user': None}
        
        # Connexion réussie
        login_user(user, remember=remember)
        user.last_login_at = utc_now()
        db.session.commit()
        
        return {'success': True, 'user': user, 'error': None}
    
    @staticmethod
    def _log_failed_attempt(email: str):
        """Log les tentatives échouées pour détection brute force"""
        from flask import current_app
        current_app.logger.warning(f"Échec de connexion pour l'email: {email}")
    
    @staticmethod
    def validate_credentials(email: str, password: str) -> tuple:
        """Valide les credentials sans connexion"""
        if not validate_email(email):
            return False, "Format d'email invalide"
        
        if not password or len(password) < 8:
            return False, "Le mot de passe doit contenir au moins 8 caractères"
        
        user = User.query.filter_by(email=email).first()
        if not user:
            return False, "Email non trouvé"
        
        if not user.check_password(password):
            return False, "Mot de passe incorrect"
        
        if not user.is_active:
            return False, "Compte désactivé"
        
        return True, user
    
    @staticmethod
    def _serializer():
        from itsdangerous import URLSafeTimedSerializer
        from flask import current_app
        return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

    @staticmethod
    def _password_fingerprint(user: User) -> str:
        import hashlib
        return hashlib.sha256((user.password_hash or '').encode()).hexdigest()[:16]

    @staticmethod
    def generate_reset_token(email: str) -> str:
        """Génère un token de réinitialisation, lié au mot de passe actuel (donc à usage unique)"""
        user = User.query.filter_by(email=email).first()
        fingerprint = AuthService._password_fingerprint(user) if user else ''
        return AuthService._serializer().dumps([email, fingerprint], salt='password-reset-salt')

    @staticmethod
    def verify_reset_token(token: str, expiration: int = 3600) -> User:
        """Vérifie un token de réinitialisation (expiré, falsifié ou déjà utilisé -> None)"""
        from itsdangerous import SignatureExpired, BadSignature

        try:
            email, fingerprint = AuthService._serializer().loads(
                token, salt='password-reset-salt', max_age=expiration)
        except (SignatureExpired, BadSignature, TypeError, ValueError):
            return None
        user = User.query.filter_by(email=email).first()
        if not user or fingerprint != AuthService._password_fingerprint(user):
            return None  # le mot de passe a changé depuis l'émission du lien
        return user

    @staticmethod
    def generate_email_token(email: str) -> str:
        """Token de vérification d'adresse email"""
        return AuthService._serializer().dumps(email, salt='email-verify-salt')

    @staticmethod
    def verify_email_token(token: str, expiration: int = 86400 * 3) -> User:
        from itsdangerous import SignatureExpired, BadSignature

        try:
            email = AuthService._serializer().loads(token, salt='email-verify-salt', max_age=expiration)
        except (SignatureExpired, BadSignature):
            return None
        return User.query.filter_by(email=email).first()

    @staticmethod
    def reset_password(token: str, new_password: str) -> bool:
        """Réinitialise le mot de passe"""
        if not validate_password(new_password):
            return False
        
        user = AuthService.verify_reset_token(token)
        if not user:
            return False
        
        user.set_password(new_password)
        db.session.commit()
        return True