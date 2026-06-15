# app/utils/seo.py
"""
SEO et métadonnées pour AgriInvest Haïti
"""

from flask import current_app, url_for


def generate_seo_metadata(title, description, image=None, url=None, type='website'):
    """
    Génère les métadonnées SEO
    
    Args:
        title: Titre de la page
        description: Description
        image: URL de l'image
        url: URL de la page
        type: Type de contenu
    
    Returns:
        Dict avec les métadonnées
    """
    site_name = current_app.config.get('APP_NAME', 'AgriInvest Haïti')
    
    metadata = {
        'title': f"{title} | {site_name}",
        'description': description,
        'og': {
            'title': title,
            'description': description,
            'type': type,
            'site_name': site_name
        },
        'twitter': {
            'card': 'summary_large_image',
            'title': title,
            'description': description
        }
    }
    
    if image:
        if not image.startswith('http'):
            image = url_for('static', filename=image, _external=True)
        metadata['og']['image'] = image
        metadata['twitter']['image'] = image
    
    if url:
        metadata['og']['url'] = url
    
    return metadata


def create_sitemap():
    """
    Génère un sitemap.xml
    
    Returns:
        Liste des URLs
    """
    from app.models import Project
    
    urls = []
    
    # Pages statiques
    static_pages = ['/', '/projects', '/about', '/contact', '/faq', '/trainings']
    for page in static_pages:
        urls.append({
            'loc': url_for('main.home', _external=True) if page == '/' else url_for(f'main.{page[1:]}', _external=True),
            'changefreq': 'weekly',
            'priority': 1.0 if page == '/' else 0.8
        })
    
    # Projets
    projects = Project.query.filter_by(is_published=True).all()
    for project in projects:
        urls.append({
            'loc': url_for('main.project_detail', project_id=project.id, _external=True),
            'changefreq': 'monthly',
            'priority': 0.9,
            'lastmod': project.updated_at.isoformat() if project.updated_at else None
        })
    
    return urls


def generate_meta_tags(metadata):
    """
    Génère les balises meta HTML
    
    Args:
        metadata: Dict des métadonnées
    
    Returns:
        HTML des balises meta
    """
    html = []
    
    # Balises de base
    html.append(f'<title>{metadata["title"]}</title>')
    html.append(f'<meta name="description" content="{metadata["description"]}">')
    
    # Open Graph
    for key, value in metadata.get('og', {}).items():
        html.append(f'<meta property="og:{key}" content="{value}">')
    
    # Twitter Card
    for key, value in metadata.get('twitter', {}).items():
        html.append(f'<meta name="twitter:{key}" content="{value}">')
    
    return '\n'.join(html)


def create_robots_txt():
    """
    Génère un fichier robots.txt
    
    Returns:
        Contenu du robots.txt
    """
    content = """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /dashboard/
Disallow: /profile/
Disallow: /api/
Disallow: /auth/

Sitemap: {{ url_for('main.sitemap', _external=True) }}
"""
    return content