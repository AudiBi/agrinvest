# app/utils/permissions.py
"""
Gestion des permissions pour AgriInvest Haïti
"""

from flask_login import current_user
from functools import wraps
from flask import abort, flash, redirect, url_for


def check_permissions(user, resource, action):
    """
    Vérifie si un utilisateur a la permission d'effectuer une action
    
    Args:
        user: Objet utilisateur
        resource: Ressource concernée
        action: Action à vérifier (read, write, delete, etc.)
    
    Returns:
        bool: True si autorisé, False sinon
    """
    if not user or not user.is_authenticated:
        return False
    
    # Admin a tous les droits
    if user.is_admin:
        return True
    
    # Vérifications spécifiques
    if action == 'read':
        # Tout le monde peut lire les projets publiés
        if hasattr(resource, 'is_published') and resource.is_published:
            return True
    
    if action in ['write', 'update', 'delete']:
        # Seul le propriétaire peut modifier
        if hasattr(resource, 'farmer_id') and resource.farmer_id == user.id:
            return True
        if hasattr(resource, 'investor_id') and resource.investor_id == user.id:
            return True
    
    return False


def is_admin(user=None):
    """Vérifie si l'utilisateur est administrateur"""
    if user is None:
        user = current_user
    return user.is_authenticated and user.is_admin


def is_investor(user=None):
    """Vérifie si l'utilisateur est investisseur"""
    if user is None:
        user = current_user
    return user.is_authenticated and user.role == 'investor'


def is_farmer(user=None):
    """Vérifie si l'utilisateur est agriculteur"""
    if user is None:
        user = current_user
    return user.is_authenticated and user.role == 'farmer'


def is_project_owner(project, user=None):
    """Vérifie si l'utilisateur est propriétaire du projet"""
    if user is None:
        user = current_user
    return user.is_authenticated and project.farmer_id == user.id


def is_contribution_owner(contribution, user=None):
    """Vérifie si l'utilisateur est propriétaire de la contribution"""
    if user is None:
        user = current_user
    return user.is_authenticated and contribution.investor_id == user.id


def permission_required(permission):
    """Décorateur pour vérifier les permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Veuillez vous connecter', 'warning')
                return redirect(url_for('main.login'))
            
            if not check_permissions(current_user, None, permission):
                flash('Permission insuffisante', 'danger')
                return redirect(url_for('main.home'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator