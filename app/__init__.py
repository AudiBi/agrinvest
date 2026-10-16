# app/__init__.py
"""
Application Flask pour AgriInvest Haïti
Plateforme de financement participatif pour l'agriculture haïtienne
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from decimal import Decimal

from flask import Flask, render_template, request, session, g, jsonify, redirect, flash, url_for
from flask_migrate import Migrate
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import config
from app.extensions import (
    db, migrate, login_manager, mail, cors, csrf, 
    cache, limiter, celery, init_extensions
)


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def utc_now():
    """Retourne la date UTC actuelle"""
    return datetime.now(timezone.utc)


def format_currency(amount, currency='HTG'):
    """Formate un montant en devise"""
    if amount is None:
        amount = 0
    try:
        return f"{float(amount):,.0f} {currency}".replace(',', ' ')
    except (ValueError, TypeError):
        return f"0 {currency}"


def format_date(date, format_str='%d/%m/%Y'):
    """Formate une date"""
    if date:
        if isinstance(date, str):
            try:
                date = datetime.fromisoformat(date)
            except ValueError:
                return date
        return date.strftime(format_str)
    return ''


# ============================================================================
# CRÉATION DE L'APPLICATION
# ============================================================================

def create_app(config_name=None):
    """
    Application factory pattern
    Crée et configure l'application Flask
    """
    
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')
    
    # Création de l'application
    app = Flask(__name__, instance_relative_config=True)
    
    # Configuration ProxyFix pour HTTPS derrière proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Chargement de la configuration
    config_class = config[config_name]
    config_class.validate()  # SECRET_KEY / DATABASE_URL obligatoires
    app.config.from_object(config_class)
    
    # Création des dossiers nécessaires
    _create_directories(app)
    
    # Initialisation des extensions
    init_extensions(app)
    
    # Configuration supplémentaire de Login Manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page'
    login_manager.login_message_category = 'warning'
    login_manager.session_protection = 'strong'
    
    # Configuration de la session
    @app.before_request
    def make_session_permanent():
        session.permanent = True
    
    # Enregistrement des blueprints (UNIQUEMENT ICI, pas deux fois)
    _register_blueprints(app)
    
    # Enregistrement des filtres Jinja2 personnalisés
    _register_template_filters(app)
    
    # Enregistrement des context processors
    _register_context_processors(app)
    
    # Enregistrement des gestionnaires d'erreurs
    _register_error_handlers(app)
    
    # Configuration du logging
    _setup_logging(app)
    
    # Initialisation des commandes CLI
    _register_cli_commands(app)
    
    # Hooks de l'application
    _register_hooks(app)
    
    app.logger.info(f"✅ Application AgriInvest Haïti démarrée en mode {config_name}")
    
    return app


# ============================================================================
# FONCTIONS INTERNES
# ============================================================================

def _create_directories(app):
    """Crée tous les dossiers nécessaires à l'application"""
    directories = [
        app.instance_path,
        app.config.get('UPLOAD_FOLDER', os.path.join(app.instance_path, 'uploads')),
        os.path.join(app.instance_path, 'logs'),
        os.path.join(app.static_folder or 'app/static', 'uploads'),
        os.path.join(app.static_folder or 'app/static', 'img', 'projects'),
        os.path.join(app.static_folder or 'app/static', 'img', 'users'),
        os.path.join(app.static_folder or 'app/static', 'img', 'blog'),
        os.path.join(app.static_folder or 'app/static', 'img', 'team'),
        os.path.join(app.static_folder or 'app/static', 'css'),
        os.path.join(app.static_folder or 'app/static', 'js'),
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as e:
            app.logger.warning(f"Impossible de créer le dossier {directory}: {e}")


def _register_blueprints(app):
    """Enregistre tous les blueprints de l'application (UNIQUEMENT ICI)"""
    
    # Blueprint principal (routes web)
    try:
        from app.routes.main import bp as main_bp
        app.register_blueprint(main_bp)
        app.logger.info("✅ Blueprint main enregistré")
    except ImportError as e:
        app.logger.error(f"❌ Blueprint main non disponible: {e}")
        raise
    
    # Blueprint d'authentification
    try:
        from app.routes.auth import auth_bp
        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.logger.info("✅ Blueprint auth enregistré")
    except ImportError as e:
        app.logger.error(f"❌ Blueprint auth non disponible: {e}")
        raise
    
    # Blueprint d'administration
    try:
        from app.routes.admin import admin_bp
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.logger.info("✅ Blueprint admin enregistré")
    except ImportError as e:
        app.logger.error(f"❌ Blueprint admin non disponible: {e}")
        raise
    
    # API Blueprint
    try:
        from app.api import api_bp
        app.register_blueprint(api_bp, url_prefix='/api/v1')
        app.logger.info("✅ Blueprint API v1 enregistré")
    except ImportError as e:
        app.logger.error(f"❌ Blueprint API non disponible: {e}")
        raise
    
    app.logger.info("🚀 Tous les blueprints ont été enregistrés")


def _register_template_filters(app):
    """Enregistre les filtres Jinja2 personnalisés"""
    
    @app.template_filter('format_date')
    def filter_format_date(date, format='%d/%m/%Y'):
        """Formate une date"""
        return format_date(date, format)
    
    @app.template_filter('format_datetime')
    def filter_format_datetime(date):
        """Formate une date et heure"""
        if date:
            if isinstance(date, str):
                try:
                    date = datetime.fromisoformat(date)
                except ValueError:
                    return date
            return date.strftime('%d/%m/%Y à %H:%M')
        return ''
    
    @app.template_filter('format_currency')
    def filter_format_currency(amount, currency='HTG'):
        """Formate un montant en devise"""
        return format_currency(amount, currency)
    
    @app.template_filter('truncate')
    def filter_truncate(text, length=100):
        """Tronque un texte"""
        if text and len(text) > length:
            return text[:length] + '...'
        return text or ''
    
    @app.template_filter('time_ago')
    def filter_time_ago(date):
        """Retourne le temps écoulé depuis une date"""
        if not date:
            return ''
        
        if isinstance(date, str):
            try:
                date = datetime.fromisoformat(date)
            except ValueError:
                return date
        
        now = utc_now()
        diff = now - date
        
        if diff.days > 365:
            return f"il y a {diff.days // 365} an{'s' if diff.days // 365 > 1 else ''}"
        elif diff.days > 30:
            return f"il y a {diff.days // 30} mois"
        elif diff.days > 0:
            return f"il y a {diff.days} jour{'s' if diff.days > 1 else ''}"
        elif diff.seconds > 3600:
            return f"il y a {diff.seconds // 3600} heure{'s' if diff.seconds // 3600 > 1 else ''}"
        elif diff.seconds > 60:
            return f"il y a {diff.seconds // 60} minute{'s' if diff.seconds // 60 > 1 else ''}"
        else:
            return "à l'instant"
    
    @app.template_filter('percentage')
    def filter_percentage(value, total):
        """Calcule un pourcentage"""
        if not total or total == 0:
            return 0
        try:
            return round((float(value) / float(total)) * 100, 1)
        except (ValueError, TypeError):
            return 0
    
    @app.template_filter('default_image')
    def filter_default_image(image_url, type='project'):
        """Retourne une image par défaut si l'image est manquante"""
        if image_url:
            return image_url
        
        defaults = {
            'project': '/static/img/project-default.jpg',
            'user': '/static/img/user-default.png',
            'blog': '/static/img/blog-default.jpg',
        }
        return defaults.get(type, defaults['project'])
    
    @app.template_filter('pluralize')
    def filter_pluralize(count, singular, plural=None):
        """Pluralise un mot selon le nombre"""
        if plural is None:
            plural = singular + 's'
        return singular if count == 1 else plural


def _register_context_processors(app):
    """Enregistre les context processors globaux"""
    
    @app.context_processor
    def utility_processor():
        """Ajoute des fonctions utilitaires à tous les templates"""
        return {
            'now': utc_now(),
            'current_year': utc_now().year,
            'app_name': 'AgriInvest Haïti',
            'app_version': '1.0.0',
            'app_slogan': 'Cultivons l\'avenir d\'Haïti ensemble',
            'supported_currencies': ['HTG', 'USD', 'EUR', 'CAD'],
            'supported_languages': [
                {'code': 'ht', 'name': 'Kreyòl', 'flag': '🇭🇹', 'direction': 'ltr'},
                {'code': 'fr', 'name': 'Français', 'flag': '🇫🇷', 'direction': 'ltr'},
                {'code': 'en', 'name': 'English', 'flag': '🇺🇸', 'direction': 'ltr'}
            ],
            'format_currency': format_currency,
            'format_date': format_date,
            'utc_now': utc_now
        }
    
    @app.context_processor
    def inject_user_settings():
        """Injecte les paramètres utilisateur dans les templates"""
        settings = {
            'user_language': session.get('language', 'fr'),
            'user_currency': 'HTG',
            'user_is_authenticated': current_user.is_authenticated if current_user else False,
            'user_role': current_user.role if current_user and current_user.is_authenticated else None,
            'user_name': current_user.name if current_user and current_user.is_authenticated else None
        }
        
        if current_user and current_user.is_authenticated:
            settings['user_language'] = current_user.preferred_language or 'fr'
            settings['user_currency'] = current_user.preferred_currency or 'HTG'
        
        return settings
    
    @app.context_processor
    def inject_site_stats():
        """Injecte les statistiques du site"""
        from app.models import Project, User, Contribution
        from app.models.enums import ContributionStatus
        
        stats = {
            'site_stats': {
                'total_projects': Project.query.filter_by(is_published=True).count(),
                'total_investors': User.query.filter_by(role='investor', is_active=True).count(),
                'total_raised': db.session.query(db.func.sum(Contribution.amount_htg)).filter_by(
                    status=ContributionStatus.COMPLETED
                ).scalar() or 0,
                'total_farmers': User.query.filter_by(role='farmer', is_active=True).count()
            }
        }
        return stats


def _register_error_handlers(app):
    """Enregistre les gestionnaires d'erreurs personnalisés"""
    
    @app.errorhandler(400)
    def bad_request(error):
        """Erreur 400 - Mauvaise requête"""
        app.logger.warning(f"400 Bad Request: {request.url}")
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Mauvaise requête', 'code': 400}), 400
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(403)
    def forbidden(error):
        """Erreur 403 - Accès interdit"""
        app.logger.warning(f"403 Forbidden: {request.url}")
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Accès interdit', 'code': 403}), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(error):
        """Erreur 404 - Page non trouvée"""
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Page non trouvée', 'code': 404}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(413)
    def too_large(error):
        """Erreur 413 - Fichier trop volumineux"""
        app.logger.warning(f"413 Payload Too Large: {request.url}")
        flash('Le fichier est trop volumineux (maximum 16MB)', 'danger')
        return redirect(request.referrer or url_for('main.home'))
    
    @app.errorhandler(429)
    def too_many_requests(error):
        """Erreur 429 - Trop de requêtes"""
        app.logger.warning(f"429 Too Many Requests: {request.url} - IP: {request.remote_addr}")
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Trop de requêtes. Veuillez réessayer plus tard.', 'code': 429}), 429
        return render_template('errors/429.html'), 429
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Erreur 500 - Erreur interne"""
        db.session.rollback()
        app.logger.error(f"500 Internal Server Error: {error} - URL: {request.url}")
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Erreur interne du serveur', 'code': 500}), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(503)
    def service_unavailable(error):
        """Erreur 503 - Service indisponible"""
        app.logger.error(f"503 Service Unavailable: {error}")
        return render_template('errors/503.html'), 503


def _setup_logging(app):
    """Configure le logging professionnel"""
    
    # Niveau de log
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
    
    # Format des logs
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s [%(name)s] %(message)s'
    )
    
    # Handler pour la console (toujours actif en développement)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    app.logger.addHandler(console_handler)
    
    # Handler pour les fichiers (en production)
    if not app.debug and app.config.get('LOG_FILE'):
        try:
            log_file = app.config['LOG_FILE']
            log_dir = os.path.dirname(log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            
            # Fichier principal
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=app.config.get('LOG_MAX_BYTES', 10 * 1024 * 1024),
                backupCount=app.config.get('LOG_BACKUP_COUNT', 10)
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            app.logger.addHandler(file_handler)
            
            # Fichier pour les erreurs uniquement
            error_log_file = log_file.replace('.log', '_error.log')
            error_handler = RotatingFileHandler(
                error_log_file,
                maxBytes=app.config.get('LOG_MAX_BYTES', 10 * 1024 * 1024),
                backupCount=app.config.get('LOG_BACKUP_COUNT', 10)
            )
            error_handler.setFormatter(formatter)
            error_handler.setLevel(logging.ERROR)
            app.logger.addHandler(error_handler)
            
            app.logger.info(f"Logging configuré: {log_file}")
            
        except Exception as e:
            app.logger.warning(f"Impossible de créer les fichiers de log: {e}")
    
    # Désactiver les logs des bibliothèques trop verbeuses
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    app.logger.setLevel(log_level)
    app.logger.info(f"Logging configuré au niveau {logging.getLevelName(log_level)}")


def _register_cli_commands(app):
    """Enregistre les commandes CLI personnalisées"""
    
    @app.cli.command('init-db')
    def init_db_command():
        """Initialise la base de données"""
        import click
        click.echo("📦 Initialisation de la base de données...")
        db.create_all()
        click.echo("✅ Base de données initialisée")
    
    @app.cli.command('reconcile-payments')
    def reconcile_payments_command():
        """Confirme ou expire les contributions « pending » en interrogeant les passerelles"""
        import click
        from app.utils.reconciliation import reconcile_pending_contributions
        stats = reconcile_pending_contributions()
        click.echo(
            f"Vérifiées: {stats['checked']} | confirmées: {stats['completed']} | "
            f"expirées: {stats['expired']} | erreurs: {stats['errors']}")
    
    @app.cli.command('seed-db')
    def seed_db_command():
        """Remplit la base de données avec des données de test"""
        import click
        click.echo("🌱 Insertion des données de test...")
        try:
            from app.utils.seed import seed_database
            seed_database()
            click.echo("✅ Données de test insérées")
        except ImportError:
            click.echo("⚠️ Fichier seed.py non trouvé")
    
    @app.cli.command('clear-cache')
    def clear_cache_command():
        """Vide le cache Redis"""
        import click
        click.echo("🗑️ Vidage du cache...")
        try:
            from app.extensions import clear_cache
            clear_cache()
            click.echo("✅ Cache vidé")
        except ImportError:
            click.echo("⚠️ Extension cache non disponible")
    
    @app.cli.command('show-routes')
    def show_routes_command():
        """Affiche toutes les routes enregistrées"""
        import click
        click.echo("\n📋 Routes enregistrées:\n")
        for rule in app.url_map.iter_rules():
            methods = ','.join(rule.methods - {'HEAD', 'OPTIONS'})
            click.echo(f"  {methods:10} {rule}")
        click.echo(f"\nTotal: {len(app.url_map.iter_rules())} routes")


def _register_hooks(app):
    """Enregistre les hooks de l'application"""
    
    @app.before_request
    def before_request():
        """Actions avant chaque requête"""
        # Définir la langue de session
        if 'language' not in session:
            session['language'] = 'fr'
        
        # Mettre à jour la dernière activité
        if current_user and current_user.is_authenticated:
            g.user_last_active = utc_now()
        
        # Journaliser les requêtes API
        if request.path.startswith('/api/'):
            app.logger.info(f"API Request: {request.method} {request.path} - IP: {request.remote_addr}")
    
    @app.after_request
    def after_request(response):
        """Actions après chaque requête"""
        # Ajouter des en-têtes de sécurité
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Forcer HTTPS en production
        if not app.debug and not request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        return response
    
    @app.teardown_request
    def teardown_request(error=None):
        """Actions après chaque requête (même en cas d'erreur)"""
        if error:
            app.logger.error(f"Erreur lors de la requête: {error}")


# ============================================================================
# IMPORT DES MODÈLES POUR SQLALCHEMY
# ============================================================================

# Importer les modèles pour que SQLAlchemy les connaisse
from app.models import User, Project, Contribution, HarvestUpdate, Training
from app.models import GroupContribution, CollectionPoint, DiasporaCampaign
from app.models import FundTransfer, WeatherAlert, WeatherSubscription
from app.models import PlatformCommissionConfig, PlatformEarning, CEOPayout
from app.models import PaymentGatewayConfig, AnalyticsEvent, Notification