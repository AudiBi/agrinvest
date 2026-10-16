# app/services/email_service.py
"""
Service d'envoi d'emails pour AgriInvest Haïti
"""

import re
from html import unescape

from flask import render_template, current_app
from flask_mail import Message
from app.extensions import mail


def _html_to_text(html):
    """Version texte brut d'un email HTML (liens conservés), pour les clients sans HTML."""
    html = re.sub(r'(?is)<(style|head|script).*?</\1>', '', html)
    html = re.sub(r'(?is)<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r'\2 (\1)', html)
    html = re.sub(r'(?i)<br\s*/?>|</p>|</h[1-6]>|</div>', '\n', html)
    text = unescape(re.sub(r'<[^>]+>', '', html))
    return re.sub(r'\n\s*\n+', '\n\n', text).strip()


def _base_url():
    """URL publique du site, issue de la configuration.

    Jamais de l'en-tête Host de la requête : un attaquant pourrait forger un lien de
    réinitialisation pointant vers son propre domaine.
    """
    return (current_app.config.get('BASE_URL') or 'http://localhost:5000').rstrip('/')


class EmailService:
    """Service d'envoi d'emails"""

    @staticmethod
    def send_email(to, subject, template, **kwargs):
        """Envoie un email à partir du gabarit email/<template>.html (texte brut généré)"""
        try:
            html = render_template(f'email/{template}.html', base_url=_base_url(), **kwargs)
            msg = Message(
                subject=subject,
                recipients=[to],
                sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@agrinvest.ht'),
                html=html,
                body=_html_to_text(html),
            )
            mail.send(msg)
            return True
        except Exception as e:
            current_app.logger.error(f"Erreur d'envoi d'email ({template}): {e}")
            return False

    @staticmethod
    def send_welcome_email(user):
        """Email de bienvenue, avec le lien de vérification de l'adresse"""
        from app.services.auth_service import AuthService
        return EmailService.send_email(
            to=user.email,
            subject='Bienvenue sur AgriInvest Haïti !',
            template='welcome',
            user=user,
            token=AuthService.generate_email_token(user.email)
        )

    @staticmethod
    def send_verification_email(user):
        """Renvoie le lien de vérification de l'adresse email"""
        from app.services.auth_service import AuthService
        return EmailService.send_email(
            to=user.email,
            subject='Confirmez votre adresse email',
            template='verify_email',
            user=user,
            token=AuthService.generate_email_token(user.email)
        )

    @staticmethod
    def send_contact_message(name, email, subject, message):
        """Transmet un message du formulaire de contact à l'équipe. Retourne True si envoyé."""
        def one_line(value):  # pas de saut de ligne dans les en-têtes (injection d'en-têtes)
            return re.sub(r'[\r\n]+', ' ', value or '').strip()

        recipient = current_app.config.get('CONTACT_EMAIL') or current_app.config.get(
            'MAIL_DEFAULT_SENDER', 'noreply@agrinvest.ht')
        try:
            msg = Message(
                subject=f"[Contact] {one_line(subject) or 'Sans objet'}",
                recipients=[recipient],
                sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@agrinvest.ht'),
                reply_to=one_line(email),
                body=f"De : {one_line(name)} <{one_line(email)}>\n\n{message or ''}",
            )
            mail.send(msg)
            return True
        except Exception as e:
            current_app.logger.error(f"Erreur d'envoi du message de contact: {e}")
            return False

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
