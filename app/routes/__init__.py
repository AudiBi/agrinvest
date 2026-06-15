# app/routes/__init__.py
"""
Package des routes de l'application AgriInvest Haïti
"""

# Import des blueprints existants
from app.routes.main import bp as main_bp
from app.routes.auth import auth_bp
from app.routes.admin import admin_bp

# Import des blueprints API (existe)
try:
    from app.api import api_bp
except ImportError:
    api_bp = None

# Liste des blueprints disponibles
__all__ = ['main_bp', 'auth_bp', 'admin_bp', 'api_bp']


def register_blueprints(app):
    """Enregistre les blueprints dans l'application"""
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    if api_bp:
        app.register_blueprint(api_bp, url_prefix='/api/v1')