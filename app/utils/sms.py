# app/utils/sms.py
"""
Envoi de SMS pour AgriInvest Haïti
"""

from flask import current_app
import requests
import random


def send_sms_notification(phone_number, message):
    """
    Envoie un SMS via Twilio ou Digicel
    
    Args:
        phone_number: Numéro de téléphone
        message: Message à envoyer
    
    Returns:
        bool: Succès ou échec
    """
    # Utiliser Twilio
    twilio_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
    twilio_token = current_app.config.get('TWILIO_AUTH_TOKEN')
    twilio_phone = current_app.config.get('TWILIO_PHONE_NUMBER')
    
    if twilio_sid and twilio_token:
        return _send_sms_twilio(phone_number, message, twilio_sid, twilio_token, twilio_phone)
    
    # Fallback: Digicel Haïti
    digicel_api_key = current_app.config.get('DIGICEL_SMS_API_KEY')
    if digicel_api_key:
        return _send_sms_digicel(phone_number, message, digicel_api_key)
    
    current_app.logger.warning("No SMS provider configured")
    return False


def _send_sms_twilio(phone_number, message, sid, token, from_phone):
    """Envoie un SMS via Twilio"""
    try:
        from twilio.rest import Client
        client = Client(sid, token)
        client.messages.create(
            body=message,
            from_=from_phone,
            to=phone_number
        )
        return True
    except Exception as e:
        current_app.logger.error(f"Twilio SMS error: {e}")
        return False


def _send_sms_digicel(phone_number, message, api_key):
    """Envoie un SMS via Digicel Haïti"""
    url = "https://api.digicelgroup.com/sms/v1/messages"
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'to': phone_number,
        'message': message
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        current_app.logger.error(f"Digicel SMS error: {e}")
        return False


def send_sms_verification_code(phone_number):
    """
    Envoie un code de vérification par SMS
    
    Args:
        phone_number: Numéro de téléphone
    
    Returns:
        str: Code de vérification
    """
    code = ''.join(str(random.randint(0, 9)) for _ in range(6))
    message = f"Votre code de vérification AgriInvest est : {code}"
    
    if send_sms_notification(phone_number, message):
        return code
    return None