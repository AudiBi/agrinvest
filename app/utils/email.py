# app/utils/email.py
"""
Envoi d'emails pour AgriInvest Haïti
"""

from flask import render_template, current_app
from flask_mail import Message
from app.extensions import mail


def send_email(to, subject, template, **kwargs):
    """
    Envoie un email générique
    
    Args:
        to: Destinataire
        subject: Sujet
        template: Nom du template (sans extension)
        **kwargs: Variables pour le template
    
    Returns:
        bool: Succès ou échec
    """
    try:
        msg = Message(
            subject=subject,
            recipients=[to],
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@agrinvest.ht'),
            html=render_template(f'email/{template}.html', **kwargs),
            body=render_template(f'email/{template}.txt', **kwargs)
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Email error: {e}")
        return False


def send_welcome_email(user):
    """Email de bienvenue"""
    return send_email(
        to=user.email,
        subject="Bienvenue sur AgriInvest Haïti !",
        template="welcome",
        user=user
    )


def send_contribution_confirmation_email(contribution):
    """Email de confirmation de contribution"""
    return send_email(
        to=contribution.investor.email,
        subject=f"Confirmation de votre investissement - {contribution.project.title}",
        template="contribution_confirmation",
        contribution=contribution
    )


def send_project_funded_notification_email(project, investor):
    """Email de notification de projet financé"""
    return send_email(
        to=investor.email,
        subject=f"Félicitations ! Le projet {project.title} est financé",
        template="project_funded",
        project=project,
        investor=investor
    )


def send_password_reset_email(user, token):
    """Email de réinitialisation de mot de passe"""
    reset_url = f"{current_app.config.get('BASE_URL')}/reset-password/{token}"
    return send_email(
        to=user.email,
        subject="Réinitialisation de votre mot de passe",
        template="password_reset",
        user=user,
        reset_url=reset_url
    )


def send_project_update_notification_email(investor, project, update):
    """Email de notification de mise à jour de projet"""
    return send_email(
        to=investor.email,
        subject=f"Nouvelle mise à jour - {project.title}",
        template="project_update",
        investor=investor,
        project=project,
        update=update
    )