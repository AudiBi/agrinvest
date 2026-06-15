# init_db.py
"""
Script d'initialisation de la base de données avec données initiales
Exécuter: python init_db.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import random

# Ajouter le répertoire parent au chemin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import (
    User, Project, Contribution, HarvestUpdate, Training, TrainingProgress,
    WeatherAlert, WeatherSubscription, GroupContribution, CollectionPoint,
    PlatformCommissionConfig, Notification
)
from app.models.enums import (
    UserRole, ProjectStatus, ContributionStatus, NotificationType
)


def utc_now():
    """Retourne la date UTC actuelle"""
    return datetime.now(timezone.utc)


def init_db():
    """Initialise la base de données avec des données de test"""
    
    app = create_app('development')
    
    with app.app_context():
        print("🗄️  Initialisation de la base de données...")
        
        # Supprimer toutes les données existantes
        print("📦 Suppression des données existantes...")
        db.drop_all()
        db.create_all()
        
        print("🌱 Création des données initiales...")
        
        # ====================================================================
        # CRÉATION DES UTILISATEURS
        # ====================================================================
        
        # Admin
        admin = User(
            name="Administrateur",
            email="admin@agrinvest.ht",
            role=UserRole.ADMIN,
            is_admin=True,
            is_verified=True,
            is_active=True,
            preferred_currency="HTG",
            preferred_language="fr"
        )
        admin.set_password("Admin123!")
        db.session.add(admin)
        
        # Agriculteurs
        farmers = [
            User(
                name="Jean Baptiste",
                email="jean.baptiste@agrinvest.ht",
                role=UserRole.FARMER,
                phone="+509 1234-5678",
                location="Hinche",
                department="Centre",
                commune="Hinche",
                bio="Agriculteur depuis 15 ans, spécialisé dans la culture du manioc et des patates douces.",
                is_verified=True,
                is_active=True,
                preferred_currency="HTG",
                preferred_language="ht"
            ),
            User(
                name="Marie Joseph",
                email="marie.joseph@agrinvest.ht",
                role=UserRole.FARMER,
                phone="+509 2345-6789",
                location="Cap-Haïtien",
                department="Nord",
                commune="Cap-Haïtien",
                bio="Productrice de cacao et de café, engagée dans l'agriculture biologique.",
                is_verified=True,
                is_active=True,
                preferred_currency="HTG",
                preferred_language="fr"
            ),
            User(
                name="Pierre Antoine",
                email="pierre.antoine@agrinvest.ht",
                role=UserRole.FARMER,
                phone="+509 3456-7890",
                location="Les Cayes",
                department="Sud",
                commune="Les Cayes",
                bio="Spécialiste de la culture de la canne à sucre et des fruits tropicaux.",
                is_verified=True,
                is_active=True,
                preferred_currency="HTG",
                preferred_language="ht"
            ),
            User(
                name="Claudette Pierre",
                email="claudette.pierre@agrinvest.ht",
                role=UserRole.FARMER,
                phone="+509 4567-8901",
                location="Jacmel",
                department="Sud-Est",
                commune="Jacmel",
                bio="Productrice de mangues et d'avocats pour l'exportation.",
                is_verified=True,
                is_active=True,
                preferred_currency="USD",
                preferred_language="fr"
            ),
            User(
                name="Joseph Michel",
                email="joseph.michel@agrinvest.ht",
                role=UserRole.FARMER,
                phone="+509 5678-9012",
                location="Jérémie",
                department="Grand'Anse",
                commune="Jérémie",
                bio="Cultivateur de riz et de maïs dans la plaine des Cayes.",
                is_verified=False,
                is_active=True,
                preferred_currency="HTG",
                preferred_language="ht"
            )
        ]
        
        for farmer in farmers:
            farmer.set_password("Farmer123!")
            db.session.add(farmer)
        
        # Investisseurs
        investors = [
            User(
                name="Paul Bernard",
                email="paul.bernard@email.com",
                role=UserRole.INVESTOR,
                country="US",
                city="Miami",
                diaspora_community="us_haitian",
                hometown_in_haiti="Port-au-Prince",
                is_verified=True,
                is_active=True,
                preferred_currency="USD",
                preferred_language="fr"
            ),
            User(
                name="Sophie Dupont",
                email="sophie.dupont@email.com",
                role=UserRole.INVESTOR,
                country="FR",
                city="Paris",
                diaspora_community="fr_haitian",
                hometown_in_haiti="Cap-Haïtien",
                is_verified=True,
                is_active=True,
                preferred_currency="EUR",
                preferred_language="fr"
            ),
            User(
                name="Marc Laurent",
                email="marc.laurent@email.com",
                role=UserRole.INVESTOR,
                country="CA",
                city="Montréal",
                diaspora_community="ca_haitian",
                hometown_in_haiti="Les Cayes",
                is_verified=True,
                is_active=True,
                preferred_currency="CAD",
                preferred_language="fr"
            ),
            User(
                name="Isabelle Paul",
                email="isabelle.paul@email.com",
                role=UserRole.INVESTOR,
                country="HT",
                city="Port-au-Prince",
                is_verified=True,
                is_active=True,
                preferred_currency="HTG",
                preferred_language="ht"
            ),
            User(
                name="Jean-François Louis",
                email="jf.louis@email.com",
                role=UserRole.INVESTOR,
                country="US",
                city="New York",
                diaspora_community="us_haitian",
                hometown_in_haiti="Jérémie",
                is_verified=False,
                is_active=True,
                preferred_currency="USD",
                preferred_language="en"
            )
        ]
        
        for investor in investors:
            investor.set_password("Invest123!")
            db.session.add(investor)
        
        db.session.commit()
        
        # ====================================================================
        # CRÉATION DES PROJETS
        # ====================================================================
        
        farmers_list = User.query.filter_by(role=UserRole.FARMER).all()
        
        projects = [
            Project(
                title="Extension plantation de manioc - Hinche",
                title_ht="Elajisman plantasyon manyòk - Ench",
                description="Extension de la plantation de manioc sur 5 hectares. Achat de boutures, engrais et système d'irrigation goutte-à-goutte.",
                description_ht="Elajisman plantasyon manyòk sou 5 ekta. Acha bouti, angrè ak sistèm irigasyon.",
                short_description="Financement pour étendre la production de manioc à Hinche",
                location="Hinche",
                department="Centre",
                commune="Hinche",
                category="Tubercules",
                amount_needed=Decimal("250000"),
                min_investment=Decimal("1000"),
                max_investment=Decimal("50000"),
                deadline=utc_now() + timedelta(days=45),
                farmer_id=farmers_list[0].id,
                currency="HTG",
                is_published=True,
                is_verified=True,
                status=ProjectStatus.PUBLISHED
            ),
            Project(
                title="Modernisation caféière - Cap-Haïtien",
                title_ht="Modènizasyon kafe - Kap Ayisyen",
                description="Modernisation de la caféière avec équipement de torréfaction et emballage sous vide pour exportation.",
                short_description="Modernisation d'une caféière pour l'exportation",
                location="Cap-Haïtien",
                department="Nord",
                commune="Cap-Haïtien",
                category="Café/Cacao",
                amount_needed=Decimal("500000"),
                min_investment=Decimal("5000"),
                max_investment=Decimal("100000"),
                deadline=utc_now() + timedelta(days=60),
                farmer_id=farmers_list[1].id,
                currency="HTG",
                is_published=True,
                is_verified=True,
                status=ProjectStatus.PUBLISHED,
                is_featured=True,
                estimated_jobs=8,
                estimated_farmers_helped=15,
                co2_reduction_kg=Decimal("5000")
            ),
            Project(
                title="Serre maraîchère - Les Cayes",
                title_ht="Sèr mawajè - Okay",
                description="Construction d'une serre de 1000m² pour la production de tomates et poivrons hors saison.",
                short_description="Serre maraîchère pour production hors saison",
                location="Les Cayes",
                department="Sud",
                commune="Les Cayes",
                category="Légumes",
                amount_needed=Decimal("350000"),
                min_investment=Decimal("2000"),
                max_investment=Decimal("75000"),
                deadline=utc_now() + timedelta(days=30),
                farmer_id=farmers_list[2].id,
                currency="HTG",
                is_published=True,
                is_verified=True,
                status=ProjectStatus.PUBLISHED,
                estimated_jobs=4,
                estimated_farmers_helped=6,
                co2_reduction_kg=Decimal("2000")
            ),
            Project(
                title="Verger de manguiers - Jacmel",
                title_ht="Jaden mango - Jakmèl",
                description="Plantation de 500 manguiers variété Francisque. Irrigation et système de protection.",
                short_description="Plantation de manguiers pour exportation",
                location="Jacmel",
                department="Sud-Est",
                commune="Jacmel",
                category="Fruits",
                amount_needed=Decimal("180000"),
                min_investment=Decimal("1000"),
                max_investment=Decimal("30000"),
                deadline=utc_now() + timedelta(days=20),
                farmer_id=farmers_list[3].id,
                currency="HTG",
                is_published=True,
                is_verified=True,
                status=ProjectStatus.PUBLISHED
            ),
            Project(
                title="Riziculture moderne - Jérémie",
                title_ht="Modènizasyon diri - Jeremi",
                description="Modernisation de la riziculture avec système d'irrigation par pompage solaire.",
                short_description="Riziculture moderne avec énergie solaire",
                location="Jérémie",
                department="Grand'Anse",
                commune="Jérémie",
                category="Céréales",
                amount_needed=Decimal("300000"),
                min_investment=Decimal("1000"),
                max_investment=Decimal("50000"),
                deadline=utc_now() + timedelta(days=55),
                farmer_id=farmers_list[4].id,
                currency="HTG",
                is_published=False,
                is_verified=False,
                status=ProjectStatus.DRAFT
            ),
            Project(
                title="Élevage caprin - Artibonite",
                title_ht="Elevaj kabrit - Latibonit",
                description="Création d'un élevage de 50 chèvres pour la production de lait et de viande.",
                short_description="Élevage caprin dans la vallée de l'Artibonite",
                location="Gonaïves",
                department="Artibonite",
                commune="Gonaïves",
                category="Élevage",
                amount_needed=Decimal("200000"),
                min_investment=Decimal("1000"),
                max_investment=Decimal("40000"),
                deadline=utc_now() + timedelta(days=40),
                farmer_id=farmers_list[0].id,
                currency="HTG",
                is_published=True,
                is_verified=True,
                status=ProjectStatus.PUBLISHED,
                is_featured=True,
                estimated_jobs=3,
                estimated_farmers_helped=5,
                co2_reduction_kg=Decimal("1000")
            )
        ]
        
        for project in projects:
            db.session.add(project)
        
        db.session.commit()
        
        # ====================================================================
        # CRÉATION DES CONTRIBUTIONS (CORRIGÉE)
        # ====================================================================
        
        investors_list = User.query.filter_by(role=UserRole.INVESTOR).all()
        projects_list = Project.query.filter_by(is_published=True).all()
        
        contribution_amounts = [1000, 5000, 10000, 25000, 50000, 1000, 5000, 20000]
        
        for project in projects_list:
            # 3-5 contributions par projet
            num_contributions = random.randint(3, 5)
            for j in range(num_contributions):
                investor = random.choice(investors_list)
                amount = Decimal(random.choice(contribution_amounts))
                amount_htg = amount * Decimal("120")  # Taux de change simplifié
                exchange_rate = Decimal("120")
                
                # Créer la contribution avec TOUS les champs initialisés
                contribution = Contribution(
                    investor_id=investor.id,
                    project_id=project.id,
                    amount=amount,
                    currency=investor.preferred_currency,
                    amount_htg=amount_htg,
                    exchange_rate=exchange_rate,
                    exchange_rate_date=utc_now(),
                    gateway_fee=Decimal("0"),
                    gateway_fee_currency=investor.preferred_currency,
                    conversion_fee=Decimal("0"),
                    platform_fee=Decimal("0"),
                    net_amount_htg=amount_htg,
                    platform_commission_applied=None,
                    platform_commission_amount=Decimal("0"),
                    payment_method=random.choice(["stripe", "paypal", "moncash"]),
                    status=ContributionStatus.COMPLETED,
                    is_anonymous=random.choice([True, False]),
                    investor_country=investor.country or "HT",
                    created_at=utc_now() - timedelta(days=random.randint(1, 30))
                )
                db.session.add(contribution)
                
                # Mettre à jour le montant collecté du projet
                project.amount_raised += amount
        
        db.session.commit()
        
        # ====================================================================
        # CRÉATION DES MISES À JOUR
        # ====================================================================
        
        for project in projects_list[:3]:
            updates = [
                HarvestUpdate(
                    project_id=project.id,
                    title="Préparation du terrain terminée",
                    title_ht="Prepare tè a fini",
                    content="Les travaux de préparation du terrain sont terminés. Nous commençons la plantation la semaine prochaine.",
                    content_ht="Travay prepare tè a fini. Nou kòmanse plante semèn pwochèn.",
                    update_type="general",
                    is_important=False,
                    is_published=True
                ),
                HarvestUpdate(
                    project_id=project.id,
                    title="Premières plantations",
                    title_ht="Premye plantasyon",
                    content="Les premières plantations ont été réalisées avec succès. Suivez notre progression.",
                    content_ht="Premye plantasyon yo te reyisi. Swiv pwogrè nou an.",
                    update_type="harvest",
                    is_important=False,
                    is_published=True
                )
            ]
            for update in updates:
                db.session.add(update)
        
        db.session.commit()
        
        # ====================================================================
        # CRÉATION DES FORMATIONS
        # ====================================================================
        
        trainings = [
            Training(
                title_ht="Teknik Irigasyon pou Agrikiltè",
                title_fr="Techniques d'irrigation pour agriculteurs",
                title_en="Irrigation Techniques for Farmers",
                description_ht="Aprann teknik irigasyon modèn pou amelyore pwodiksyon ou.",
                description_fr="Apprenez les techniques d'irrigation modernes pour améliorer votre production.",
                description_en="Learn modern irrigation techniques to improve your production.",
                content_type="video_low",
                content_url="https://example.com/irrigation.mp4",
                thumbnail_url="/static/img/trainings/irrigation.jpg",
                duration_minutes=45,
                file_size_mb=50,
                category="Irrigation",
                difficulty_level="beginner",
                region_specific="national",
                is_published=True,
                is_featured=True,
                sort_order=1
            ),
            Training(
                title_ht="Jesyon Solo pou Agrikilti Dirab",
                title_fr="Gestion des sols pour une agriculture durable",
                title_en="Soil Management for Sustainable Agriculture",
                description_ht="Teknik pou prezève ak amelyore kalite tè ou.",
                description_fr="Techniques pour préserver et améliorer la qualité de vos sols.",
                description_en="Techniques to preserve and improve your soil quality.",
                content_type="video_low",
                content_url="https://example.com/soil.mp4",
                thumbnail_url="/static/img/trainings/soil.jpg",
                duration_minutes=60,
                file_size_mb=75,
                category="Gestion des sols",
                difficulty_level="intermediate",
                region_specific="national",
                is_published=True,
                is_featured=True,
                sort_order=2
            ),
            Training(
                title_ht="Lutte Kont Vèmin nan Agrikilti",
                title_fr="Lutte contre les ravageurs en agriculture",
                title_en="Pest Control in Agriculture",
                description_ht="Metòd natirèl ak chimik pou pwoteje rekòt ou kont vèmin.",
                description_fr="Méthodes naturelles et chimiques pour protéger vos cultures contre les ravageurs.",
                description_en="Natural and chemical methods to protect your crops from pests.",
                content_type="video_low",
                content_url="https://example.com/pest.mp4",
                thumbnail_url="/static/img/trainings/pest.jpg",
                duration_minutes=50,
                file_size_mb=60,
                category="Protection des cultures",
                difficulty_level="beginner",
                region_specific="national",
                is_published=True,
                is_featured=False,
                sort_order=3
            )
        ]
        
        for training in trainings:
            db.session.add(training)
        
        db.session.commit()
        
        # ====================================================================
        # CRÉATION DES ALERTES MÉTÉO
        # ====================================================================
        
        weather_alerts = [
            WeatherAlert(
                zone="Nord-Ouest",
                department="Nord-Ouest",
                alert_type="forte_pluie",
                severity="warning",
                message_ht="Gwo lapli pwograme pou semèn kap vini an. Pran prekosyon.",
                message_fr="Fortes pluies prévues pour la semaine à venir. Soyez prudents.",
                agricultural_advice_ht="Evite plante pandan peryòd sa a. Verifye sistèm drenaj ou yo.",
                agricultural_advice_fr="Évitez de planter pendant cette période. Vérifiez vos systèmes de drainage.",
                starts_at=utc_now() + timedelta(days=2),
                ends_at=utc_now() + timedelta(days=5),
                source="Météo Haïti",
                is_active=True
            ),
            WeatherAlert(
                zone="Artibonite",
                department="Artibonite",
                alert_type="secheresse",
                severity="info",
                message_ht="Peryòd sechrès ap pwolonje. Planifye irigasyon ou.",
                message_fr="La période de sécheresse se prolonge. Planifiez votre irrigation.",
                agricultural_advice_ht="Ogmente irigasyon si posib. Sere dlo.",
                agricultural_advice_fr="Augmentez l'irrigation si possible. Stockez l'eau.",
                starts_at=utc_now() + timedelta(days=5),
                ends_at=utc_now() + timedelta(days=20),
                source="CNIGS",
                is_active=True
            )
        ]
        
        for alert in weather_alerts:
            db.session.add(alert)
        
        db.session.commit()
        
        # ====================================================================
        # CRÉATION DE LA CONFIGURATION DES COMMISSIONS
        # ====================================================================
        
        commission_config = PlatformCommissionConfig(
            commission_type="platform_fee",
            percentage=Decimal("3.0"),
            applies_on="amount_raised",
            min_amount_to_apply=Decimal("0"),
            is_active=True,
            is_default=True,
            description_fr="Commission standard de 3% sur les projets financés",
            description_ht="Kòmisyon estanda 3% sou pwojè finanse yo",
            valid_from=utc_now()
        )
        db.session.add(commission_config)
        
        # ====================================================================
        # CRÉATION DES NOTIFICATIONS
        # ====================================================================
        
        for investor in investors_list[:3]:
            notification = Notification(
                user_id=investor.id,
                title="Bienvenue sur AgriInvest Haïti !",
                message="Merci d'avoir rejoint notre plateforme. Commencez à explorer les projets agricoles.",
                notification_type=NotificationType.SUCCESS,
                link="/projects"
            )
            db.session.add(notification)
        
        db.session.commit()
        
        # ====================================================================
        # CRÉATION DES POINTS DE COLLECTE
        # ====================================================================
        
        collection_points = [
            CollectionPoint(
                name="Agence Digicel - Port-au-Prince",
                department="Ouest",
                commune="Port-au-Prince",
                address="123, Rue Capois, Port-au-Prince",
                manager_name="Jean Claude",
                manager_phone="+509 1234-5678",
                opening_hours="Lundi-Vendredi 8h-17h, Samedi 8h-12h",
                is_active=True,
                fee_percentage=Decimal("1.0")
            ),
            CollectionPoint(
                name="Super Marché Tropic",
                department="Nord",
                commune="Cap-Haïtien",
                address="Boulevard Carenage, Cap-Haïtien",
                manager_name="Marie-Ange",
                manager_phone="+509 2345-6789",
                opening_hours="Lundi-Samedi 7h-20h, Dimanche 8h-13h",
                is_active=True,
                fee_percentage=Decimal("1.5")
            )
        ]
        
        for point in collection_points:
            db.session.add(point)
        
        db.session.commit()
        
        # ====================================================================
        # RÉCAPITULATIF
        # ====================================================================
        
        print("\n" + "="*60)
        print("✅ BASE DE DONNÉES INITIALISÉE AVEC SUCCÈS !")
        print("="*60)
        print(f"\n📊 STATISTIQUES:")
        print(f"   👤 Utilisateurs: {User.query.count()}")
        print(f"      - Admin: 1")
        print(f"      - Agriculteurs: {User.query.filter_by(role=UserRole.FARMER).count()}")
        print(f"      - Investisseurs: {User.query.filter_by(role=UserRole.INVESTOR).count()}")
        print(f"   📦 Projets: {Project.query.count()}")
        print(f"      - Publiés: {Project.query.filter_by(is_published=True).count()}")
        print(f"   💰 Contributions: {Contribution.query.count()}")
        print(f"   📚 Formations: {Training.query.count()}")
        print(f"   📝 Mises à jour: {HarvestUpdate.query.count()}")
        print(f"   ⚠️ Alertes météo: {WeatherAlert.query.count()}")
        print(f"   📍 Points de collecte: {CollectionPoint.query.count()}")
        print(f"   🔔 Notifications: {Notification.query.count()}")
        print("\n🔑 COMPTES DE TEST:")
        print("   Admin: admin@agrinvest.ht / Admin123!")
        print("   Agriculteur: jean.baptiste@agrinvest.ht / Farmer123!")
        print("   Investisseur: paul.bernard@email.com / Invest123!")
        print("\n🌐 URL de test:")
        print("   Accueil: http://localhost:5000/")
        print("   Projets: http://localhost:5000/projects")
        print("   Login: http://localhost:5000/login")
        print("   Dashboard: http://localhost:5000/dashboard")
        print("\n🚀 Pour lancer l'application: flask run --debug")
        print("="*60)


if __name__ == "__main__":
    init_db()