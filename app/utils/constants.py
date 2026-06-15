# app/utils/constants.py
"""
Constantes globales pour AgriInvest Haïti
"""

# Devises
CURRENCY_SYMBOLS = {
    'HTG': 'G',
    'USD': '$',
    'EUR': '€',
    'CAD': 'C$',
    'GBP': '£'
}

SUPPORTED_CURRENCIES = ['HTG', 'USD', 'EUR', 'CAD']

# Montants
MIN_CONTRIBUTION_AMOUNT = 100  # HTG
MAX_CONTRIBUTION_AMOUNT = 10000000  # 10M HTG
MIN_PROJECT_AMOUNT = 10000  # HTG
MAX_PROJECT_AMOUNT = 50000000  # 50M HTG

# Paliers d'investissement
INVESTMENT_TIERS = {
    'basic': {'min': 100, 'max': 9999, 'label': 'Débutant'},
    'standard': {'min': 10000, 'max': 49999, 'label': 'Standard'},
    'premium': {'min': 50000, 'max': 199999, 'label': 'Premium'},
    'investor': {'min': 200000, 'max': None, 'label': 'Grand investisseur'}
}

# Types de notifications
NOTIFICATION_TYPES = {
    'info': 'info',
    'success': 'success',
    'warning': 'warning',
    'danger': 'danger'
}

# Statuts des projets
PROJECT_STATUS = {
    'draft': 'Brouillon',
    'pending': 'En attente',
    'published': 'Publié',
    'funded': 'Financé',
    'expired': 'Expiré',
    'cancelled': 'Annulé'
}

# Statuts des contributions
CONTRIBUTION_STATUS = {
    'pending': 'En attente',
    'completed': 'Confirmé',
    'failed': 'Échoué',
    'refunded': 'Remboursé'
}

# Rôles utilisateur
USER_ROLES = {
    'investor': 'Investisseur',
    'farmer': 'Agriculteur',
    'admin': 'Administrateur',
    'agent': 'Agent',
    'ambassador': 'Ambassadeur'
}

# Types de fichiers autorisés
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'ogg'}

# Tailles maximales (en octets)
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB

# Pagination
ITEMS_PER_PAGE = 20
PROJECTS_PER_PAGE = 12
CONTRIBUTIONS_PER_PAGE = 50

# Cache
CACHE_TIMEOUT_SHORT = 60  # 1 minute
CACHE_TIMEOUT_MEDIUM = 300  # 5 minutes
CACHE_TIMEOUT_LONG = 3600  # 1 heure

# Rate limiting
RATE_LIMIT_LOGIN = "20 per hour"
RATE_LIMIT_API = "100 per minute"
RATE_LIMIT_CONTRIBUTION = "10 per minute"

# Commission plateforme
DEFAULT_COMMISSION_PERCENTAGE = 3.0
CEO_COMMISSION_RANGE = (2.0, 5.0)

# JWT
JWT_EXPIRATION_HOURS = 24
JWT_REFRESH_EXPIRATION_DAYS = 30

# Email
DEFAULT_FROM_EMAIL = "noreply@agrinvest.ht"
ADMIN_EMAIL = "admin@agrinvest.ht"

# SMS
SMS_MAX_LENGTH = 160
SMS_VERIFICATION_CODE_LENGTH = 6

# Haïti
HAITI_DEPARTMENTS = [
    'Artibonite', 'Centre', 'Grand\'Anse', 'Nippes', 'Nord',
    'Nord-Est', 'Nord-Ouest', 'Ouest', 'Sud', 'Sud-Est'
]

HAITI_MAIN_CITIES = [
    'Port-au-Prince', 'Cap-Haïtien', 'Gonaïves', 'Les Cayes',
    'Jacmel', 'Jérémie', 'Hinche', 'Miragoâne', 'Saint-Marc'
]