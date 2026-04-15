# Sales & POS (module: `sales`)

Universal sales engine with multi-tax support, payment methods, and reporting.

## Purpose

The Sales module is the transactional core of the hub. It owns all sale records regardless of origin channel (POS touch screen, orders module, delivery module, etc.) and provides the shared data layer that other modules build on top of.

Key responsibilities: creating and completing sales with multi-line items, multi-payment splits, tax calculations, discounts, and voiding. It maintains active shopping carts and parked tickets (saved in-progress sales). It emits `sale.completed` and `sales.after_checkout` hook, which drive stock deduction (inventory), invoice generation (invoice), commission calculation (commissions), and cash movement recording (cash_register).

The module also owns payment method configuration (cash, card, transfer, and custom methods) and provides the sales dashboard with daily/weekly/monthly reporting.

## Models

- `SalesSettings` — Singleton per hub. Payment method enablement, POS sync flags (products, services), require-customer, discount policy, parked ticket expiry, receipt header/footer.
- `PaymentMethod` — Configured tender type (cash, card, transfer, other) with name, icon, is_active.
- `Sale` — Core transaction record: sale_number, status (draft/completed/void), source_module, channel, customer reference, items, subtotal, tax_amount, discount, total, payment details, staff reference, table reference.
- `SaleItem` — Line item within a sale: product/service reference, name, quantity, unit_price, discount, tax_rate, total.
- `ActiveCart` — In-progress sale state persisted server-side (for multi-device POS or crash recovery).
- `ParkedTicket` — Named parked sale that can be recalled later. Linked to a Sale in draft status.

## Routes

`GET /m/sales/` — Sales dashboard with KPIs
`GET /m/sales/pos` — POS interface (full-screen)
`GET /m/sales/history` — Sales history with filters
`GET /m/sales/reports` — Sales reports
`GET /m/sales/settings` — Module settings

## Events

### Emitted

`sale.completed` — Fired after a sale is completed. Consumed by `invoice`, `inventory`, `commissions`, `cash_register`.
`sales.completed` — Alias event consumed by `commissions`.

### Consumed

`inventory.stock_updated` — Logged for traceability when stock is updated externally.

## Hooks

### Emitted

`sales.after_checkout` — Fired after checkout. Used by `orders` to link the sale back to its order record. Used by `cash_register` to record a cash movement.

## Dependencies

- `customers`
- `inventory`
- `tables`

## Pricing

Free.
