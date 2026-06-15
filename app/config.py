import os
from datetime import timedelta
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Configuration de base (commune à tous les environnements)"""

    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')

    # =========================================================================
    # BASE DE DONNÉES
    # =========================================================================
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(basedir, "..", "instance", "agrinvest.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }

    # =========================================================================
    # SÉCURITÉ
    # =========================================================================
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    
    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    
    # Rate Limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # =========================================================================
    # EMAIL (Flask-Mail)
    # =========================================================================
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@agrinvest.com')
    MAIL_MAX_EMAILS = 50
    MAIL_ASCII_ATTACHMENTS = False

    # =========================================================================
    # UPLOADS & FICHIERS
    # =========================================================================
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max
    UPLOAD_FOLDER = os.path.join(basedir, '..', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp4', 'mp3', 'ogg'}
    
    # Images
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
    IMAGE_QUALITY = 85
    IMAGE_THUMBNAIL_SIZE = (300, 300)
    IMAGE_MEDIUM_SIZE = (800, 600)
    IMAGE_LARGE_SIZE = (1200, 900)

    # =========================================================================
    # PAIEMENTS - STRIPE
    # =========================================================================
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', '')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    STRIPE_API_VERSION = '2023-10-16'
    
    # Stripe Connect (pour les virements vers Haïti)
    STRIPE_CONNECT_CLIENT_ID = os.environ.get('STRIPE_CONNECT_CLIENT_ID', '')
    STRIPE_CONNECT_WEBHOOK_SECRET = os.environ.get('STRIPE_CONNECT_WEBHOOK_SECRET', '')
    
    # =========================================================================
    # PAIEMENTS - PAYPAL
    # =========================================================================
    PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID', '')
    PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET', '')
    PAYPAL_MODE = os.environ.get('PAYPAL_MODE', 'sandbox')  # 'sandbox' or 'live'
    PAYPAL_WEBHOOK_ID = os.environ.get('PAYPAL_WEBHOOK_ID', '')
    
    # =========================================================================
    # PAIEMENTS - MONCASH (Haïti)
    # =========================================================================
    MONCASH_CLIENT_ID = os.environ.get('MONCASH_CLIENT_ID', '')
    MONCASH_CLIENT_SECRET = os.environ.get('MONCASH_CLIENT_SECRET', '')
    MONCASH_ENVIRONMENT = os.environ.get('MONCASH_ENVIRONMENT', 'sandbox')  # 'sandbox' or 'production'
    MONCASH_API_URL = os.environ.get('MONCASH_API_URL', 'https://sandbox.moncashapi.com/v1')
    MONCASH_WEBHOOK_SECRET = os.environ.get('MONCASH_WEBHOOK_SECRET', '')
    
    # =========================================================================
    # PAIEMENTS - INTERAC (Canada)
    # =========================================================================
    INTERAC_API_KEY = os.environ.get('INTERAC_API_KEY', '')
    INTERAC_API_SECRET = os.environ.get('INTERAC_API_SECRET', '')
    INTERAC_ENVIRONMENT = os.environ.get('INTERAC_ENVIRONMENT', 'sandbox')
    
    # =========================================================================
    # PAIEMENTS - LYDIA (France)
    # =========================================================================
    LYDIA_CLIENT_ID = os.environ.get('LYDIA_CLIENT_ID', '')
    LYDIA_CLIENT_SECRET = os.environ.get('LYDIA_CLIENT_SECRET', '')
    LYDIA_ENVIRONMENT = os.environ.get('LYDIA_ENVIRONMENT', 'sandbox')
    
    # =========================================================================
    # TRANSFERTS INTERNATIONAUX
    # =========================================================================
    # Wise (ex-TransferWise)
    WISE_API_KEY = os.environ.get('WISE_API_KEY', '')
    WISE_API_URL = os.environ.get('WISE_API_URL', 'https://api.transferwise.com')
    WISE_PROFILE_ID = os.environ.get('WISE_PROFILE_ID', '')
    WISE_WEBHOOK_SECRET = os.environ.get('WISE_WEBHOOK_SECRET', '')
    
    # Western Union
    WESTERN_UNION_API_KEY = os.environ.get('WESTERN_UNION_API_KEY', '')
    WESTERN_UNION_API_SECRET = os.environ.get('WESTERN_UNION_API_SECRET', '')
    
    # Remitly
    REMITLY_API_KEY = os.environ.get('REMITLY_API_KEY', '')
    
    # =========================================================================
    # REDIS / CELERY (File d'attente)
    # =========================================================================
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'America/Port-au-Prince'
    CELERY_ENABLE_UTC = True
    CELERY_TASK_TRACK_STARTED = True
    CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
    CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
    CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
    CELERY_WORKER_PREFETCH_MULTIPLIER = 1
    
    # =========================================================================
    # MÉTÉO & ALERTES
    # =========================================================================
    # OpenWeatherMap
    OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', '')
    OPENWEATHER_API_URL = 'https://api.openweathermap.org/data/2.5'
    
    # NOAA (National Hurricane Center - pour les cyclones)
    NOAA_API_URL = 'https://api.weather.gov'
    
    # CNIGS Haïti
    CNIGS_API_URL = os.environ.get('CNIGS_API_URL', '')
    CNIGS_API_KEY = os.environ.get('CNIGS_API_KEY', '')
    
    # MARNDR (Ministère Agriculture Haïti)
    MARNDR_API_URL = os.environ.get('MARNDR_API_URL', '')
    
    # =========================================================================
    # SMS & WHATSAPP
    # =========================================================================
    # Twilio
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')
    TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER', '')
    
    # Digicel Haïti (SMS)
    DIGICEL_SMS_API_KEY = os.environ.get('DIGICEL_SMS_API_KEY', '')
    DIGICEL_SMS_API_URL = os.environ.get('DIGICEL_SMS_API_URL', 'https://api.digicelgroup.com/sms/v1')
    
    # =========================================================================
    # TAUX DE CHANGE
    # =========================================================================
    EXCHANGE_RATE_API_KEY = os.environ.get('EXCHANGE_RATE_API_KEY', '')
    EXCHANGE_RATE_API_URL = 'https://api.exchangerate-api.com/v4/latest'
    EXCHANGE_RATE_CACHE_TTL = 3600  # 1 heure
    DEFAULT_CURRENCY = 'HTG'
    SUPPORTED_CURRENCIES = ['HTG', 'USD', 'EUR', 'CAD']
    
    # =========================================================================
    # COMMISSIONS PLATEFORME (CEO)
    # =========================================================================
    DEFAULT_PLATFORM_COMMISSION = 3.0  # 3%
    CEO_COMMISSION_RANGE = (2.0, 5.0)  # Entre 2% et 5%
    COMMISSION_PAYOUT_DAY = 1  # Paiement le 1er du mois
    MIN_PAYOUT_AMOUNT = 10000  # Montant minimum en HTG pour un virement au CEO
    
    # =========================================================================
    # CACHING
    # =========================================================================
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'RedisCache')
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes
    CACHE_KEY_PREFIX = 'agrinvest_'
    
    # =========================================================================
    # PAGINATION
    # =========================================================================
    ITEMS_PER_PAGE = 20
    PROJECTS_PER_PAGE = 12
    CONTRIBUTIONS_PER_PAGE = 50
    MESSAGES_PER_PAGE = 30
    
    # =========================================================================
    # JWT (pour l'API mobile)
    # =========================================================================
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ['headers', 'cookies']
    JWT_COOKIE_SECURE = SESSION_COOKIE_SECURE
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_COOKIE_SAMESITE = 'Lax'
    
    # =========================================================================
    # CORS (Cross-Origin Resource Sharing)
    # =========================================================================
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:5000,https://agrinvest.ht')
    CORS_SUPPORTS_CREDENTIALS = True
    
    # =========================================================================
    # LOGGING
    # =========================================================================
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.path.join(basedir, '..', 'logs', 'agrinvest.log')
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT = 10
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # =========================================================================
    # SENTRY (Monitoring erreurs)
    # =========================================================================
    SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
    SENTRY_ENVIRONMENT = os.environ.get('FLASK_ENV', 'development')
    SENTRY_TRACES_SAMPLE_RATE = 1.0
    
    # =========================================================================
    # GOOGLE SERVICES
    # =========================================================================
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    GOOGLE_RECAPTCHA_SITE_KEY = os.environ.get('GOOGLE_RECAPTCHA_SITE_KEY', '')
    GOOGLE_RECAPTCHA_SECRET_KEY = os.environ.get('GOOGLE_RECAPTCHA_SECRET_KEY', '')
    
    # =========================================================================
    # MÉDIAS SOCIAUX
    # =========================================================================
    FACEBOOK_APP_ID = os.environ.get('FACEBOOK_APP_ID', '')
    FACEBOOK_APP_SECRET = os.environ.get('FACEBOOK_APP_SECRET', '')
    WHATSAPP_BUSINESS_API_KEY = os.environ.get('WHATSAPP_BUSINESS_API_KEY', '')
    WHATSAPP_BUSINESS_PHONE_ID = os.environ.get('WHATSAPP_BUSINESS_PHONE_ID', '')
    
    # =========================================================================
    # STOCKAGE CLOUD (pour les images)
    # =========================================================================
    CLOUD_STORAGE_PROVIDER = os.environ.get('CLOUD_STORAGE_PROVIDER', 'local')  # 'local', 's3', 'cloudinary'
    
    # AWS S3
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
    AWS_S3_BUCKET_NAME = os.environ.get('AWS_S3_BUCKET_NAME', '')
    AWS_S3_REGION = os.environ.get('AWS_S3_REGION', 'us-east-1')
    AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN', '')
    
    # Cloudinary
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')
    
    # =========================================================================
    # CERTIFICATS FISCAUX (USA 501(c)(3))
    # =========================================================================
    TAX_RECEIPT_ORGANIZATION_NAME = os.environ.get('TAX_RECEIPT_ORGANIZATION_NAME', 'AgriInvest Haiti Foundation')
    TAX_RECEIPT_ORGANIZATION_EIN = os.environ.get('TAX_RECEIPT_ORGANIZATION_EIN', '')
    TAX_RECEIPT_ADDRESS = os.environ.get('TAX_RECEIPT_ADDRESS', '')
    TAX_RECEIPT_WEBSITE = os.environ.get('TAX_RECEIPT_WEBSITE', 'https://agrinvest.ht')
    
    # =========================================================================
    # LIMITES & SEUILS
    # =========================================================================
    MAX_PROJECT_TITLE_LENGTH = 200
    MAX_USER_NAME_LENGTH = 100
    MAX_CONTRIBUTION_MESSAGE_LENGTH = 500
    MIN_CONTRIBUTION_AMOUNT = 100  # 100 HTG minimum
    MAX_CONTRIBUTION_AMOUNT = 10000000  # 10M HTG maximum
    
    # Seuils pour les alertes
    DAILY_CONTRIBUTION_LIMIT = 1000000  # 1M HTG par jour (sécurité)
    MAX_PROJECTS_PER_FARMER = 10
    MAX_ACTIVE_CONTRIBUTIONS_PER_USER = 50
    
    # =========================================================================
    # FORMATION & CONTENU
    # =========================================================================
    MAX_TRAINING_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    ALLOWED_TRAINING_TYPES = ['audio', 'video_low', 'text', 'pdf', 'whatsapp']
    TRAINING_VIDEO_MAX_DURATION = 3600  # 1 heure
    TRAINING_AUDIO_MAX_DURATION = 1800  # 30 minutes
    
    # =========================================================================
    # CACHES SPECIFIQUES
    # =========================================================================
    PROJECT_CACHE_TIMEOUT = 300  # 5 minutes
    USER_CACHE_TIMEOUT = 600  # 10 minutes
    WEATHER_CACHE_TIMEOUT = 1800  # 30 minutes
    EXCHANGE_RATE_CACHE_TIMEOUT = 3600  # 1 heure
    
    # =========================================================================
    # WEBHOOKS
    # =========================================================================
    WEBHOOK_MAX_RETRIES = 3
    WEBHOOK_RETRY_DELAY = 60  # secondes
    WEBHOOK_TIMEOUT = 30  # secondes


class DevelopmentConfig(Config):
    """Configuration pour le développement"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    
    # Désactiver certaines sécurités pour le développement
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    
    # Logging plus détaillé
    LOG_LEVEL = 'DEBUG'
    
    # Utiliser SQLite en développement
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(basedir, "..", "instance", "agrinvest_dev.db")}'
    )
    
    # Mode test pour les paiements
    STRIPE_PUBLIC_KEY = 'pk_test_...'
    PAYPAL_MODE = 'sandbox'
    MONCASH_ENVIRONMENT = 'sandbox'
    
    # Cache plus court pour le développement
    CACHE_DEFAULT_TIMEOUT = 60
    PROJECT_CACHE_TIMEOUT = 30
    
    # URL de base pour le développement
    BASE_URL = 'http://localhost:5000'
    API_BASE_URL = 'http://localhost:5000/api'


