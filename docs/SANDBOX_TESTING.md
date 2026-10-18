# Guide de test en sandbox (Stripe, PayPal, MonCash)

À dérouler **avant** d'accepter de l'argent réel. Les tests automatisés (`pytest tests`) simulent les
passerelles : ce guide vérifie l'intégration réelle. Cochez chaque cas ; en cas d'écart, notez la charge
utile reçue (surtout pour MonCash, dont le format n'est pas confirmé).

## 0. Préparation

1. Copier `.env.example` en `.env` et renseigner **uniquement des clés de test** :
   `STRIPE_*` (clés `pk_test_` / `sk_test_`), `PAYPAL_MODE=sandbox`, `MONCASH_ENVIRONMENT=sandbox`.
2. En local : `FLASK_ENV=development`, puis `flask db upgrade` et `flask run`.
   Créer deux comptes via l'inscription (un investisseur, un agriculteur) et un projet publié.
3. Les webhooks doivent atteindre votre machine :
   - **Stripe** : `stripe listen --forward-to localhost:5000/api/v1/payments/webhook/stripe`
     (la CLI affiche le `whsec_...` à mettre dans `STRIPE_WEBHOOK_SECRET`).
   - **PayPal et MonCash** : exposer le port avec un tunnel HTTPS (ngrok, cloudflared) et déclarer les URL ci-dessous.
4. Planifier ou lancer à la main la réconciliation : `flask reconcile-payments`.

| Passerelle | URL de webhook | Événements / en-tête |
|---|---|---|
| Stripe | `/api/v1/payments/webhook/stripe` | `payment_intent.succeeded`, `payment_intent.payment_failed`, `charge.refunded` |
| PayPal | `/api/v1/payments/webhook/paypal` | `CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.REFUNDED` ; renseigner `PAYPAL_WEBHOOK_ID` |
| MonCash | `/api/v1/webhooks/moncash` | en-tête `X-MonCash-Signature` = HMAC-SHA256 hex du corps brut avec `MONCASH_WEBHOOK_SECRET` (**format supposé, à confirmer**) |

**Devises** : Stripe et PayPal n'acceptent pas le HTG. Depuis le formulaire web, le montant saisi en HTG est converti
en USD au taux du jour (`EXCHANGE_RATE_API_URL`) ; l'API refuse `HTG` pour ces deux moyens. MonCash débite en HTG.

## 1. Stripe (carte)

Cartes de test publiées par Stripe : `4242 4242 4242 4242` (succès), `4000 0000 0000 9995` (refus, fonds insuffisants),
`4000 0025 0000 3155` (authentification 3D Secure). Date future quelconque, CVC quelconque.

- [ ] **Succès** : investir 1 300 HTG par carte → page `/payment/card/<id>` s'affiche → payer avec `4242…`.
      Attendu : retour sur le tableau de bord, puis contribution `completed` (webhook), projet crédité, commission 3 % enregistrée.
- [ ] **Refus** : carte `4000 0000 0000 9995` → message d'erreur sur la page ; contribution `pending` puis `failed` (webhook `payment_failed`).
- [ ] **3D Secure** : carte `4000 0025 0000 3155` → écran d'authentification, puis succès.
- [ ] **Webhook rejoué** : depuis le tableau de bord Stripe, renvoyer l'événement ; aucun effet supplémentaire (montant du projet inchangé).
- [ ] **Signature invalide** : `curl -X POST .../webhook/stripe -d '{}'` → 400.
- [ ] **Remboursement total** depuis le tableau de bord Stripe → contribution `refunded`, montant du projet décrémenté une seule fois.
- [ ] **Remboursement partiel** → ignoré avec un avertissement dans les logs (traitement manuel).
- [ ] **Webhook perdu** : arrêter `stripe listen`, payer, attendre 15 min, lancer `flask reconcile-payments` → contribution confirmée.

## 2. PayPal (sandbox)

Créer un compte *acheteur* sandbox dans https://developer.paypal.com (Sandbox → Accounts).

- [ ] **Succès** : investir par PayPal → redirection vers PayPal → se connecter avec le compte acheteur → approuver.
      Attendu : retour sur `/payment/success?token=...`, **capture automatique** (sans elle aucun fonds n'est prélevé),
      contribution `completed`.
- [ ] **Annulation** côté PayPal → retour `/payment/cancel`, contribution reste `pending` puis `failed` après 24 h (réconciliation).
- [ ] **Webhook signé** : un faux POST sur `/webhook/paypal` sans en-têtes PayPal → 401. Un webhook réel (`PAYMENT.CAPTURE.COMPLETED`) → 200.
- [ ] **Montant altéré** : vérifier dans les logs qu'une capture dont le montant ne correspond pas n'est pas confirmée.
- [ ] **Remboursement** via l'API `POST /api/v1/contributions/<id>/refund` (compte propriétaire du projet ou admin) → remboursement visible côté PayPal.

## 3. MonCash (sandbox)

- [ ] **Paiement** : investir via MonCash → redirection vers la page MonCash → payer avec un compte de test.
- [ ] **Capturer la charge utile réelle du webhook** (logs ou outil de tunnel) et la comparer à ce que lit le code
      (`payment_id` / `paymentId`, `transaction_id` / `transactionId`, `status`, `amount`) : adapter
      `app/api/webhook_routes.py::moncash_webhook` et `app/utils/payments.py::verify_payment` si besoin.
- [ ] **Signature** : confirmer auprès de MonCash le mécanisme réel (en-tête et algorithme). Tant que ce n'est pas fait,
      toute requête non signée est refusée (401) : c'est voulu.
- [ ] **Statut de `retrieve`** : vérifier la valeur renvoyée pour un paiement terminé (le code attend `completed`).
- [ ] **Remboursement** et cas d'échec/abandon.

## 4. Contrôles transverses

- [ ] `GET /health` renvoie 200 ; couper la base → 503.
- [ ] Après chaque scénario : `flask reconcile-payments` ne change rien aux contributions déjà finalisées.
- [ ] Les logs ne contiennent ni clé secrète ni numéro de carte.
- [ ] Passer en production : remplacer toutes les clés par les clés *live*, `PAYPAL_MODE=live`,
      `MONCASH_ENVIRONMENT=production`, `SESSION_COOKIE_SECURE=true`, et refaire **un** paiement réel de faible montant.
