# app/api/__init__.py
"""
API Routes pour AgriInvest Haïti
Version: 1.0.0
Base URL: /api/v1
"""

from flask import Blueprint
from flask_cors import CORS

# Création du blueprint principal
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Import des routes (après création du blueprint pour éviter circular imports)
from app.api import auth_routes
from app.api import user_routes
from app.api import project_routes
from app.api import contribution_routes
from app.api import group_contribution_routes
from app.api import collection_point_routes
from app.api import diaspora_routes
from app.api import fund_transfer_routes
from app.api import harvest_routes
from app.api import training_routes
from app.api import weather_routes
from app.api import payment_routes
from app.api import commission_routes
from app.api import admin_routes
from app.api import analytics_routes
from app.api import webhook_routes

# Enregistrement des blueprints
api_bp.register_blueprint(auth_routes.auth_bp)
api_bp.register_blueprint(user_routes.user_bp)
api_bp.register_blueprint(project_routes.project_bp)
api_bp.register_blueprint(contribution_routes.contribution_bp)
api_bp.register_blueprint(group_contribution_routes.group_bp)
api_bp.register_blueprint(collection_point_routes.collection_bp)
api_bp.register_blueprint(diaspora_routes.diaspora_bp)
api_bp.register_blueprint(fund_transfer_routes.transfer_bp)
api_bp.register_blueprint(harvest_routes.harvest_bp)
api_bp.register_blueprint(training_routes.training_bp)
api_bp.register_blueprint(weather_routes.weather_bp)
api_bp.register_blueprint(payment_routes.payment_bp)
api_bp.register_blueprint(commission_routes.commission_bp)
api_bp.register_blueprint(admin_routes.admin_bp)
api_bp.register_blueprint(analytics_routes.analytics_bp)
api_bp.register_blueprint(webhook_routes.webhook_bp)