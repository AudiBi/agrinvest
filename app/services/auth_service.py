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
    def generate_reset_token(email: str) -> str:
        """Génère un token de réinitialisation"""
        from itsdangerous import URLSafeTimedSerializer
        from flask import current_app
        
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return serializer.dumps(email, salt='password-reset-salt')
    
    @staticmethod
    def verify_reset_token(token: str, expiration: int = 3600) -> User:
        """Vérifie un token de réinitialisation"""
        from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
        from flask import current_app
        
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        
        try:
            email = serializer.loads(
                token,
                salt='password-reset-salt',
                max_age=expiration
            )
            return User.query.filter_by(email=email).first()
        except (SignatureExpired, BadSignature):
            return None
    
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