# app/utils/data.py
"""
Sérialisation des données pour AgriInvest Haïti
"""

from decimal import Decimal
from datetime import datetime


def serialize_contribution(contribution):
    """
    Sérialise une contribution pour l'API
    
    Args:
        contribution: Objet Contribution
    
    Returns:
        Dict sérialisé
    """
    if not contribution:
        return None
    
    return {
        'id': contribution.id,
        'investor_id': contribution.investor_id,
        'investor_name': contribution.investor.name if contribution.investor else None,
        'project_id': contribution.project_id,
        'project_title': contribution.project.title if contribution.project else None,
        'amount': float(contribution.amount),
        'amount_htg': float(contribution.amount_htg),
        'currency': contribution.currency,
        'status': contribution.status,
        'is_anonymous': contribution.is_anonymous,
        'message': contribution.message if not contribution.is_anonymous else None,
        'payment_method': contribution.payment_method,
        'created_at': contribution.created_at.isoformat() if contribution.created_at else None,
        'completed_at': contribution.completed_at.isoformat() if contribution.completed_at else None
    }


def serialize_project(project):
    """
    Sérialise un projet pour l'API
    
    Args:
        project: Objet Project
    
    Returns:
        Dict sérialisé
    """
    if not project:
        return None
    
    return {
        'id': project.id,
        'title': project.title,
        'slug': project.slug,
        'description': project.description,
        'short_description': project.short_description,
        'location': project.location,
        'department': project.department,
        'category': project.category,
        'image_url': project.image_url,
        'amount_needed': float(project.amount_needed),
        'amount_raised': float(project.amount_raised),
        'progress': project.progress_percentage,
        'status': project.status,
        'farmer_id': project.farmer_id,
        'farmer_name': project.farmer.name if project.farmer else None,
        'investor_count': project.investor_count,
        'days_remaining': project.days_remaining,
        'created_at': project.created_at.isoformat() if project.created_at else None,
        'deadline': project.deadline.isoformat() if project.deadline else None
    }


def serialize_user(user, include_email=False):
    """
    Sérialise un utilisateur pour l'API
    
    Args:
        user: Objet User
        include_email: Inclure l'email
    
    Returns:
        Dict sérialisé
    """
    if not user:
        return None
    
    data = {
        'id': user.id,
        'name': user.name,
        'role': user.role,
        'avatar_url': user.avatar_url,
        'location': user.location,
        'country': user.country,
        'is_verified': user.is_verified,
        'is_diaspora': user.country and user.country != 'HT',
        'created_at': user.created_at.isoformat() if user.created_at else None
    }
    
    if include_email:
        data['email'] = user.email
        data['phone'] = user.phone
    
    return data


def serialize_list(items, serializer_func):
    """
    Sérialise une liste d'objets
    
    Args:
        items: Liste d'objets
        serializer_func: Fonction de sérialisation
    
    Returns:
        Liste sérialisée
    """
    return [serializer_func(item) for item in items if item]