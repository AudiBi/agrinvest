# app/services/payment_service.py
"""
Service de paiement pour AgriInvest Haïti
Gère Stripe, PayPal, MonCash et autres méthodes de paiement
"""

from flask import current_app, url_for
from decimal import Decimal
import stripe


class PaymentService:
    """Service de gestion des paiements"""

    @staticmethod
    def process_stripe_payment(contribution):
        """Traite un paiement Stripe"""
        try:
            stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
            
            intent = stripe.PaymentIntent.create(
                amount=int(contribution.amount * 100),  # Stripe utilise les centimes
                currency=contribution.currency.lower(),
                metadata={
                    'contribution_id': contribution.id,
                    'project_id': contribution.project_id,
                    'investor_id': contribution.investor_id
                },
                receipt_email=contribution.investor.email
            )
            
            return {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': intent.amount,
                'currency': intent.currency
            }
        except Exception as e:
            current_app.logger.error(f"Erreur Stripe: {e}")
            return None

    @staticmethod
    def process_paypal_payment(contribution):
        """Traite un paiement PayPal"""
        # À implémenter avec l'API PayPal
        current_app.logger.info(f"Paiement PayPal pour contribution {contribution.id}")
        return {
            'payment_id': f'PAYPAL_{contribution.id}',
            'status': 'created',
            'approval_url': '#'
        }

    @staticmethod
    def process_moncash_payment(contribution):
        """Traite un paiement MonCash (Haïti)"""
        # À implémenter avec l'API MonCash
        current_app.logger.info(f"Paiement MonCash pour contribution {contribution.id}")
        return {
            'payment_id': f'MONCASH_{contribution.id}',
            'status': 'pending',
            'payment_url': '#'
        }

    @staticmethod
    def verify_payment(contribution, payment_intent_id):
        """Vérifie le statut d'un paiement"""
        try:
            stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if intent.status == 'succeeded':
                return True
            return False
        except Exception as e:
            current_app.logger.error(f"Erreur vérification paiement: {e}")
            return False

    @staticmethod
    def process_refund(contribution):
        """Traite un remboursement"""
        try:
            stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
            
            if contribution.stripe_payment_intent_id:
                refund = stripe.Refund.create(
                    payment_intent=contribution.stripe_payment_intent_id
                )
                return refund.status == 'succeeded'
            return False
        except Exception as e:
            current_app.logger.error(f"Erreur remboursement: {e}")
            return False