# app/utils/config.py
"""
Gestion de configuration pour AgriInvest Haïti
"""

from flask import current_app
import json
import os


def load_config(config_file=None):
    """
    Charge la configuration depuis un fichier
    
    Args:
        config_file: Chemin du fichier de configuration
    
    Returns:
        Dictionnaire de configuration
    """
    if config_file is None:
        config_file = os.path.join(current_app.root_path, 'config.json')
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_config_value(key, default=None):
    """
    Récupère une valeur de configuration
    
    Args:
        key: Clé de configuration
        default: Valeur par défaut
    
    Returns:
        Valeur de configuration
    """
    # Priorité: app.config > config.json > default
    value = current_app.config.get(key)
    
    if value is not None:
        return value
    
    # Essayer de charger depuis config.json
    config = load_config()
    return config.get(key, default)


def set_config_value(key, value, config_file=None):
    """
    Définit une valeur de configuration
    
    Args:
        key: Clé de configuration
        value: Valeur à définir
        config_file: Chemin du fichier de configuration
    
    Returns:
        bool: True si réussi
    """
    if config_file is None:
        config_file = os.path.join(current_app.root_path, 'config.json')
    
    try:
        config = load_config(config_file)
        config[key] = value
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception:
        return False


def get_platform_settings():
    """
    Récupère les paramètres de la plateforme
    
    Returns:
        Dictionnaire des paramètres
    """
    return {
        'app_name': get_config_value('APP_NAME', 'AgriInvest Haïti'),
        'commission_rate': get_config_value('COMMISSION_RATE', 3.0),
        'min_contribution': get_config_value('MIN_CONTRIBUTION', 100),
        'max_contribution': get_config_value('MAX_CONTRIBUTION', 10000000),
        'site_url': get_config_value('SITE_URL', 'https://agrinvest.ht'),
        'support_email': get_config_value('SUPPORT_EMAIL', 'support@agrinvest.ht'),
        'facebook_url': get_config_value('FACEBOOK_URL', '#'),
        'twitter_url': get_config_value('TWITTER_URL', '#'),
        'instagram_url': get_config_value('INSTAGRAM_URL', '#'),
        'linkedin_url': get_config_value('LINKEDIN_URL', '#')
    }