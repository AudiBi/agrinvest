# app/utils/formatters.py
"""
Formateurs pour AgriInvest Haïti
"""

from datetime import datetime
import re
from app.utils.constants import CURRENCY_SYMBOLS


def format_investor_name(investor):
    """
    Formate le nom d'un investisseur
    
    Args:
        investor: Objet User
    
    Returns:
        Nom formaté
    """
    if not investor:
        return "Anonyme"
    
    if hasattr(investor, 'is_anonymous') and investor.is_anonymous:
        return "Investisseur anonyme"
    
    return investor.name


def format_project_title(project):
    """
    Formate le titre d'un projet
    
    Args:
        project: Objet Project
    
    Returns:
        Titre formaté
    """
    if not project:
        return ""
    
    return project.title


def format_contribution_amount(contribution):
    """
    Formate le montant d'une contribution
    
    Args:
        contribution: Objet Contribution
    
    Returns:
        Montant formaté
    """
    if not contribution:
        return "0 HTG"
    
    currency = contribution.currency
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    
    return f"{contribution.amount:,.0f} {symbol}"


def format_investment_date(date):
    """
    Formate une date d'investissement
    
    Args:
        date: Date
    
    Returns:
        Date formatée
    """
    if not date:
        return ""
    
    if isinstance(date, str):
        try:
            date = datetime.fromisoformat(date)
        except ValueError:
            return date
    
    return date.strftime("%d/%m/%Y à %H:%M")


def format_project_deadline(deadline):
    """
    Formate la date limite d'un projet
    
    Args:
        deadline: Date limite
    
    Returns:
        Date formatée avec indication de temps restant
    """
    if not deadline:
        return "Non définie"
    
    if isinstance(deadline, str):
        try:
            deadline = datetime.fromisoformat(deadline)
        except ValueError:
            return deadline
    
    from app.utils.timezone import utc_now
    now = utc_now()
    
    if deadline < now:
        return "Expiré"
    
    days_left = (deadline - now).days
    
    if days_left == 0:
        return "Aujourd'hui"
    elif days_left == 1:
        return "Demain"
    else:
        return f"{days_left} jours restants"


def format_phone_number(phone, country='HT'):
    """
    Formate un numéro de téléphone
    
    Args:
        phone: Numéro à formater
        country: Code pays
    
    Returns:
        Numéro formaté
    """
    if not phone:
        return ""
    
    # Supprimer les espaces et caractères spéciaux
    phone = re.sub(r'[^\d+]', '', phone)
    
    if country == 'HT' and phone.startswith('509'):
        return f"+{phone}"
    elif country == 'HT' and phone.startswith('0'):
        return f"+509{phone[1:]}"
    
    return phone