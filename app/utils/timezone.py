# app/utils/timezone.py
"""
Gestion des fuseaux horaires pour AgriInvest Haïti
"""

from datetime import datetime, timezone, timedelta
from flask import session
from flask_login import current_user


# Fuseau horaire d'Haïti (UTC-5)
HAITI_TIMEZONE = timezone(timedelta(hours=-5))


def utc_now():
    """
    Retourne la date UTC actuelle
    
    Returns:
        datetime UTC
    """
    return datetime.now(timezone.utc)


def convert_to_timezone(dt, target_tz=HAITI_TIMEZONE):
    """
    Convertit une date dans un fuseau horaire
    
    Args:
        dt: Datetime à convertir
        target_tz: Fuseau horaire cible
    
    Returns:
        Datetime convertie
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt.astimezone(target_tz)


def get_user_timezone():
    """
    Récupère le fuseau horaire de l'utilisateur
    
    Returns:
        Fuseau horaire
    """
    # Par défaut, Haïti
    if current_user and current_user.is_authenticated:
        # Si l'utilisateur a un pays, déterminer le fuseau
        country = current_user.country
        if country == 'US':
            return timezone(timedelta(hours=-5))  # EST
        elif country == 'CA':
            return timezone(timedelta(hours=-5))  # EST
        elif country == 'FR':
            return timezone(timedelta(hours=1))   # CET
        elif country == 'HT':
            return HAITI_TIMEZONE
    
    return HAITI_TIMEZONE


def format_user_time(dt, format='%d/%m/%Y %H:%M'):
    """
    Formate une date selon le fuseau utilisateur
    
    Args:
        dt: Datetime
        format: Format de sortie
    
    Returns:
        Date formatée
    """
    if dt is None:
        return ''
    
    user_tz = get_user_timezone()
    local_dt = convert_to_timezone(dt, user_tz)
    return local_dt.strftime(format)