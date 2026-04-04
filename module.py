"""
Sales module manifest.

Universal sales engine: Sale, SaleItem, PaymentMethod, SalesSettings,
ActiveCart, ParkedTicket. No POS interface (that's the pos module).
"""

from app.core.i18n import LazyString

# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------
MODULE_ID = "sales"
MODULE_NAME = LazyString("Sales & POS", module_id="sales")
MODULE_VERSION = "2.0.0"
MODULE_ICON = "cart-outline"
MODULE_DESCRIPTION = LazyString(
    "Universal sales engine with multi-tax support, payment methods, and reporting",
    module_id="sales",
)
MODULE_AUTHOR = "ERPlora"
MODULE_CATEGORY = "pos"

# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------
HAS_MODELS = True
MIDDLEWARE = ""

# ---------------------------------------------------------------------------
# Menu (sidebar entry)
# ---------------------------------------------------------------------------
MENU = {
    "label": LazyString("Sales", module_id="sales"),
    "icon": "cart-outline",
    "order": 5,
}

# ---------------------------------------------------------------------------
# Navigation tabs (bottom tabbar in module views)
# ---------------------------------------------------------------------------
NAVIGATION = [
    {"id": "dashboard", "label": LazyString("Dashboard", module_id="sales"), "icon": "speedometer-outline", "view": "dashboard"},
    {"id": "pos", "label": LazyString("POS", module_id="sales"), "icon": "storefront-outline", "view": "pos_screen", "fullpage": True},
    {"id": "history", "label": LazyString("History", module_id="sales"), "icon": "time-outline", "view": "history"},
    {"id": "reports", "label": LazyString("Reports", module_id="sales"), "icon": "bar-chart-outline", "view": "reports"},
    {"id": "settings", "label": LazyString("Settings", module_id="sales"), "icon": "settings-outline", "view": "settings"},
]

# ---------------------------------------------------------------------------
# Dependencies (other modules required to be active)
# ---------------------------------------------------------------------------
DEPENDENCIES: list[str] = ["customers", "inventory"]

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
PERMISSIONS = [
    ("view_sale", LazyString("View sales", module_id="sales")),
    ("add_sale", LazyString("Add sales", module_id="sales")),
    ("change_sale", LazyString("Edit sales", module_id="sales")),
    ("delete_sale", LazyString("Delete sales", module_id="sales")),
    ("void_sale", LazyString("Void sales", module_id="sales")),
    ("view_paymentmethod", LazyString("View payment methods", module_id="sales")),
    ("add_paymentmethod", LazyString("Add payment methods", module_id="sales")),
    ("change_paymentmethod", LazyString("Edit payment methods", module_id="sales")),
    ("delete_paymentmethod", LazyString("Delete payment methods", module_id="sales")),
    ("view_reports", LazyString("View reports", module_id="sales")),
    ("manage_settings", LazyString("Manage settings", module_id="sales")),
]

ROLE_PERMISSIONS = {
    "admin": ["*"],
    "manager": [
        "view_sale", "add_sale", "change_sale", "void_sale",
        "view_paymentmethod", "add_paymentmethod", "change_paymentmethod",
        "view_reports", "manage_settings",
    ],
    "employee": ["view_sale", "add_sale", "view_paymentmethod"],
}

# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------
SCHEDULED_TASKS: list[dict] = []

# ---------------------------------------------------------------------------
# Pricing (free module)
# ---------------------------------------------------------------------------
# PRICING = {"monthly": 0, "yearly": 0}
