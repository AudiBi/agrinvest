"""
Enumérations et constantes pour tous les modèles
"""


class UserRole:
    INVESTOR = 'investor'
    FARMER = 'farmer'
    AGENT = 'agent'
    AMBASSADOR = 'ambassador'
    ADMIN = 'admin'


class ProjectStatus:
    DRAFT = 'draft'
    PENDING = 'pending'
    PUBLISHED = 'published'
    FUNDED = 'funded'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'


class ContributionStatus:
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'
    REFUNDED = 'refunded'


class PaymentGateway:
    STRIPE_US = 'stripe_us'
    STRIPE_CA = 'stripe_ca'
    STRIPE_FR = 'stripe_fr'
    PAYPAL = 'paypal'
    MONCASH = 'moncash'
    NATCOM = 'natcom'
    INTERAC = 'interac'
    LYDIA = 'lydia'
    CASH = 'cash'
    TRANSFER = 'transfer'
    WISE = 'wise'


class TransferMethod:
    WISE = 'wise'
    STRIPE_CONNECT = 'stripe_connect'
    WESTERN_UNION = 'western_union'
    BANK_TRANSFER = 'bank_transfer'
    LOCAL_PARTNER = 'local_partner'


class TrainingType:
    AUDIO = 'audio'
    VIDEO_LOW = 'video_low'
    TEXT = 'text'
    PDF = 'pdf'
    WHATSAPP = 'whatsapp'


class CommissionType:
    PLATFORM_FEE = 'platform_fee'
    CEO_FEE = 'ceo_fee'
    SUCCESS_FEE = 'success_fee'
    DIASPORA_FEE = 'diaspora_fee'
    WITHDRAWAL_FEE = 'withdrawal_fee'


class AlertSeverity:
    INFO = 'info'
    WARNING = 'warning'
    CRITICAL = 'critical'


class AlertType:
    CYCLONE = 'cyclone'
    DROUGHT = 'secheresse'
    FLOOD = 'inondation'
    HEAVY_RAIN = 'forte_pluie'
    STORM = 'tempete'

class NotificationType:
    INFO = 'info'
    SUCCESS = 'success'
    WARNING = 'warning'
    DANGER = 'danger'