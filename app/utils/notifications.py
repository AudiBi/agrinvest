# app/utils/notifications.py
"""
Système de notifications pour AgriInvest Haïti
"""

from app.models.user import utc_now
from flask import current_app
from app.extensions import db
from app.models import Notification
import json


def send_notification(user_id, title, message, notification_type='info', link=None, data=None):
    """
    Envoie une notification à un utilisateur
    
    Args:
        user_id: ID de l'utilisateur
        title: Titre de la notification
        message: Message de la notification
        notification_type: Type (info, success, warning, danger)
        link: Lien optionnel
        data: Données supplémentaires (dict)
    
    Returns:
        Notification créée
    """
    try:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link,
            data=json.dumps(data) if data else None
        )
        db.session.add(notification)
        db.session.commit()
        return notification
    except Exception as e:
        current_app.logger.error(f"Erreur création notification: {e}")
        return None


def notify_investor(investor, project, contribution):
    """Notifie un investisseur après une contribution"""
    return send_notification(
        user_id=investor.id,
        title=f"Contribution confirmée - {project.title}",
        message=f"Votre investissement de {contribution.amount_htg:,.0f} HTG a été confirmé avec succès.",
        notification_type='success',
        link=f'/projects/{project.id}'
    )


def notify_project_owner(project, contribution):
    """Notifie le propriétaire du projet d'une nouvelle contribution"""
    return send_notification(
        user_id=project.farmer_id,
        title=f"Nouvelle contribution - {project.title}",
        message=f"Un investisseur a contribué {contribution.amount_htg:,.0f} HTG à votre projet.",
        notification_type='info',
        link=f'/projects/{project.id}'
    )


def notify_project_funded(project):
    """Notifie le propriétaire que son projet est financé"""
    return send_notification(
        user_id=project.farmer_id,
        title=f"Projet financé - {project.title}",
        message=f"Félicitations ! Votre projet a atteint son objectif de financement.",
        notification_type='success',
        link=f'/projects/{project.id}'
    )


def notify_project_update(project, update):
    """Notifie tous les investisseurs d'une mise à jour du projet"""
    from app.models import Contribution
    from app.models.enums import ContributionStatus
    
    contributions = Contribution.query.filter_by(
        project_id=project.id,
        status=ContributionStatus.COMPLETED
    ).all()
    
    notifications = []
    for contribution in contributions:
        notif = send_notification(
            user_id=contribution.investor_id,
            title=f"Mise à jour - {project.title}",
            message=update.title[:100],
            notification_type='info',
            link=f'/projects/{project.id}/updates'
        )
        if notif:
            notifications.append(notif)
    
    return notifications


def mark_notification_as_read(notification_id, user_id):
    """Marque une notification comme lue"""
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=user_id
    ).first()
    
    if notification:
        notification.mark_as_read()
        return True
    return False


def get_unread_count(user_id):
    """Retourne le nombre de notifications non lues"""
    return Notification.query.filter_by(
        user_id=user_id,
        is_read=False
    ).count()


def get_user_notifications(user_id, limit=50, offset=0):
    """Récupère les notifications d'un utilisateur"""
    return Notification.query.filter_by(
        user_id=user_id
    ).order_by(
        Notification.created_at.desc()
    ).offset(offset).limit(limit).all()


def delete_old_notifications(days=30):
    """Supprime les notifications anciennes"""
    from datetime import datetime, timedelta
    
    cutoff_date = utc_now() - timedelta(days=days)
    deleted = Notification.query.filter(
        Notification.created_at < cutoff_date,
        Notification.is_read == True
    ).delete()
    
    db.session.commit()
    return deleted


SEVERITY_ORDER = {'info': 0, 'warning': 1, 'critical': 2}


def send_weather_alert_notifications(alert):
    """Notifie les agriculteurs abonnés à la zone de l'alerte (notification dans l'application).

    Respecte la gravité minimale choisie par chaque abonné. Retourne le nombre de personnes notifiées.
    """
    from app.models import WeatherSubscription

    subscriptions = WeatherSubscription.query.filter_by(zone=alert.zone, is_active=True).all()
    level = SEVERITY_ORDER.get(alert.severity, 0)
    notified = 0
    for subscription in subscriptions:
        if SEVERITY_ORDER.get(subscription.min_severity, 1) > level:
            continue
        language = subscription.language or 'ht'
        message = getattr(alert, f'message_{language}', None) or alert.message_ht
        if send_notification(
            user_id=subscription.farmer_id,
            title=f'Alerte météo - {alert.zone}',
            message=message,
            notification_type='danger' if alert.severity == 'critical' else 'warning',
            data={'alert_id': alert.id, 'severity': alert.severity},
        ):
            subscription.last_notified_at = utc_now()
            notified += 1
    alert.sent_at = utc_now()
    db.session.commit()
    return notified
