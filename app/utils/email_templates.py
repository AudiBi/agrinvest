# app/utils/email_templates.py
"""
Génération de templates d'emails pour AgriInvest Haïti
"""

from flask import render_template


def render_email_template(template_name, **kwargs):
    """
    Rend un template d'email
    
    Args:
        template_name: Nom du template (sans extension)
        **kwargs: Variables pour le template
    
    Returns:
        HTML et texte brut
    """
    html = render_template(f'email/{template_name}.html', **kwargs)
    text = render_template(f'email/{template_name}.txt', **kwargs)
    
    return html, text


def render_contribution_confirmation(contribution):
    """
    Template de confirmation de contribution
    """
    return render_email_template(
        'contribution_confirmation',
        contribution=contribution,
        investor=contribution.investor,
        project=contribution.project
    )


def render_project_funded_notification(project, investor):
    """
    Template de notification de projet financé
    """
    return render_email_template(
        'project_funded',
        project=project,
        investor=investor
    )


def render_welcome_email(user):
    """
    Template d'email de bienvenue
    """
    return render_email_template(
        'welcome',
        user=user
    )


def render_password_reset_email(user, token):
    """
    Template d'email de réinitialisation
    """
    from flask import url_for
    reset_url = url_for('main.reset_password', token=token, _external=True)
    
    return render_email_template(
        'password_reset',
        user=user,
        reset_url=reset_url
    )


def render_project_update_email(project, update, investor):
    """
    Template d'email de mise à jour de projet
    """
    return render_email_template(
        'project_update',
        project=project,
        update=update,
        investor=investor
    )