# app/utils/pagination.py
"""
Fonctions de pagination pour AgriInvest Haïti
"""

from flask import request, url_for


def paginate_query(query, page=1, per_page=20, error_out=False):
    """
    Pagine une requête SQLAlchemy
    
    Args:
        query: Requête SQLAlchemy
        page: Numéro de page
        per_page: Nombre d'éléments par page
        error_out: Lever une erreur si page invalide
    
    Returns:
        Objet de pagination
    """
    return query.paginate(page=page, per_page=per_page, error_out=error_out)


def get_pagination_info(pagination, endpoint, **kwargs):
    """
    Génère les informations de pagination pour les templates
    
    Args:
        pagination: Objet de pagination SQLAlchemy
        endpoint: Nom du blueprint
        **kwargs: Paramètres supplémentaires pour l'URL
    
    Returns:
        Dictionnaire avec les informations de pagination
    """
    return {
        'current_page': pagination.page,
        'total_pages': pagination.pages,
        'total_items': pagination.total,
        'per_page': pagination.per_page,
        'has_prev': pagination.has_prev,
        'has_next': pagination.has_next,
        'prev_num': pagination.prev_num,
        'next_num': pagination.next_num,
        'items': pagination.items,
        'pages': pagination.iter_pages(),
        'url_for_page': lambda p: url_for(endpoint, page=p, **kwargs)
    }


def generate_pagination_links(pagination, endpoint, **kwargs):
    """
    Génère les liens de pagination HTML
    
    Args:
        pagination: Objet de pagination
        endpoint: Nom du blueprint
        **kwargs: Paramètres supplémentaires
    
    Returns:
        HTML des liens de pagination
    """
    links = []
    
    if pagination.has_prev:
        links.append({
            'url': url_for(endpoint, page=pagination.prev_num, **kwargs),
            'label': '« Précédent',
            'active': False
        })
    
    for page in pagination.iter_pages():
        if page:
            if page == pagination.page:
                links.append({
                    'url': '#',
                    'label': str(page),
                    'active': True
                })
            else:
                links.append({
                    'url': url_for(endpoint, page=page, **kwargs),
                    'label': str(page),
                    'active': False
                })
        else:
            links.append({
                'url': '#',
                'label': '...',
                'active': False
            })
    
    if pagination.has_next:
        links.append({
            'url': url_for(endpoint, page=pagination.next_num, **kwargs),
            'label': 'Suivant »',
            'active': False
        })
    
    return links