class TestingConfig(Config):
    """Configuration pour les tests unitaires"""
    TESTING = True
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    
    # Base de données en mémoire
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_size': 5}
    
    # Désactiver les services externes
    REDIS_URL = 'redis://localhost:6379/1'
    
    # Logging minimal
    LOG_LEVEL = 'ERROR'
    
    # Emails en mode test
    MAIL_SUPPRESS_SEND = True
    
    # Uploads temporaires
    UPLOAD_FOLDER = '/tmp/agrinvest_test'
    
    # Cache en mémoire pour les tests
    CACHE_TYPE = 'SimpleCache'
    
    # URL de base pour les tests
    BASE_URL = 'http://localhost:5000'
    API_BASE_URL = 'http://localhost:5000/api'
    
    # Désactiver les webhooks en test
    WEBHOOK_MAX_RETRIES = 0


class StagingConfig(Config):
    """Configuration pour l'environnement de pré-production"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    
    # Logging modéré
    LOG_LEVEL = 'INFO'
    
    # Mode test pour les paiements
    PAYPAL_MODE = 'sandbox'
    MONCASH_ENVIRONMENT = 'sandbox'
    
    # Sentry en staging
    SENTRY_ENVIRONMENT = 'staging'
    SENTRY_TRACES_SAMPLE_RATE = 0.5
    
    # URL de base
    BASE_URL = os.environ.get('BASE_URL', 'https://staging.agrinvest.ht')
    API_BASE_URL = f'{BASE_URL}/api'


class ProductionConfig(Config):
    """Configuration pour la production"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    
    # Forcer HTTPS
    PREFERRED_URL_SCHEME = 'https'
    
    # Logging en production
    LOG_LEVEL = 'WARNING'
    
    # Base de données PostgreSQL en production
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("DATABASE_URL must be set in production")
    
    # Mode live pour les paiements
    PAYPAL_MODE = 'live'
    MONCASH_ENVIRONMENT = 'production'
    
    # Sentry en production
    SENTRY_ENVIRONMENT = 'production'
    SENTRY_TRACES_SAMPLE_RATE = 0.1  # Réduire le sampling en prod
    
    # Cache plus long en production
    CACHE_DEFAULT_TIMEOUT = 600
    PROJECT_CACHE_TIMEOUT = 1800
    USER_CACHE_TIMEOUT = 3600
    
    # Rate limiting plus strict
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT = "100 per day;20 per hour"
    
    # Sécurité renforcée
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Strict'
    
    # URL de base
    BASE_URL = os.environ.get('BASE_URL', 'https://agrinvest.ht')
    API_BASE_URL = f'{BASE_URL}/api'
    
    # Limites de sécurité
    MAX_CONTRIBUTION_AMOUNT = 1000000  # 1M HTG max par contribution en prod
    
    # Webhooks
    WEBHOOK_MAX_RETRIES = 5
    WEBHOOK_RETRY_DELAY = 300  # 5 minutes


class HerokuConfig(ProductionConfig):
    """Configuration spécifique pour Heroku"""
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    REDIS_URL = os.environ.get('REDIS_URL')
    
    # Configuration pour les logs Heroku
    LOG_FILE = None  # Désactiver les logs fichier sur Heroku
    LOG_LEVEL = 'INFO'


class DockerConfig(ProductionConfig):
    """Configuration spécifique pour Docker"""
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@db:5432/agrinvest')
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
    
    # Configuration pour Docker
    CACHE_REDIS_URL = REDIS_URL
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL


# =============================================================================
# DICTIONNAIRE DE CONFIGURATIONS
# =============================================================================

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
    'heroku': HerokuConfig,
    'docker': DockerConfig,
    'default': DevelopmentConfig,
}


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def get_config():
    """Retourne la configuration en fonction de l'environnement"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])


def init_config(app):
    """Initialise la configuration de l'application"""
    config_obj = get_config()
    app.config.from_object(config_obj)
    
    # Créer les dossiers nécessaires
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    log_dir = os.path.dirname(app.config['LOG_FILE'])
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    return app