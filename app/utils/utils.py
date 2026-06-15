# app/utils/utils.py
"""
Fonctions utilitaires générales pour AgriInvest Haïti
"""

import re
import random
import string
from decimal import Decimal
from datetime import datetime, timedelta, timezone


def utc_now():
    """Retourne la date UTC actuelle"""
    return datetime.now(timezone.utc)

def generate_random_string(length=10):
    """
    Génère une chaîne aléatoire
    
    Args:
        length: Longueur de la chaîne
    
    Returns:
        Chaîne aléatoire
    """
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for _ in range(length))


def calculate_investment_return(amount, interest_rate, duration_months):
    """
    Calcule le retour sur investissement
    
    Args:
        amount: Montant investi
        interest_rate: Taux d'intérêt annuel (%)
        duration_months: Durée en mois
    
    Returns:
        Montant total avec intérêts
    """
    amount = Decimal(str(amount))
    rate = Decimal(str(interest_rate)) / Decimal('100')
    
    # Intérêts composés mensuels
    monthly_rate = rate / Decimal('12')
    total = amount * (Decimal('1') + monthly_rate) ** duration_months
    
    return round(total, 2)


def validate_email(email):
    """
    Valide le format d'un email
    
    Args:
        email: Adresse email à valider
    
    Returns:
        bool: True si valide, False sinon
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone_number(phone, country='HT'):
    """
    Valide le format d'un numéro de téléphone
    
    Args:
        phone: Numéro à valider
        country: Code pays (HT, US, CA, FR)
    
    Returns:
        bool: True si valide, False sinon
    """
    patterns = {
        'HT': r'^(?:(?:\+509|0)?[34]\d{7})$',
        'US': r'^(?:(?:\+1|1)?[2-9]\d{2}[2-9]\d{6})$',
        'CA': r'^(?:(?:\+1|1)?[2-9]\d{2}[2-9]\d{6})$',
        'FR': r'^(?:(?:\+33|0)[1-9]\d{8})$',
    }
    
    pattern = patterns.get(country, patterns['HT'])
    return re.match(pattern, phone) is not None


def validate_url(url):
    """
    Valide le format d'une URL
    
    Args:
        url: URL à valider
    
    Returns:
        bool: True si valide, False sinon
    """
    pattern = r'^https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)$'
    return re.match(pattern, url) is not None


def calculate_project_progress(amount_raised, amount_needed):
    """
    Calcule la progression d'un projet
    
    Args:
        amount_raised: Montant collecté
        amount_needed: Montant nécessaire
    
    Returns:
        Pourcentage de progression
    """
    if not amount_needed or amount_needed == 0:
        return 0
    
    try:
        progress = (float(amount_raised) / float(amount_needed)) * 100
        return min(100, round(progress, 1))
    except (ValueError, TypeError):
        return 0


def slugify(text):
    """
    Convertit un texte en slug pour URL
    
    Args:
        text: Texte à convertir
    
    Returns:
        Slug
    """
    if not text:
        return ''
    
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')