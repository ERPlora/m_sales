"""
Sales module AI context — injected into the LLM system prompt.

Provides the LLM with knowledge about the module's models, relationships,
and standard operating procedures.
"""

CONTEXT = """
## Sales Module

Universal sales engine. Models: Sale, SaleItem, PaymentMethod, SalesSettings, ActiveCart, ParkedTicket.

### Sale Model
- Fields: sale_number (YYYYMMDD-0001), status (draft/pending/completed/voided/refunded)
- Amounts: subtotal (net), tax_amount, tax_breakdown (JSONB by rate), discount_amount, discount_percent, total
- Payment: payment_method_id (FK), payment_method_name (snapshot), amount_tendered, change_due
- Customer: customer_id (FK to customers), customer_name (snapshot)
- Employee: employee_id (UUID of LocalUser)

### SaleItem Model
- Fields: product_id (FK to inventory), product_name (snapshot), product_sku, is_service
- Amounts: quantity, unit_price, discount_percent, tax_rate, tax_class_name
- Calculated: net_amount, tax_amount, line_total
- Modifiers: JSONB for extras (size, toppings, etc.)

### Multi-Tax Support
- Each SaleItem has its own tax_rate
- Sale.tax_breakdown aggregates by rate: {"21.00": {"base": 100.00, "tax": 21.00}, "10.00": ...}
- Supports tax-included and tax-excluded pricing (SalesSettings.default_tax_included)

### PaymentMethod Model
- name, type (cash/card/transfer/other), icon, is_active, sort_order
- opens_cash_drawer (triggers Bridge), requires_change (shows change calc)

### SalesSettings (singleton per hub)
- Payment toggles: allow_cash, allow_card, allow_transfer
- POS sync: sync_products, sync_services
- Options: require_customer, allow_discounts, enable_parked_tickets
- Tax: default_tax_included
- Receipt: receipt_header, receipt_footer, receipt_footer_image

### ActiveCart
- One cart per employee per hub. Persisted across restarts.
- cart_data JSONB: {items: [...]}

### ParkedTicket
- Temporarily saved carts. ticket_number (PARK-YYYYMMDD-0001)
- cart_data JSONB, expires_at (configurable hours)
- Auto-cleanup of expired tickets

### Key Relationships
- Sale -> SaleItem (one-to-many, CASCADE)
- Sale -> PaymentMethod (FK, SET NULL on delete)
- Sale -> Customer (FK to customers module)
- Sale -> Employee (UUID, no FK)

### Architecture Notes
- sales is the universal engine — NO POS interface (that's the pos module)
- pos module uses sales for completing transactions
- orders module creates Sale with status=draft, source_module='orders'
- commands module reads SaleItems for kitchen display
"""

SOPS = [
    {
        "id": "check_sales_today",
        "triggers_es": ["ventas de hoy", "cuantas ventas hoy", "ingresos hoy"],
        "triggers_en": ["today's sales", "how many sales today", "revenue today"],
        "steps": ["get_sales_stats"],
        "modules_required": ["sales"],
    },
    {
        "id": "find_sale",
        "triggers_es": ["buscar venta", "encontrar venta", "ticket numero"],
        "triggers_en": ["find sale", "search sale", "ticket number"],
        "steps": ["list_sales"],
        "modules_required": ["sales"],
    },
    {
        "id": "void_sale",
        "triggers_es": ["anular venta", "cancelar venta"],
        "triggers_en": ["void sale", "cancel sale"],
        "steps": ["get_sale_detail", "void_sale"],
        "modules_required": ["sales"],
    },
]
