"""
Sales module manifest.

Universal sales engine: Sale, SaleItem, PaymentMethod, SalesSettings,
ActiveCart, ParkedTicket. No POS interface (that's the pos module).
"""


# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------
MODULE_ID = "sales"
MODULE_NAME = "Sales & POS"
MODULE_VERSION = "2.3.1"
MODULE_ICON = "cart-outline"
MODULE_DESCRIPTION = "Universal sales engine with multi-tax support, payment methods, and reporting"
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
    "label": "Sales",
    "icon": "cart-outline",
    "order": 5,
}

# ---------------------------------------------------------------------------
# Navigation tabs (bottom tabbar in module views)
# ---------------------------------------------------------------------------
NAVIGATION = [
    {"id": "dashboard", "label": "Dashboard", "icon": "speedometer-outline", "view": "dashboard"},
    {"id": "pos", "label": "POS", "icon": "storefront-outline", "view": "pos_screen", "fullpage": True},
    {"id": "history", "label": "History", "icon": "time-outline", "view": "history"},
    {"id": "reports", "label": "Reports", "icon": "bar-chart-outline", "view": "reports"},
    {"id": "settings", "label": "Settings", "icon": "settings-outline", "view": "settings"},
]

# ---------------------------------------------------------------------------
# Dependencies (other modules required to be active)
# ---------------------------------------------------------------------------
DEPENDENCIES: list[str] = ["customers", "inventory"]

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
PERMISSIONS = [
    ("view_sale", "View sales"),
    ("add_sale", "Add sales"),
    ("change_sale", "Edit sales"),
    ("delete_sale", "Delete sales"),
    ("void_sale", "Void sales"),
    ("view_paymentmethod", "View payment methods"),
    ("add_paymentmethod", "Add payment methods"),
    ("change_paymentmethod", "Edit payment methods"),
    ("delete_paymentmethod", "Delete payment methods"),
    ("view_reports", "View reports"),
    ("manage_settings", "Manage settings"),
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
