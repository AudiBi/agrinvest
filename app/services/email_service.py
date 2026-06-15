# app/services/email_service.py
"""
Service d'envoi d'emails pour AgriInvest Haïti
"""

from flask import render_template, current_app
from flask_mail import Message
from app.extensions import mail


class EmailService:
    """Service d'envoi d'emails"""

    @staticmethod
    def send_email(to, subject, template, **kwargs):
        """Envoie un email générique"""
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
            current_app.logger.error(f"Erreur d'envoi d'email: {e}")
            return False

    @staticmethod
    def send_welcome_email(user):
        """Email de bienvenue"""
        return EmailService.send_email(
            to=user.email,
            subject='Bienvenue sur AgriInvest Haïti !',
            template='welcome',
            user=user
        )

    @staticmethod
    def send_contribution_confirmation(contribution):
        """Confirmation de contribution"""
        return EmailService.send_email(
            to=contribution.investor.email,
            subject=f'Confirmation de votre investissement - {contribution.project.title}',
            template='contribution_confirmation',
            contribution=contribution
        )

    @staticmethod
    def send_project_funded_notification(project):
        """Notification de projet financé"""
        for contribution in project.contributions:
            EmailService.send_email(
                to=contribution.investor.email,
                subject=f'Félicitations ! Le projet {project.title} est financé',
                template='project_funded',
                project=project,
                contribution=contribution
            )

    @staticmethod
    def send_password_reset_email(user, token):
        """Email de réinitialisation de mot de passe"""
        return EmailService.send_email(
            to=user.email,
            subject='Réinitialisation de votre mot de passe',
            template='password_reset',
            user=user,
            token=token
        )

    @staticmethod
    def send_project_update_notification(user, project, update):
        """Notification de mise à jour de projet"""
        return EmailService.send_email(
            to=user.email,
            subject=f'Nouvelle mise à jour - {project.title}',
            template='project_update',
            user=user,
            project=project,
            update=update
        )