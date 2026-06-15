# app/utils/errors.py
"""
Classes d'erreurs personnalisées pour AgriInvest Haïti
"""


class AgriInvestError(Exception):
    """Classe de base pour toutes les erreurs de l'application"""
    def __init__(self, message, code=400, details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details


class NotFoundError(AgriInvestError):
    """Erreur 404 - Ressource non trouvée"""
    def __init__(self, message="Ressource non trouvée", details=None):
        super().__init__(message, code=404, details=details)


class ValidationError(AgriInvestError):
    """Erreur 400 - Validation échouée"""
    def __init__(self, message="Données invalides", details=None):
        super().__init__(message, code=400, details=details)


class UnauthorizedError(AgriInvestError):
    """Erreur 401 - Non authentifié"""
    def __init__(self, message="Authentification requise", details=None):
        super().__init__(message, code=401, details=details)


class BadRequestError(AgriInvestError):
    """Erreur 400 - Mauvaise requête"""
    def __init__(self, message="Mauvaise requête", details=None):
        super().__init__(message, code=400, details=details)


class ForbiddenError(AgriInvestError):
    """Erreur 403 - Accès interdit"""
    def __init__(self, message="Accès interdit", details=None):
        super().__init__(message, code=403, details=details)


class InternalServerError(AgriInvestError):
    """Erreur 500 - Erreur interne"""
    def __init__(self, message="Erreur interne du serveur", details=None):
        super().__init__(message, code=500, details=details)


class PaymentError(AgriInvestError):
    """Erreur de paiement"""
    def __init__(self, message="Erreur de paiement", details=None):
        super().__init__(message, code=400, details=details)


class RateLimitError(AgriInvestError):
    """Erreur 429 - Trop de requêtes"""
    def __init__(self, message="Trop de requêtes. Veuillez réessayer plus tard.", details=None):
        super().__init__(message, code=429, details=details)