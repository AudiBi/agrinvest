# app/utils/logger.py
"""
Système de logging pour AgriInvest Haïti
"""

import logging
from flask import current_app, request, session
from functools import wraps
from datetime import datetime


def get_logger():
    """Retourne le logger de l'application"""
    return current_app.logger


def log_action(user_id, action, resource_type, resource_id, details=None):
    """
    Enregistre une action utilisateur dans les logs
    
    Args:
        user_id: ID de l'utilisateur
        action: Action effectuée
        resource_type: Type de ressource
        resource_id: ID de la ressource
        details: Détails supplémentaires
    """
    logger = get_logger()
    
    log_data = {
        'user_id': user_id,
        'action': action,
        'resource_type': resource_type,
        'resource_id': resource_id,
        'ip_address': request.remote_addr,
        'user_agent': request.user_agent.string if request.user_agent else None,
        'timestamp': datetime.utcnow().isoformat(),
        'details': details
    }
    
    logger.info(f"ACTION: {log_data}")


def log_error(error, context=None):
    """
    Enregistre une erreur dans les logs
    
    Args:
        error: Exception ou message d'erreur
        context: Contexte supplémentaire
    """
    logger = get_logger()
    logger.error(f"ERROR: {error}", exc_info=True, extra={'context': context})


def log_info(message, data=None):
    """Enregistre un message d'information"""
    logger = get_logger()
    logger.info(f"INFO: {message}", extra={'data': data})


def log_warning(message, data=None):
    """Enregistre un avertissement"""
    logger = get_logger()
    logger.warning(f"WARNING: {message}", extra={'data': data})


def log_api_call(f):
    """Décorateur pour logger les appels API"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = datetime.utcnow()
        
        # Exécuter la fonction
        result = f(*args, **kwargs)
        
        # Calculer la durée
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Logger l'appel
        log_info(
            f"API Call: {request.method} {request.path}",
            {
                'status_code': getattr(result, 'status_code', 200),
                'duration_ms': round(duration * 1000, 2),
                'ip': request.remote_addr
            }
        )
        
        return result
    return decorated_function