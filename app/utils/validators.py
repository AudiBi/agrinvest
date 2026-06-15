# app/utils/validators.py
"""
Validateurs de données pour AgriInvest Haïti
"""

import re
from decimal import Decimal
from datetime import datetime
from app.utils.constants import MIN_CONTRIBUTION_AMOUNT, MAX_CONTRIBUTION_AMOUNT


def validate_email(email):
    """
    Valide le format d'un email
    
    Args:
        email: Adresse email à valider
    
    Returns:
        bool: True si valide, False sinon
    """
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password):
    """
    Valide la force du mot de passe
    
    Args:
        password: Mot de passe à valider
    
    Returns:
        bool: True si valide, False sinon
    """
    if not password:
        return False
    
    # Au moins 8 caractères
    if len(password) < 8:
        return False
    
    # Au moins une majuscule
    if not re.search(r'[A-Z]', password):
        return False
    
    # Au moins une minuscule
    if not re.search(r'[a-z]', password):
        return False
    
    # Au moins un chiffre
    if not re.search(r'[0-9]', password):
        return False
    
    return True


def validate_phone_number(phone, country='HT'):
    """
    Valide le format d'un numéro de téléphone
    
    Args:
        phone: Numéro à valider
        country: Code pays (HT, US, CA, FR)
    
    Returns:
        bool: True si valide, False sinon
    """
    if not phone:
        return False
    
    patterns = {
        'HT': r'^(?:(?:\+509|0)?[34]\d{7})$',
        'US': r'^(?:(?:\+1|1)?[2-9]\d{2}[2-9]\d{6})$',
        'CA': r'^(?:(?:\+1|1)?[2-9]\d{2}[2-9]\d{6})$',
        'FR': r'^(?:(?:\+33|0)[1-9]\d{8})$',
    }
    
    pattern = patterns.get(country, patterns['HT'])
    return re.match(pattern, phone) is not None


def validate_contribution_amount(amount, project=None):
    """
    Valide le montant d'une contribution
    
    Args:
        amount: Montant à valider
        project: Projet concerné (optionnel)
    
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        amount = Decimal(str(amount))
    except (ValueError, TypeError):
        return False, "Montant invalide"
    
    if amount < MIN_CONTRIBUTION_AMOUNT:
        return False, f"Le montant minimum est de {MIN_CONTRIBUTION_AMOUNT} HTG"
    
    if amount > MAX_CONTRIBUTION_AMOUNT:
        return False, f"Le montant maximum est de {MAX_CONTRIBUTION_AMOUNT} HTG"
    
    if project:
        if amount < project.min_investment:
            return False, f"L'investissement minimum pour ce projet est de {project.min_investment} HTG"
        
        if project.max_investment and amount > project.max_investment:
            return False, f"L'investissement maximum pour ce projet est de {project.max_investment} HTG"
    
    return True, None


def validate_project_data(data):
    """
    Valide les données d'un projet
    
    Args:
        data: Dictionnaire des données du projet
    
    Returns:
        tuple: (is_valid, errors_dict)
    """
    errors = {}
    
    # Titre
    if not data.get('title'):
        errors['title'] = "Le titre est requis"
    elif len(data['title']) < 5:
        errors['title'] = "Le titre doit contenir au moins 5 caractères"
    elif len(data['title']) > 200:
        errors['title'] = "Le titre ne doit pas dépasser 200 caractères"
    
    # Description
    if not data.get('description'):
        errors['description'] = "La description est requise"
    elif len(data['description']) < 50:
        errors['description'] = "La description doit contenir au moins 50 caractères"
    
    # Montant nécessaire
    try:
        amount_needed = Decimal(str(data.get('amount_needed', 0)))
        if amount_needed < MIN_CONTRIBUTION_AMOUNT * 10:
            errors['amount_needed'] = f"Le montant doit être au moins de {MIN_CONTRIBUTION_AMOUNT * 10} HTG"
        elif amount_needed > 50000000:
            errors['amount_needed'] = "Le montant ne peut pas dépasser 50,000,000 HTG"
    except (ValueError, TypeError):
        errors['amount_needed'] = "Montant invalide"
    
    # Date limite
    if data.get('deadline'):
        try:
            deadline = datetime.fromisoformat(data['deadline'].replace('Z', '+00:00'))
            from app.utils.timezone import utc_now
            if deadline < utc_now():
                errors['deadline'] = "La date limite doit être dans le futur"
        except ValueError:
            errors['deadline'] = "Date invalide"
    
    return len(errors) == 0, errors


def validate_user_registration(data):
    """
    Valide les données d'inscription utilisateur
    
    Args:
        data: Dictionnaire des données d'inscription
    
    Returns:
        tuple: (is_valid, errors_dict)
    """
    errors = {}
    
    # Nom
    if not data.get('name'):
        errors['name'] = "Le nom est requis"
    elif len(data['name']) < 2:
        errors['name'] = "Le nom doit contenir au moins 2 caractères"
    
    # Email
    email = data.get('email', '')
    if not email:
        errors['email'] = "L'email est requis"
    elif not validate_email(email):
        errors['email'] = "Email invalide"
    
    # Mot de passe
    password = data.get('password', '')
    if not password:
        errors['password'] = "Le mot de passe est requis"
    elif not validate_password(password):
        errors['password'] = "Le mot de passe doit contenir au moins 8 caractères avec une majuscule, une minuscule et un chiffre"
    
    # Confirmation
    if password != data.get('confirm_password'):
        errors['confirm_password'] = "Les mots de passe ne correspondent pas"
    
    # Rôle
    role = data.get('role', 'investor')
    if role not in ['investor', 'farmer']:
        errors['role'] = "Rôle invalide"
    
    return len(errors) == 0, errors


def validate_project_update(data):
    """
    Valide les données de mise à jour d'un projet
    
    Args:
        data: Dictionnaire des données
    
    Returns:
        tuple: (is_valid, errors_dict)
    """
    errors = {}
    
    if not data.get('title'):
        errors['title'] = "Le titre est requis"
    
    if not data.get('content'):
        errors['content'] = "Le contenu est requis"
    
    return len(errors) == 0, errors


def validate_user_profile_update(data):
    """
    Valide les données de mise à jour de profil
    
    Args:
        data: Dictionnaire des données
    
    Returns:
        tuple: (is_valid, errors_dict)
    """
    errors = {}
    
    if data.get('phone'):
        if not validate_phone_number(data['phone']):
            errors['phone'] = "Numéro de téléphone invalide"
    
    if data.get('email'):
        if not validate_email(data['email']):
            errors['email'] = "Email invalide"
    
    return len(errors) == 0, errors

def validate_slug(slug):
    """Valide le format d'un slug"""
    if not slug:
        return False
    import re
    pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
    return re.match(pattern, slug) is not None

def validate_url(url):
    """
    Valide le format d'une URL
    
    Args:
        url: URL à valider
    
    Returns:
        bool: True si valide, False sinon
    """
    if not url:
        return False
    
    pattern = r'^https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)$'
    return re.match(pattern, url) is not None