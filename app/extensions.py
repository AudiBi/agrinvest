# app/extensions.py
"""
Extensions Flask pour AgriInvest Haïti
Centralise toutes les extensions utilisées par l'application
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery import Celery
import redis
from datetime import timedelta

# ============================================================================
# INITIALISATION DES EXTENSIONS
# ============================================================================

# Base de données
db = SQLAlchemy()

# Migrations
migrate = Migrate()

# Gestion des sessions utilisateur
login_manager = LoginManager()

# Emails
mail = Mail()

# CORS (Cross-Origin Resource Sharing)
cors = CORS()

# Protection CSRF
csrf = CSRFProtect()

# Cache (Redis)
cache = Cache()

# Rate Limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
)

# File d'attente (Celery)
celery = Celery()


# ============================================================================
# CONFIGURATION DE LOGIN MANAGER
# ============================================================================

@login_manager.user_loader
def load_user(user_id):
    """Charge un utilisateur à partir de son ID"""
    from app.models import User
    return db.session.get(User, int(user_id))


# ============================================================================
# FONCTIONS D'INITIALISATION
# ============================================================================

def init_extensions(app):
    """
    Initialise toutes les extensions avec l'application Flask
    """
    # Extensions de base
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    cors.init_app(app)
    csrf.init_app(app)
    
    # Configuration de login
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page'
    login_manager.login_message_category = 'warning'
    login_manager.session_protection = 'strong'
    
    # Cache (Redis)
    if app.config.get('CACHE_TYPE'):
        cache.init_app(app, config={
            'CACHE_TYPE': app.config.get('CACHE_TYPE', 'SimpleCache'),
            'CACHE_REDIS_URL': app.config.get('REDIS_URL', 'redis://localhost:6379/0'),
            'CACHE_DEFAULT_TIMEOUT': app.config.get('CACHE_DEFAULT_TIMEOUT', 300)
        })
    else:
        cache.init_app(app, config={'CACHE_TYPE': 'SimpleCache'})
    
    # Rate Limiting
    limiter.init_app(app)
    
    # Celery
    celery.conf.update(app.config)
    
    return app


# ============================================================================
# FONCTIONS UTILITAIRES POUR LES EXTENSIONS
# ============================================================================

def get_redis_client():
    """
    Retourne un client Redis configuré
    """
    try:
        from flask import current_app
        redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        return redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        print(f"Erreur de connexion Redis: {e}")
        return None


def clear_cache():
    """
    Vide tout le cache (utile après des modifications majeures)
    """
    try:
        cache.clear()
        redis_client = get_redis_client()
        if redis_client:
            redis_client.flushdb()
        return True
    except Exception as e:
        print(f"Erreur lors du nettoyage du cache: {e}")
        return False


def get_cache_stats():
    """
    Retourne les statistiques du cache
    """
    try:
        redis_client = get_redis_client()
        if redis_client:
            info = redis_client.info()
            return {
                'connected': True,
                'used_memory': info.get('used_memory_human', 'N/A'),
                'total_keys': redis_client.dbsize(),
                'hit_rate': info.get('keyspace_hits_ratio', 0)
            }
        return {'connected': False, 'error': 'Redis non disponible'}
    except Exception as e:
        return {'connected': False, 'error': str(e)}


# ============================================================================
# DÉCORATEURS PERSONNALISÉS POUR LES EXTENSIONS
# ============================================================================

def rate_limit(limit, per=3600, methods=None):
    """
    Décorateur pour appliquer une limite de taux personnalisée
    
    Usage:
        @bp.route('/api/login', methods=['POST'])
        @rate_limit(limit=10, per=60)
        def login():
            ...
    """
    def decorator(f):
        return limiter.limit(f"{limit} per {per} seconds", methods=methods)(f)
    return decorator


def _login_email_key():
    """Clé de limitation par compte ciblé (corps JSON ou formulaire)."""
    from flask import request
    payload = request.get_json(silent=True) or {}
    email = (payload.get('email') or request.form.get('email') or '').strip().lower()
    return f"login:{email}" if email else get_remote_address()


def login_throttle(f):
    """Limite les tentatives de connexion : par IP ET par compte visé (anti brute-force distribué)."""
    f = limiter.limit("10 per hour", key_func=_login_email_key, methods=["POST"])(f)
    return limiter.limit("20 per hour", methods=["POST"])(f)


def cached(timeout=300, key_prefix=None):
    """
    Décorateur pour mettre en cache une réponse
    
    Usage:
        @bp.route('/api/projects')
        @cached(timeout=600)
        def get_projects():
            ...
    """
    def decorator(f):
        return cache.cached(timeout=timeout, key_prefix=key_prefix)(f)
    return decorator


# ============================================================================
# CLASSES POUR LA GESTION DES FICHIERS
# ============================================================================

class FileUpload:
    """
    Gestionnaire d'upload de fichiers
    """
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}
    MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB
    
    @staticmethod
    def allowed_file(filename):
        """Vérifie si le type de fichier est autorisé"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in FileUpload.ALLOWED_EXTENSIONS
    
    @staticmethod
    def get_file_size(file):
        """Retourne la taille du fichier en octets"""
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        return size
    
    @staticmethod
    def validate_file(file):
        """Valide un fichier avant upload"""
        if not file or file.filename == '':
            return False, "Aucun fichier sélectionné"
        
        if not FileUpload.allowed_file(file.filename):
            return False, "Type de fichier non autorisé"
        
        if FileUpload.get_file_size(file) > FileUpload.MAX_FILE_SIZE:
            return False, "Fichier trop volumineux (max 16 MB)"
        
        return True, "OK"


# ============================================================================
# CONFIGURATION POUR DIFFÉRENTS ENVIRONNEMENTS
# ============================================================================

class ExtensionsConfig:
    """Configuration des extensions par environnement"""
    
    @staticmethod
    def configure_for_development(app):
        """Configuration pour le développement"""
        app.config['CACHE_TYPE'] = 'SimpleCache'
        app.config['CACHE_DEFAULT_TIMEOUT'] = 60
        app.config['RATELIMIT_ENABLED'] = False
        app.config['RATELIMIT_STORAGE_URL'] = 'memory://'
    
    @staticmethod
    def configure_for_testing(app):
        """Configuration pour les tests"""
        app.config['CACHE_TYPE'] = 'SimpleCache'
        app.config['CACHE_NO_NULL_WARNING'] = True
        app.config['RATELIMIT_ENABLED'] = False
        app.config['WTF_CSRF_ENABLED'] = False
    
    @staticmethod
    def configure_for_production(app):
        """Configuration pour la production"""
        app.config['CACHE_TYPE'] = 'RedisCache'
        app.config['CACHE_REDIS_URL'] = app.config.get('REDIS_URL')
        app.config['CACHE_DEFAULT_TIMEOUT'] = 300
        app.config['RATELIMIT_ENABLED'] = True
        app.config['RATELIMIT_STORAGE_URL'] = app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        app.config['RATELIMIT_STRATEGY'] = 'fixed-window'
        app.config['RATELIMIT_HEADERS_ENABLED'] = True


# ============================================================================
# FONCTIONS DE NETTOYAGE
# ============================================================================

def cleanup_expired_sessions():
    """
    Nettoie les sessions expirées (à appeler périodiquement)
    """
    try:
        redis_client = get_redis_client()
        if redis_client:
            # Nettoyer les clés de session expirées
            keys = redis_client.keys('session:*')
            for key in keys:
                if not redis_client.ttl(key):
                    redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Erreur lors du nettoyage des sessions: {e}")
        return False


def flush_rate_limits():
    """
    Vide toutes les limites de taux
    """
    try:
        redis_client = get_redis_client()
        if redis_client:
            keys = redis_client.keys('rate-limit:*')
            for key in keys:
                redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Erreur lors du nettoyage des limites: {e}")
        return False


# ============================================================================
# INITIALISATION AVEC L'APPLICATION
# ============================================================================

def init_app(app):
    """
    Initialise toutes les extensions avec l'application Flask
    Cette fonction est appelée dans create_app()
    """
    # Configurer les extensions selon l'environnement
    if app.config.get('DEBUG'):
        ExtensionsConfig.configure_for_development(app)
    elif app.config.get('TESTING'):
        ExtensionsConfig.configure_for_testing(app)
    else:
        ExtensionsConfig.configure_for_production(app)
    
    # Initialiser toutes les extensions
    init_extensions(app)
    
    # Configurer CORS avec les origines autorisées
    cors.init_app(app, resources={
        r"/api/*": {
            "origins": app.config.get('CORS_ORIGINS', '*'),
            "supports_credentials": True,
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["X-Total-Count", "X-Page"]
        }
    })
    
    # Configurer CSRF protection
    csrf.init_app(app)
    
    return app