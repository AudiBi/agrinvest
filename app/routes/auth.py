# app/routes/auth.py
"""
Routes d'authentification pour l'interface web AgriInvest Haïti
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timezone

from app.models import User
from app.extensions import db, login_throttle
from app.utils.validators import validate_email, validate_password


# Création du blueprint
auth_bp = Blueprint('auth', __name__)


def utc_now():
    """Retourne la date UTC actuelle"""
    return datetime.now(timezone.utc)


# ============================================================================
# ROUTES D'AUTHENTIFICATION
# ============================================================================

@auth_bp.route('/login', methods=['GET', 'POST'])
@login_throttle
def login():
    """Page de connexion"""
    # Rediriger si déjà connecté
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        # Validation des champs
        if not email or not password:
            flash('Veuillez remplir tous les champs', 'danger')
            return render_template('login.html')
        
        # Recherche de l'utilisateur
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Votre compte est désactivé. Veuillez contacter l\'administrateur.', 'danger')
                return render_template('login.html')
            
            # Connexion réussie
            login_user(user, remember=remember)
            user.last_login_at = utc_now()
            db.session.commit()
            
            # Redirection après connexion
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            
            flash(f'Bienvenue {user.name} !', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Email ou mot de passe incorrect', 'danger')
    
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Déconnexion"""
    logout_user()
    flash('Vous avez été déconnecté avec succès.', 'info')
    return redirect(url_for('main.home'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Page d'inscription"""
    # Rediriger si déjà connecté
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        # Récupération des données
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'investor')
        phone = request.form.get('phone', '').strip()
        country = request.form.get('country', 'HT')
        
        # Validation des champs obligatoires
        if not name or not email or not password:
            flash('Tous les champs sont requis', 'danger')
            return render_template('register.html')
        
        # Validation de la confirmation du mot de passe
        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas', 'danger')
            return render_template('register.html')
        
        # Validation de l'email
        if not validate_email(email):
            flash('Adresse email invalide', 'danger')
            return render_template('register.html')
        
        # Validation du mot de passe
        if not validate_password(password):
            flash('Le mot de passe doit contenir au moins 8 caractères avec une majuscule, une minuscule et un chiffre', 'danger')
            return render_template('register.html')
        
        # Vérification si l'email existe déjà
        if User.query.filter_by(email=email).first():
            flash('Cet email est déjà utilisé', 'danger')
            return render_template('register.html')
        
        # Validation du rôle
        if role not in ['investor', 'farmer']:
            role = 'investor'
        
        try:
            # Création de l'utilisateur
            user = User(
                name=name,
                email=email,
                role=role,
                phone=phone,
                country=country,
                preferred_currency='USD' if country != 'HT' else 'HTG',
                preferred_language='ht',
                is_active=True,
                is_verified=False
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # Connexion automatique après inscription
            login_user(user)
            
            flash('Inscription réussie ! Bienvenue sur AgriInvest Haïti.', 'success')
            return redirect(url_for('main.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur lors de l'inscription: {e}")
            flash('Une erreur est survenue lors de l\'inscription. Veuillez réessayer.', 'danger')
    
    return render_template('register.html')


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Page de profil utilisateur"""
    if request.method == 'POST':
        # Mise à jour du profil
        current_user.name = request.form.get('name', current_user.name)
        current_user.phone = request.form.get('phone', current_user.phone)
        current_user.location = request.form.get('location', current_user.location)
        current_user.bio = request.form.get('bio', current_user.bio)
        current_user.preferred_currency = request.form.get('preferred_currency', 'HTG')
        current_user.preferred_language = request.form.get('preferred_language', 'ht')
        
        db.session.commit()
        flash('Profil mis à jour avec succès', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('profile.html')


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Changement de mot de passe"""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Vérification de l'ancien mot de passe
        if not current_user.check_password(current_password):
            flash('Mot de passe actuel incorrect', 'danger')
            return render_template('change_password.html')
        
        # Validation du nouveau mot de passe
        if new_password != confirm_password:
            flash('Les nouveaux mots de passe ne correspondent pas', 'danger')
            return render_template('change_password.html')
        
        if not validate_password(new_password):
            flash('Le mot de passe doit contenir au moins 8 caractères avec une majuscule, une minuscule et un chiffre', 'danger')
            return render_template('change_password.html')
        
        # Mise à jour du mot de passe
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('Mot de passe modifié avec succès', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('change_password.html')


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def is_safe_url(target):
    """
    Vérifie que l'URL de redirection est sécurisée
    Évite les attaques de type open redirect
    """
    from urllib.parse import urlparse, urljoin
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc