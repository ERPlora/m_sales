# Ventas y POS (módulo: `sales`)

Motor de ventas universal con soporte multi-impuesto, métodos de pago e informes.

## Propósito

El módulo Sales es el núcleo transaccional del hub. Centraliza todos los registros de venta independientemente del canal de origen (pantalla táctil POS, módulo de pedidos, módulo de delivery, etc.) y proporciona la capa de datos compartida sobre la que construyen el resto de módulos.

Responsabilidades principales: crear y completar ventas con líneas múltiples, pagos divididos multi-método, cálculos de impuestos, descuentos y anulaciones. Mantiene carritos activos y tickets aparcados (ventas en curso guardadas). Emite `sale.completed` y el hook `sales.after_checkout`, que desencadenan la deducción de stock (inventory), la generación de facturas (invoice), el cálculo de comisiones (commissions) y el registro de movimientos de caja (cash_register).

El módulo también gestiona la configuración de métodos de pago (efectivo, tarjeta, transferencia y métodos personalizados) y proporciona el panel de ventas con informes diarios, semanales y mensuales.

## Modelos

- `SalesSettings` — Singleton por hub. Habilitación de métodos de pago, indicadores de sincronización POS (productos, servicios), requerimiento de cliente, política de descuentos, caducidad de tickets aparcados, encabezado/pie de ticket.
- `PaymentMethod` — Tipo de pago configurado (efectivo, tarjeta, transferencia, otro) con nombre, icono e is_active.
- `Sale` — Registro de transacción principal: sale_number, estado (borrador/completada/anulada), source_module, canal, referencia del cliente, artículos, subtotal, importe de impuestos, descuento, total, detalles de pago, referencia del personal, referencia de mesa.
- `SaleItem` — Línea de artículo dentro de una venta: referencia de producto/servicio, nombre, cantidad, precio unitario, descuento, tipo impositivo, total.
- `ActiveCart` — Estado de venta en curso persistido en el servidor (para POS multi-dispositivo o recuperación tras fallo).
- `ParkedTicket` — Venta aparcada con nombre que puede recuperarse más tarde. Vinculada a una Sale en estado borrador.

## Rutas

`GET /m/sales/` — Panel de ventas con KPIs
`GET /m/sales/pos` — Interfaz POS (pantalla completa)
`GET /m/sales/history` — Historial de ventas con filtros
`GET /m/sales/reports` — Informes de ventas
`GET /m/sales/settings` — Configuración del módulo

## Eventos

### Emitidos

`sale.completed` — Se dispara tras completar una venta. Consumido por `invoice`, `inventory`, `commissions`, `cash_register`.
`sales.completed` — Evento alias consumido por `commissions`.

### Consumidos

`inventory.stock_updated` — Registrado para trazabilidad cuando el stock se actualiza externamente.

## Hooks

### Emitidos

`sales.after_checkout` — Se dispara tras el checkout. Usado por `orders` para vincular la venta a su registro de pedido. Usado por `cash_register` para registrar un movimiento de caja.

## Dependencias

- `customers`
- `inventory`
- `tables`

## Precio

Gratuito.
