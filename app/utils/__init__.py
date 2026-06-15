# app/utils/__init__.py
"""
Application Flask pour AgriInvest Haïti
Plateforme de financement participatif pour l'agriculture haïtienne
"""

from app.utils.helpers import *
from app.utils.decorators import *
from app.utils.errors import *
from app.utils.pagination import *
from app.utils.permissions import *
from app.utils.cache import *
from app.utils.logger import *
from app.utils.utils import *
from app.utils.constants import *
from app.utils.config import *
from app.utils.formatters import *
from app.utils.validators import *      
from app.utils.stripe import create_stripe_payment_intent, handle_stripe_webhook
from app.utils.paypal import *
from app.utils.moncash import *
from app.utils.pdf import *
from app.utils.analytics import *
from app.utils.seo import *
from app.utils.email_templates import *
from app.utils.pdf_templates import *

# Imports conditionnels pour éviter les erreurs
try:
    from app.utils.notifications import *
except ImportError:
    pass

try:
    from app.utils.cache import *
except ImportError:
    pass

try:
    from app.utils.logger import *
except ImportError:
    pass

try:
    from app.utils.email import *
except ImportError:
    pass

try:
    from app.utils.sms import *
except ImportError:
    pass

try:
    from app.utils.security import *
except ImportError:
    pass

try:
    from app.utils.i18n import *
except ImportError:
    pass

try:
    from app.utils.timezone import *
except ImportError:
    pass

try:
    from app.utils.file import *
except ImportError:
    pass

try:
    from app.utils.data import *
except ImportError:
    pass

try:
    from app.utils.decorators import *
except ImportError:
    pass

__all__ = [
    'utc_now', 'format_currency', 'format_date', 'slugify', 'generate_contract_pdf',
    'login_required', 'admin_required', 'NotFoundError', 'ValidationError', 'UnauthorizedError',
    'paginate_query', 'check_permissions', 'send_notification', 'cache_result', 'log_action',
    'calculate_investment_return', 'validate_email', 'validate_phone_number',
    'CURRENCY_SYMBOLS', 'INVESTMENT_TIERS', 'NOTIFICATION_TYPES',
    'load_config', 'format_investor_name', 'format_project_title', 'format_contribution_amount',
    'validate_contribution_amount', 'validate_project_data', 'validate_user_registration',
    'create_stripe_payment_intent', 'handle_stripe_webhook',
    'create_paypal_payment', 'handle_paypal_webhook',
    'create_moncash_payment', 'handle_moncash_webhook',
    'generate_investment_contract_pdf', 'generate_project_report_pdf',
    'send_welcome_email', 'send_contribution_confirmation_email', 'send_project_funded_notification_email',
    'send_sms_notification', 'track_user_action', 'generate_investment_report',
    'generate_seo_metadata', 'create_sitemap', 'hash_password', 'verify_password', 'generate_jwt_token', 'decode_jwt_token',
    'translate', 'get_locale', 'convert_to_timezone', 'get_user_timezone', 'save_file', 'allowed_file', 'get_file_url',
    'render_email_template', 'render_contract_pdf_template', 'render_report_pdf_template',
    'rate_limit', 'cache_response', 'log_execution_time',
    'BadRequestError', 'ForbiddenError', 'InternalServerError',
    'is_admin', 'is_investor', 'is_project_owner',
    'notify_investor', 'notify_project_owner',
    'clear_cache', 'get_cache_key',
    'log_error', 'log_info', 'log_warning',
    'generate_random_string', 'calculate_project_progress', 'validate_url',
    'MAX_CONTRIBUTION_AMOUNT', 'MIN_CONTRIBUTION_AMOUNT', 'SUPPORTED_CURRENCIES',
    'get_config_value', 'set_config_value',
    'format_investment_date', 'format_project_deadline',
    'validate_project_update', 'validate_user_profile_update',
    'refund_stripe_payment', 'retrieve_stripe_payment_intent',
    'refund_paypal_payment', 'retrieve_paypal_payment',
    'refund_moncash_payment', 'retrieve_moncash_payment',
    'generate_investment_summary_pdf', 'generate_project_overview_pdf',
    'send_password_reset_email', 'send_project_update_notification_email',
    'send_sms_verification_code', 'track_page_view', 'generate_user_activity_report',
    'generate_meta_tags', 'create_robots_txt'
]