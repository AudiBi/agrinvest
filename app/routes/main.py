# app/routes/main.py
"""
Routes principales de l'application web AgriInvest Haïti
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app, session, send_file, jsonify
from flask_login import login_required, current_user, logout_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
import os
import json
from decimal import Decimal

from app.models import (
    User, Project, Contribution, HarvestUpdate, Training, TrainingProgress,
    WeatherAlert, WeatherSubscription, GroupContribution, CollectionPoint,
    PlatformCommissionConfig, AnalyticsEvent, Notification
)
from app.models.enums import ProjectStatus, ContributionStatus, UserRole
from app.extensions import db
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services.payment_service import PaymentService
from app.utils.decorators import farmer_required, investor_required, admin_required
from app.utils.validators import validate_email, validate_password
from app.utils.helpers import format_currency, generate_contract_pdf, utc_now


# ============================================================================
# CRÉATION DU BLUEPRINT (DOIT ÊTRE ICI, AVANT LES DÉCORATEURS)
# ============================================================================

bp = Blueprint('main', __name__)


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def is_safe_url(target):
    """Vérifie que l'URL de redirection est sécurisée"""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def allowed_file(filename):
    """Vérifie si le type de fichier est autorisé"""
    if not filename:
        return False
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'pdf'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


# ============================================================================
# FILTRES JINJA2 PERSONNALISÉS
# ============================================================================

@bp.app_template_filter('format_date')
def format_date_filter(date, format='%d/%m/%Y'):
    """Formate une date"""
    if date:
        if isinstance(date, str):
            try:
                date = datetime.fromisoformat(date)
            except ValueError:
                return date
        return date.strftime(format)
    return ''


@bp.app_template_filter('format_datetime')
def format_datetime_filter(date):
    """Formate une date et heure"""
    if date:
        if isinstance(date, str):
            try:
                date = datetime.fromisoformat(date)
            except ValueError:
                return date
        return date.strftime('%d/%m/%Y à %H:%M')
    return ''


@bp.app_template_filter('format_currency')
def format_currency_filter(amount, currency='HTG'):
    """Formate un montant en devise"""
    if amount:
        try:
            return f"{float(amount):,.0f} {currency}".replace(',', ' ')
        except (ValueError, TypeError):
            return f"0 {currency}"
    return f"0 {currency}"


@bp.app_template_filter('truncate')
def truncate_filter(text, length=100):
    """Tronque un texte"""
    if text and len(text) > length:
        return text[:length] + '...'
    return text or ''


@bp.app_template_filter('time_ago')
def time_ago_filter(date):
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


@bp.app_template_filter('percentage')
def percentage_filter(value, total):
    """Calcule un pourcentage"""
    if not total or total == 0:
        return 0
    try:
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, TypeError):
        return 0


@bp.app_template_filter('default_image')
def default_image_filter(image_url, type='project'):
    """Retourne une image par défaut si l'image est manquante"""
    if image_url:
        return image_url
    
    defaults = {
        'project': '/static/img/project-default.jpg',
        'user': '/static/img/user-default.png',
        'blog': '/static/img/blog-default.jpg',
    }
    return defaults.get(type, defaults['project'])


# ============================================================================
# PAGES PUBLIQUES
# ============================================================================

@bp.route('/')
def home():
    """Page d'accueil"""
    # Statistiques pour la page d'accueil
    stats = {
        'total_projects': Project.query.filter_by(is_published=True).count(),
        'total_investors': User.query.filter_by(role=UserRole.INVESTOR, is_active=True).count(),
        'total_raised': db.session.query(db.func.sum(Contribution.amount_htg)).filter_by(
            status=ContributionStatus.COMPLETED
        ).scalar() or 0,
        'farmers_helped': User.query.filter_by(role=UserRole.FARMER, is_verified=True).count()
    }
    
    # Projets vedettes
    featured_projects = Project.query.filter_by(
        is_featured=True,
        is_published=True,
        status=ProjectStatus.PUBLISHED
    ).limit(6).all()
    
    # Projets récents
    recent_projects = Project.query.filter_by(
        is_published=True,
        status=ProjectStatus.PUBLISHED
    ).order_by(Project.created_at.desc()).limit(9).all()
    
    # Témoignages
    testimonials = [
        {
            'name': 'Marie Joseph',
            'role': 'Agricultrice',
            'location': 'Hinche',
            'message': 'Grâce à AgriInvest, j\'ai pu financer ma première récolte de manioc. Une expérience fluide et humaine !',
            'avatar': 'MJ'
        },
        {
            'name': 'Jean-Paul Pierre',
            'role': 'Investisseur',
            'location': 'Port-au-Prince',
            'message': 'Un moyen concret d\'investir dans notre pays. J\'ai déjà soutenu 3 projets et je vois l\'impact !',
            'avatar': 'JP'
        }
    ]
    
    return render_template('index.html',
                         stats=stats,
                         featured_projects=featured_projects,
                         recent_projects=recent_projects,
                         testimonials=testimonials)


