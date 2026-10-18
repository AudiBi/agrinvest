# Mise en production — liste de contrôle

À dérouler dans l'ordre. Chaque case cochée est une vérification que **vous** avez faite sur l'environnement
cible : les tests automatisés couvrent le code, pas votre configuration.

## 1. Configuration (variables d'environnement)

L'application **refuse de démarrer** sans `SECRET_KEY` ni `DATABASE_URL` en production. `FLASK_ENV` vaut
`production` par défaut : définissez-le explicitement.

- [ ] `FLASK_ENV=production`, `SECRET_KEY` (aléatoire, 32 octets minimum), `DATABASE_URL` (PostgreSQL), `BASE_URL`
- [ ] `SESSION_COOKIE_SECURE=true` et l'application servie **uniquement en HTTPS**
- [ ] `REDIS_URL` — limitation de débit partagée entre les processus (sans elle, les limites sont par processus)
- [ ] `CORS_ORIGINS` limité à vos domaines
- [ ] Clés des passerelles : `STRIPE_*`, `PAYPAL_*` (+ `PAYPAL_WEBHOOK_ID`), `MONCASH_*` (+ `MONCASH_WEBHOOK_SECRET`)
- [ ] `MAIL_*` : sans SMTP valide, **aucun email ne part** (réinitialisation de mot de passe comprise)
- [ ] `EXCHANGE_RATE_API_KEY` si votre fournisseur de taux l'exige (sans taux, les paiements en devise sont refusés)
- [ ] Suivi d'erreurs : `pip install 'sentry-sdk[flask]'` (**non inclus dans `requirements.txt`**) puis `SENTRY_DSN` ;
      sans la bibliothèque, un avertissement est journalisé au démarrage et aucune erreur n'est remontée
- [ ] Aucune clé dans le dépôt ni dans les journaux (le fichier `.env` n'est jamais versionné)

## 2. Base de données

- [ ] PostgreSQL 16, sauvegardes automatiques **et un test de restauration réussi**
- [ ] `flask db upgrade` sur la base vide — **jamais** `init-db` ni `init_db.py` (ils sont refusés hors développement)
- [ ] `flask db check` ne signale aucun écart
- [ ] La session PostgreSQL est forcée en UTC par l'application (rien à régler), mais vérifiez le fuseau du serveur

## 3. Premier démarrage

- [ ] `flask create-admin` : crée le premier administrateur (mot de passe fort exigé, jamais affiché)
- [ ] Se connecter, puis changer le mot de passe si l'administrateur a été créé par un tiers
- [ ] Créer les **points de collecte** (`POST /api/v1/collection-points`) et les rattacher aux projets
- [ ] Créer les comptes **agents** puis les **rattacher à leurs points**
      (`POST /api/v1/collection-points/<id>/agents`) : sans rattachement, un agent ne peut encaisser nulle part
- [ ] Définir la configuration de commission par défaut (`POST /api/v1/commission/config`, taux entre 0 et 20 %) ;
      à défaut, 3 % s'applique
- [ ] Décider de la **modération des projets** : `REQUIRE_PROJECT_APPROVAL=true` place chaque projet soumis en
      attente de validation par un administrateur. Désactivé, les agriculteurs publient directement.

## 4. Tâches planifiées

- [ ] `flask reconcile-payments` **toutes les 15 minutes** (cron, tâche planifiée ou service dédié).
      Elle confirme les paiements dont le webhook s'est perdu et expire les paiements abandonnés après
      24 h (`PENDING_PAYMENT_TTL_HOURS`). Les paiements en espèces ne sont pas concernés.

## 5. Webhooks à déclarer chez les passerelles

| Passerelle | URL | Détail |
|---|---|---|
| Stripe | `/api/v1/payments/webhook/stripe` | `payment_intent.succeeded`, `payment_intent.payment_failed`, `charge.refunded` ; secret dans `STRIPE_WEBHOOK_SECRET` |
| PayPal | `/api/v1/payments/webhook/paypal` | `CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.REFUNDED` ; identifiant dans `PAYPAL_WEBHOOK_ID` |
| MonCash | `/api/v1/webhooks/moncash` | en-tête `X-MonCash-Signature` (HMAC-SHA256 du corps) — **format à confirmer avec MonCash** |

- [ ] Les trois sont déclarés en HTTPS et répondent 401 à une requête non signée (`curl -X POST <url> -d '{}'`)

## 6. Essais avant d'ouvrir

- [ ] Parcours complet en sandbox : voir [`SANDBOX_TESTING.md`](SANDBOX_TESTING.md) (Stripe, PayPal, MonCash)
- [ ] **Format réel du webhook MonCash** capturé et comparé au code (`app/api/webhook_routes.py`)
- [ ] Un paiement réel de faible montant par passerelle, puis son remboursement
- [ ] Un encaissement d'espèces de bout en bout (contribution → agent → reçu → projet crédité)
- [ ] `GET /health` répond 200 (et 503 si la base est coupée)
- [ ] Une alerte (Sentry) est bien reçue sur une erreur provoquée

## 7. Exploitation

- [ ] Journal d'audit consulté régulièrement : `GET /api/v1/admin/audit-logs` (administrateur)
- [ ] Surveillance des contributions restées `pending`, des remboursements et des versements au CEO
- [ ] Rotation prévue des secrets (clés des passerelles, `SECRET_KEY` — la changer déconnecte tous les utilisateurs)
- [ ] Politique de conservation des journaux d'audit et des journaux applicatifs

## 8. Limites connues (non traitées dans le code)

À connaître et à arbitrer — elles sont décrites en détail dans les PR correspondantes :

- **Matching fund** de la diaspora : enregistré mais jamais appliqué aux paiements (règle métier à définir).
- **Plafonds d'encaissement** par agent (montant par jour ou par opération) : non implémentés.
- **Journal d'audit** : ni signé ni chaîné ; un accès direct à la base permet de le modifier.
  Pour une exigence légale, prévoir un stockage en ajout seul ou un export externe.
- **Paramètres du site** (`/admin/settings`) : écrits dans un `config.json` du dossier du code — ils ne
  survivent pas à un conteneur et ne se partagent pas entre instances.
- **Email de confirmation de contribution** : non envoyé (il faut un envoi asynchrone pour ne pas bloquer
  les webhooks des passerelles).
- **Utilisateurs non vérifiés** : peuvent investir (décision produit).
- **Alertes météo** : notification dans l'application seulement, pas d'envoi SMS ou WhatsApp.
- **Certificats de formation** non générés ; la progression est déclarative.
- **Conformité** (vérification d'identité, lutte contre le blanchiment, conditions d'utilisation,
  protection des données) : hors du code, à faire valider par un juriste avant d'accepter de l'argent.
- **Aucun test avec de vrais appels aux passerelles** : seules des simulations sont automatisées.