@bp.route('/about')
def about():
    """Page À propos"""
    return render_template('about.html')


@bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """Page de contact"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        # Envoyer l'email
        try:
            EmailService.send_contact_message(name, email, subject, message)
            flash('Votre message a été envoyé. Nous vous répondrons dans les plus brefs délais.', 'success')
        except Exception as e:
            current_app.logger.error(f"Erreur envoi email: {e}")
            flash('Une erreur est survenue. Veuillez réessayer plus tard.', 'danger')
        
        return redirect(url_for('main.contact'))
    
    return render_template('contact.html')


@bp.route('/faq')
def faq():
    """Page FAQ"""
    faqs = [
        {
            'question': 'Comment puis-je investir dans un projet ?',
            'answer': 'Il vous suffit de créer un compte investisseur, parcourir les projets disponibles, choisir celui qui vous intéresse et saisir le montant que vous souhaitez investir.'
        },
        {
            'question': 'Est-ce que mon argent est en sécurité ?',
            'answer': 'Oui, toutes les transactions sont sécurisées via des partenaires de paiement agréés. Les fonds sont bloqués sur des comptes séquestres jusqu\'à l\'atteinte de l\'objectif du projet.'
        },
        {
            'question': 'Les projets sont-ils vérifiés ?',
            'answer': 'Oui, chaque projet est soumis à une vérification rigoureuse avant publication. Notre équipe vérifie la faisabilité technique, la viabilité financière et les antécédents de l\'agriculteur.'
        },
        {
            'question': 'Puis-je investir depuis l\'étranger ?',
            'answer': 'Absolument ! La diaspora haïtienne peut investir facilement depuis n\'importe où dans le monde. Nous acceptons les paiements internationaux (USD, EUR, CAD).'
        },
        {
            'question': 'Quel est le retour sur investissement ?',
            'answer': 'Le retour sur investissement varie selon les projets. En moyenne, nos investisseurs obtiennent un rendement annuel de 5 à 12% selon le niveau de risque du projet.'
        }
    ]
    
    return render_template('faq.html', faqs=faqs)


@bp.route('/terms')
def terms():
    """Conditions d'utilisation"""
    return render_template('terms.html')


@bp.route('/privacy')
def privacy():
    """Politique de confidentialité"""
    return render_template('privacy.html')


# ============================================================================
# AUTHENTIFICATION
# ============================================================================

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Page de connexion"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        next_url = request.form.get('next') or request.args.get('next')
        
        # Authentification via le service unifié
        result = AuthService.authenticate_user(email, password, remember)
        
        if not result['success']:
            flash(result['error'], 'danger')
            return render_template('login.html', next=next_url)
        
        # Redirection après connexion
        if next_url and is_safe_url(next_url):
            return redirect(next_url)
        
        return redirect(url_for('main.dashboard'))
    
    return render_template('login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Page d'inscription"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role', 'investor')
        phone = request.form.get('phone')
        country = request.form.get('country', 'HT')
        
        # Validation
        if not name or not email or not password:
            flash('Tous les champs sont requis', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas', 'danger')
            return render_template('register.html')
        
        if not validate_email(email):
            flash('Adresse email invalide', 'danger')
            return render_template('register.html')
        
        if not validate_password(password):
            flash('Le mot de passe doit contenir au moins 8 caractères avec une majuscule, une minuscule et un chiffre', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Cet email est déjà utilisé', 'danger')
            return render_template('register.html')
        
        # Création de l'utilisateur
        user = User(
            name=name,
            email=email,
            role=role,
            phone=phone,
            country=country,
            preferred_currency='USD' if country != 'HT' else 'HTG',
            preferred_language='ht'
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Envoyer email de bienvenue
        try:
            EmailService.send_welcome_email(user)
        except Exception as e:
            current_app.logger.error(f"Erreur envoi email bienvenue: {e}")
        
        # Connexion automatique
        login_user(user)
        
        flash('Inscription réussie ! Bienvenue sur AgriInvest Haïti.', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('register.html')


@bp.route('/logout')
@login_required
def logout():
    """Déconnexion"""
    logout_user()
    flash('Vous avez été déconnecté avec succès.', 'info')
    return redirect(url_for('main.home'))


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Mot de passe oublié"""
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = AuthService.generate_reset_token(email)
            EmailService.send_password_reset_email(user, token)
            flash('Un email de réinitialisation vous a été envoyé.', 'success')
        else:
            # Ne pas révéler si l'email existe ou non (sécurité)
            flash('Si cet email existe, vous recevrez un lien de réinitialisation.', 'info')
        
        return redirect(url_for('main.login'))
    
    return render_template('forgot_password.html')


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Réinitialisation du mot de passe"""
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas', 'danger')
            return render_template('reset_password.html', token=token)
        
        if not validate_password(password):
            flash('Le mot de passe doit contenir au moins 8 caractères avec une majuscule, une minuscule et un chiffre', 'danger')
            return render_template('reset_password.html', token=token)
        
        if AuthService.reset_password(token, password):
            flash('Votre mot de passe a été réinitialisé avec succès.', 'success')
            return redirect(url_for('main.login'))
        else:
            flash('Lien invalide ou expiré.', 'danger')
            return redirect(url_for('main.forgot_password'))
    
    return render_template('reset_password.html', token=token)

# Ajoutez ceci dans app/routes/main.py, par exemple après la route newsletter

@bp.route('/set-language', methods=['POST'])
def set_language():
    """Change la langue de l'utilisateur"""
    language = request.form.get('language')
    if language in ['ht', 'fr', 'en']:
        if current_user.is_authenticated:
            current_user.preferred_language = language
            db.session.commit()
        session['language'] = language
    return jsonify({'success': True})

# ============================================================================
# TABLEAU DE BORD UTILISATEUR
# ============================================================================

@bp.route('/dashboard')
@login_required
def dashboard():
    """Tableau de bord principal"""
    if current_user.is_farmer:
        return redirect(url_for('main.farmer_dashboard'))
    elif current_user.is_investor:
        return redirect(url_for('main.investor_dashboard'))
    elif current_user.is_admin:
        return redirect(url_for('admin.dashboard'))
    else:
        return redirect(url_for('main.home'))


@bp.route('/dashboard/farmer')
@login_required
@farmer_required
def farmer_dashboard():
    """Tableau de bord agriculteur"""
    # Statistiques
    projects = Project.query.filter_by(farmer_id=current_user.id).all()
    
    stats = {
        'total_projects': len(projects),
        'published_projects': sum(1 for p in projects if p.is_published),
        'funded_projects': sum(1 for p in projects if p.status == ProjectStatus.FUNDED),
        'total_raised': sum(p.amount_raised for p in projects),
        'total_investors': Contribution.query.join(Project).filter(
            Project.farmer_id == current_user.id,
            Contribution.status == ContributionStatus.COMPLETED
        ).distinct('investor_id').count()
    }
    
    # Projets paginés
    page = request.args.get('page', 1, type=int)
    filter_status = request.args.get('status', 'all')
    search = request.args.get('search', '')
    
    query = Project.query.filter_by(farmer_id=current_user.id)
    
    if filter_status != 'all':
        query = query.filter_by(status=filter_status)
    if search:
        query = query.filter(Project.title.ilike(f'%{search}%'))
    
    pagination = query.order_by(Project.created_at.desc()).paginate(
        page=page, per_page=9, error_out=False
    )
    
    return render_template('dashboard/farmer.html',
                         stats=stats,
                         projects=pagination,
                         filter_status=filter_status,
                         search_query=search)


@bp.route('/dashboard/investor')
@login_required
@investor_required
def investor_dashboard():
    """Tableau de bord investisseur"""
    # Contributions
    contributions = Contribution.query.filter_by(
        investor_id=current_user.id,
        status=ContributionStatus.COMPLETED
    )
    
    total_invested = contributions.with_entities(db.func.sum(Contribution.amount_htg)).scalar() or 0
    
    # Projets soutenus
    projects_invested = db.session.query(
        Project,
        db.func.sum(Contribution.amount_htg).label('total_invested'),
        db.func.count(Contribution.id).label('count')
    ).join(
        Contribution, Contribution.project_id == Project.id
    ).filter(
        Contribution.investor_id == current_user.id,
        Contribution.status == ContributionStatus.COMPLETED
    ).group_by(Project.id).order_by(db.func.sum(Contribution.amount_htg).desc()).all()
    
    # Historique des contributions paginé
    page = request.args.get('page', 1, type=int)
    selected_project = request.args.get('project_id', type=int)
    selected_status = request.args.get('status', '')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    query = Contribution.query.filter_by(investor_id=current_user.id)
    
    if selected_project:
        query = query.filter_by(project_id=selected_project)
    if selected_status:
        query = query.filter_by(status=selected_status)
    if date_from:
        try:
            query = query.filter(Contribution.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Contribution.created_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass
    
    pagination = query.order_by(Contribution.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Liste des projets pour le filtre
    all_projects = Project.query.filter_by(is_published=True).all()
    
    # Données pour le graphique (6 derniers mois)
    monthly_data = []
    for i in range(6):
        month_start = utc_now().replace(day=1) - timedelta(days=30*i)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(microseconds=1)
        
        amount = db.session.query(db.func.sum(Contribution.amount_htg)).filter(
            Contribution.investor_id == current_user.id,
            Contribution.status == ContributionStatus.COMPLETED,
            Contribution.created_at.between(month_start, month_end)
        ).scalar() or 0
        
        monthly_data.append({
            'month': month_start.strftime('%b %Y'),
            'amount': float(amount)
        })
    
    return render_template('dashboard/investor.html',
                         total_invested=total_invested,
                         projects_invested=projects_invested,
                         contributions=pagination,
                         all_projects=all_projects,
                         selected_project=selected_project,
                         selected_status=selected_status,
                         date_from=date_from,
                         date_to=date_to,
                         monthly_data=monthly_data)


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Profil utilisateur"""
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.phone = request.form.get('phone')
        current_user.location = request.form.get('location')
        current_user.bio = request.form.get('bio')
        current_user.preferred_currency = request.form.get('preferred_currency', 'HTG')
        current_user.preferred_language = request.form.get('preferred_language', 'ht')
        
        # Gestion de l'avatar
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"user_{current_user.id}_{file.filename}")
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                current_user.avatar_url = url_for('static', filename=f'uploads/{filename}')
        
        db.session.commit()
        flash('Profil mis à jour avec succès', 'success')
        return redirect(url_for('main.profile'))
    
    return render_template('profile.html')


# ============================================================================
# GESTION DES PROJETS
# ============================================================================

@bp.route('/projects')
def project_list():
    """Liste des projets"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category')
    department = request.args.get('department')
    search = request.args.get('q')
    sort = request.args.get('sort', 'newest')
    
    query = Project.query.filter_by(is_published=True, status=ProjectStatus.PUBLISHED)
    
    if category:
        query = query.filter_by(category=category)
    if department:
        query = query.filter_by(department=department)
    if search:
        query = query.filter(
            Project.title.ilike(f'%{search}%') |
            Project.description.ilike(f'%{search}%')
        )
    
    # Tri
    if sort == 'newest':
        query = query.order_by(Project.created_at.desc())
    elif sort == 'popular':
        query = query.order_by(Project.investor_count.desc())
    elif sort == 'ending':
        query = query.filter(Project.deadline > utc_now()).order_by(Project.deadline.asc())
    
    pagination = query.paginate(page=page, per_page=12, error_out=False)
    
    # Catégories et départements pour les filtres
    categories = db.session.query(Project.category.distinct()).filter_by(is_published=True).all()
    departments = db.session.query(Project.department.distinct()).filter_by(is_published=True).all()
    
    return render_template('projects/list.html',
                         projects=pagination,
                         categories=[c[0] for c in categories if c[0]],
                         departments=[d[0] for d in departments if d[0]],
                         selected_category=category,
                         selected_department=department,
                         search_query=search,
                         sort=sort)


@bp.route('/project/<int:project_id>')
def project_detail(project_id):
    """Détail d'un projet"""
    project = Project.query.get_or_404(project_id)
    
    # Vérifier l'accès
    if not project.is_published and not current_user.is_authenticated:
        abort(404)
    if not project.is_published and project.farmer_id != current_user.id and not current_user.is_admin:
        abort(404)
    
    # Contributions du projet
    contributions = Contribution.query.filter_by(
        project_id=project_id,
        status=ContributionStatus.COMPLETED
    ).order_by(Contribution.created_at.desc()).limit(20).all()
    
    # Mises à jour
    updates = project.updates.filter_by(is_published=True).limit(10).all()
    
    # Projets similaires
    similar_projects = Project.query.filter(
        Project.is_published == True,
        Project.status == ProjectStatus.PUBLISHED,
        Project.category == project.category,
        Project.id != project_id
    ).limit(3).all()
    
    return render_template('projects/detail.html',
                         project=project,
                         contributions=contributions,
                         updates=updates,
                         similar_projects=similar_projects)


@bp.route('/project/create', methods=['GET', 'POST'])
@login_required
@farmer_required
def create_project():
    """Créer un nouveau projet"""
    if request.method == 'POST':
        try:
            project = Project(
                title=request.form.get('title'),
                title_ht=request.form.get('title_ht'),
                description=request.form.get('description'),
                description_ht=request.form.get('description_ht'),
                short_description=request.form.get('short_description'),
                location=request.form.get('location'),
                department=request.form.get('department'),
                commune=request.form.get('commune'),
                category=request.form.get('category'),
                amount_needed=Decimal(request.form.get('amount_needed')),
                min_investment=Decimal(request.form.get('min_investment', 100)),
                deadline=datetime.fromisoformat(request.form.get('deadline')),
                farmer_id=current_user.id,
                currency='HTG'
            )
            
            db.session.add(project)
            db.session.commit()
            
            # Gestion de l'image après l'ID
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"project_{project.id}_{file.filename}")
                    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                    project.image_url = url_for('static', filename=f'uploads/{filename}')
                    db.session.commit()
            
            flash('Projet créé avec succès ! Vous pouvez maintenant le compléter et le publier.', 'success')
            return redirect(url_for('main.edit_project', project_id=project.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur création projet: {e}")
            flash('Une erreur est survenue lors de la création du projet.', 'danger')
    
    return render_template('projects/create.html')


@bp.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    """Modifier un projet"""
    project = Project.query.get_or_404(project_id)
    
    if project.farmer_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    if request.method == 'POST':
        try:
            project.title = request.form.get('title')
            project.title_ht = request.form.get('title_ht')
            project.description = request.form.get('description')
            project.description_ht = request.form.get('description_ht')
            project.short_description = request.form.get('short_description')
            project.location = request.form.get('location')
            project.department = request.form.get('department')
            project.commune = request.form.get('commune')
            project.category = request.form.get('category')
            project.amount_needed = Decimal(request.form.get('amount_needed'))
            project.min_investment = Decimal(request.form.get('min_investment', 100))
            project.max_investment = Decimal(request.form.get('max_investment')) if request.form.get('max_investment') else None
            project.deadline = datetime.fromisoformat(request.form.get('deadline'))
            
            # Gestion de l'image
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"project_{project.id}_{file.filename}")
                    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                    project.image_url = url_for('static', filename=f'uploads/{filename}')
            
            db.session.commit()
            flash('Projet mis à jour avec succès', 'success')
            return redirect(url_for('main.project_detail', project_id=project.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur modification projet: {e}")
            flash('Une erreur est survenue lors de la modification du projet.', 'danger')
    
    return render_template('projects/edit.html', project=project)


@bp.route('/project/<int:project_id>/publish', methods=['POST'])
@login_required
def publish_project(project_id):
    """Publier un projet"""
    project = Project.query.get_or_404(project_id)
    
    if project.farmer_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    if not project.image_url:
        flash('Veuillez ajouter une image avant de publier', 'warning')
        return redirect(url_for('main.edit_project', project_id=project.id))
    
    project.publish()
    flash('Projet publié avec succès !', 'success')
    return redirect(url_for('main.project_detail', project_id=project.id))


@bp.route('/project/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    """Supprimer un projet (soft delete)"""
    project = Project.query.get_or_404(project_id)
    
    if project.farmer_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    if project.status == ProjectStatus.FUNDED:
        flash('Impossible de supprimer un projet déjà financé', 'danger')
        return redirect(url_for('main.project_detail', project_id=project.id))
    
    project.status = ProjectStatus.CANCELLED
    project.is_published = False
    db.session.commit()
    
    flash('Projet supprimé avec succès', 'success')
    return redirect(url_for('main.farmer_dashboard'))


# ============================================================================
# INVESTISSEMENTS
# ============================================================================

@bp.route('/invest/<int:project_id>', methods=['GET', 'POST'])
@login_required
@investor_required
def invest(project_id):
    """Page d'investissement"""
    project = Project.query.get_or_404(project_id)
    
    # Vérifier que l'utilisateur est investisseur
    if not current_user.is_investor and not current_user.is_admin:
        flash('Seuls les investisseurs peuvent contribuer aux projets.', 'warning')
        return redirect(url_for('main.project_detail', project_id=project_id))
    
    if request.method == 'POST':
        try:
            amount = Decimal(request.form.get('amount', 0))
            
            # Vérifier si le projet accepte les contributions
            can_accept, error = project.can_accept_contribution(amount)
            
            if not can_accept:
                flash(error, 'warning')
                return redirect(url_for('main.project_detail', project_id=project_id))
            
            payment_method = request.form.get('payment_method')
            is_anonymous = request.form.get('is_anonymous') == 'on'
            message = request.form.get('message')
            
            # Calculer les valeurs par défaut
            amount_htg = amount  # Si en HTG, sinon appliquer taux de change
            gateway_fee = Decimal('0')
            conversion_fee = Decimal('0')
            platform_fee = Decimal('0')
            platform_commission_amount = Decimal('0')
            
            # Créer la contribution avec toutes les valeurs par défaut
            contribution = Contribution(
                investor_id=current_user.id,
                project_id=project_id,
                amount=amount,
                currency='HTG',
                amount_htg=amount_htg,
                gateway_fee=gateway_fee,
                conversion_fee=conversion_fee,
                platform_fee=platform_fee,
                net_amount_htg=amount_htg - gateway_fee - conversion_fee - platform_fee - platform_commission_amount,
                platform_commission_applied=None,
                platform_commission_amount=platform_commission_amount,
                payment_method=payment_method,
                is_anonymous=is_anonymous,
                message=message,
                investor_country=current_user.country or 'HT'
            )
            
            db.session.add(contribution)
            db.session.commit()
            
            flash('Contribution enregistrée avec succès !', 'success')
            return redirect(url_for('main.investor_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur investissement: {e}")
            flash('Une erreur est survenue. Veuillez réessayer.', 'danger')
            return redirect(url_for('main.project_detail', project_id=project_id))
    
    # Vérification GET
    can_accept, error = project.can_accept_contribution(project.min_investment or Decimal('100'))
    if not can_accept and project.status == 'published':
        flash(error, 'warning')
        return redirect(url_for('main.project_detail', project_id=project_id))
    
    return render_template('projects/invest.html', project=project)

@bp.route('/contribution/<int:contribution_id>/contract')
@login_required
def download_contract(contribution_id):
    """Télécharger le contrat d'investissement"""
    contribution = Contribution.query.get_or_404(contribution_id)
    
    if contribution.investor_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    # Générer le PDF du contrat
    pdf = generate_contract_pdf(contribution)
    
    if pdf:
        return send_file(
            pdf,
            as_attachment=True,
            download_name=f"contrat_{contribution.project.slug}_{contribution.id}.pdf",
            mimetype='application/pdf'
        )
    else:
        flash('Le contrat est en cours de génération. Vous le recevrez par email.', 'info')
        return redirect(url_for('main.investor_dashboard'))


# ============================================================================
# MISES À JOUR DES PROJETS
# ============================================================================

@bp.route('/project/<int:project_id>/updates')
def project_updates(project_id):
    """Liste des mises à jour d'un projet"""
    project = Project.query.get_or_404(project_id)
    
    page = request.args.get('page', 1, type=int)
    updates = project.updates.filter_by(is_published=True).paginate(page=page, per_page=10)
    
    return render_template('projects/updates.html', project=project, updates=updates)


@bp.route('/project/<int:project_id>/update/create', methods=['GET', 'POST'])
@login_required
def create_update(project_id):
    """Créer une mise à jour"""
    project = Project.query.get_or_404(project_id)
    
    if project.farmer_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    if request.method == 'POST':
        update = HarvestUpdate(
            project_id=project_id,
            title=request.form.get('title'),
            title_ht=request.form.get('title_ht'),
            content=request.form.get('content'),
            content_ht=request.form.get('content_ht'),
            update_type=request.form.get('update_type', 'general'),
            is_important=request.form.get('is_important') == 'on',
            notify_investors=request.form.get('notify_investors') == 'on'
        )
        
        db.session.add(update)
        db.session.commit()
        
        # Envoyer des notifications aux investisseurs si demandé
        if update.notify_investors:
            for contribution in project.contributions.filter_by(status=ContributionStatus.COMPLETED):
                try:
                    EmailService.send_project_update_notification(contribution.investor, project, update)
                except Exception as e:
                    current_app.logger.error(f"Erreur envoi notification: {e}")
        
        flash('Mise à jour publiée avec succès', 'success')
        return redirect(url_for('main.project_detail', project_id=project_id))
    
    return render_template('projects/create_update.html', project=project)


# ============================================================================
# FORMATIONS
# ============================================================================

@bp.route('/trainings')
def trainings():
    """Liste des formations"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category')
    language = request.args.get('lang', 'ht')
    
    query = Training.query.filter_by(is_published=True)
    
    if category:
        query = query.filter_by(category=category)
    
    pagination = query.order_by(Training.sort_order).paginate(page=page, per_page=12, error_out=False)
    
    return render_template('trainings/list.html', trainings=pagination, language=language)


@bp.route('/training/<int:training_id>')
def training_detail(training_id):
    """Détail d'une formation"""
    training = Training.query.get_or_404(training_id)
    language = request.args.get('lang', 'ht')
    
    # Progression de l'utilisateur (si connecté et agriculteur)
    progress = None
    if current_user.is_authenticated and current_user.is_farmer:
        progress = TrainingProgress.query.filter_by(
            farmer_id=current_user.id,
            training_id=training_id
        ).first()
    
    return render_template('trainings/detail.html', training=training, progress=progress, language=language)


@bp.route('/training/<int:training_id>/progress', methods=['POST'])
@login_required
@farmer_required
def update_training_progress(training_id):
    """Mettre à jour la progression d'une formation"""
    data = request.get_json()
    
    progress = TrainingProgress.query.filter_by(
        farmer_id=current_user.id,
        training_id=training_id
    ).first()
    
    if not progress:
        progress = TrainingProgress(
            farmer_id=current_user.id,
            training_id=training_id
        )
        db.session.add(progress)
    
    if data.get('progress_percentage'):
        progress.progress_percentage = data['progress_percentage']
    
    if data.get('last_position_seconds'):
        progress.last_position_seconds = data['last_position_seconds']
    
    if data.get('completed'):
        progress.mark_completed()
    
    db.session.commit()
    
    return jsonify({'success': True, 'progress': progress.progress_percentage})


# ============================================================================
# MÉTÉO
# ============================================================================

@bp.route('/weather')
def weather():
    """Page météo agricole"""
    department = request.args.get('department')
    
    # Récupérer les alertes actives
    alerts = WeatherAlert.query.filter(
        WeatherAlert.is_active == True,
        WeatherAlert.ends_at >= utc_now()
    ).order_by(WeatherAlert.severity.desc()).all()
    
    # Abonnement utilisateur
    subscription = None
    if current_user.is_authenticated and current_user.is_farmer:
        subscription = WeatherSubscription.query.filter_by(
            farmer_id=current_user.id,
            is_active=True
        ).first()
    
    return render_template('weather.html', alerts=alerts, subscription=subscription, department=department)


@bp.route('/weather/subscribe', methods=['POST'])
@login_required
@farmer_required
def subscribe_weather():
    """S'abonner aux alertes météo"""
    zone = request.form.get('zone')
    
    subscription = WeatherSubscription.query.filter_by(
        farmer_id=current_user.id,
        zone=zone
    ).first()
    
    if not subscription:
        subscription = WeatherSubscription(
            farmer_id=current_user.id,
            zone=zone,
            receive_sms=request.form.get('receive_sms') == 'on',
            receive_whatsapp=request.form.get('receive_whatsapp') == 'on',
            phone_number=request.form.get('phone_number', current_user.phone)
        )
        db.session.add(subscription)
    else:
        subscription.is_active = True
        subscription.receive_sms = request.form.get('receive_sms') == 'on'
        subscription.receive_whatsapp = request.form.get('receive_whatsapp') == 'on'
    
    db.session.commit()
    flash('Abonnement aux alertes météo activé', 'success')
    return redirect(url_for('main.weather'))


# ============================================================================
# GROUPES ET CAGNOTTES
# ============================================================================

@bp.route('/groups')
@login_required
def my_groups():
    """Mes cagnottes"""
    created_groups = GroupContribution.query.filter_by(created_by_id=current_user.id).all()
    
    # Groupes auxquels l'utilisateur a contribué
    contributed_ids = db.session.query(Contribution.group_id).filter_by(
        investor_id=current_user.id,
        status=ContributionStatus.COMPLETED
    ).distinct().all()
    
    contributed_groups = GroupContribution.query.filter(
        GroupContribution.id.in_([c[0] for c in contributed_ids if c[0]])
    ).all()
    
    return render_template('groups/list.html', 
                         created_groups=created_groups,
                         contributed_groups=contributed_groups)


@bp.route('/groups/create', methods=['GET', 'POST'])
@login_required
def create_group():
    """Créer une cagnotte"""
    if request.method == 'POST':
        try:
            group = GroupContribution(
                project_id=request.form.get('project_id'),
                created_by_id=current_user.id,
                group_name=request.form.get('group_name'),
                group_type=request.form.get('group_type', 'family'),
                target_amount=Decimal(request.form.get('target_amount')),
                currency=request.form.get('currency', 'USD'),
                expires_at=datetime.fromisoformat(request.form.get('expires_at')) if request.form.get('expires_at') else None,
                is_public=request.form.get('is_public') == 'on'
            )
            
            db.session.add(group)
            db.session.commit()
            
            flash('Cagnotte créée avec succès !', 'success')
            return redirect(url_for('main.my_groups'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur création cagnotte: {e}")
            flash('Une erreur est survenue.', 'danger')
    
    projects = Project.query.filter_by(is_published=True).all()
    return render_template('groups/create.html', projects=projects)


# ============================================================================
# NEWSLETTER
# ============================================================================

@bp.route('/newsletter', methods=['POST'])
def newsletter():
    """Inscription à la newsletter"""
    email = request.form.get('email')
    
    if not validate_email(email):
        flash('Email invalide', 'danger')
        return redirect(request.referrer or url_for('main.home'))
    
    # Ajouter à la liste de newsletter (à implémenter)
    flash('Inscription à la newsletter réussie !', 'success')
    return redirect(request.referrer or url_for('main.home'))


# ============================================================================
# RECHERCHE
# ============================================================================

@bp.route('/search')
def search():
    """Recherche globale"""
    q = request.args.get('q', '')
    
    if not q:
        return redirect(url_for('main.home'))
    
    projects = Project.query.filter(
        Project.is_published == True,
        Project.title.ilike(f'%{q}%') | Project.description.ilike(f'%{q}%')
    ).limit(20).all()
    
    trainings = Training.query.filter(
        Training.is_published == True,
        Training.title_ht.ilike(f'%{q}%') | Training.description_ht.ilike(f'%{q}%')
    ).limit(10).all()
    
    return render_template('search_results.html', 
                         query=q, 
                         projects=projects, 
                         trainings=trainings)

@bp.route('/generate-qr-token')
@login_required
def generate_qr_token():
    """Génère un token pour connexion par QR code"""
    import secrets
    import pyqrcode
    from io import BytesIO
    import base64
    
    token = secrets.token_urlsafe(32)
    # Stocker le token en cache avec expiration 5 minutes
    # À implémenter avec Redis ou cache simple
    
    # Générer l'URL
    qr_url = url_for('main.qr_login', token=token, _external=True)
    
    # Générer l'image QR code (simplifié)
    import qrcode
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    # Stocker le token (simplifié - à remplacer par Redis)
    session[f'qr_token_{token}'] = current_user.id
    
    return jsonify({
        'qr_code': f'data:image/png;base64,{qr_base64}',
        'token': token
    })


@bp.route('/qr-login/<token>')
def qr_login(token):
    """Validation du QR code par l'application mobile"""
    user_id = session.get(f'qr_token_{token}')
    if user_id:
        user = User.query.get(int(user_id))
        if user:
            login_user(user)
            session.pop(f'qr_token_{token}', None)
            return redirect(url_for('main.dashboard'))
    flash('QR code invalide ou expiré', 'danger')
    return redirect(url_for('main.login'))


@bp.route('/check-qr-status')
def check_qr_status():
    """Vérifie si le QR code a été scanné"""
    token = request.args.get('token')
    if token and session.get(f'qr_token_{token}'):
        # Vérifier si l'utilisateur s'est connecté
        # Simulé - à implémenter avec un système de statut
        return jsonify({'authenticated': False})
    return jsonify({'authenticated': False})


@bp.route('/social-login')
def social_login():
    """Connexion via réseaux sociaux (Google/Facebook)"""
    provider = request.args.get('provider')
    # À implémenter avec OAuth
    flash(f'Connexion avec {provider} à implémenter', 'info')
    return redirect(url_for('main.login'))

@bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Supprimer définitivement le compte utilisateur"""
    user = current_user
    
    # Soft delete - désactiver le compte
    user.is_active = False
    user.is_verified = False
    user.email = f"deleted_{user.id}_{user.email}"
    user.name = "Compte supprimé"
    
    db.session.commit()
    logout_user()
    
    flash('Votre compte a été supprimé avec succès. Nous sommes tristes de vous voir partir.', 'info')
    return redirect(url_for('main.home'))

# ============================================================================
# HANDLERS D'ERREURS
# ============================================================================

@bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500


@bp.app_errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403