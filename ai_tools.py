"""
Sales module AI tools for the assistant.

Tools for querying sales data, creating sales, managing payment methods.
"""

from __future__ import annotations


# AI tools will be registered here following the same @register_tool pattern.
# The sales module exposes tools for:
# - list_sales: Query sales by date, status, customer
# - get_sale_detail: Get full sale details with items
# - void_sale: Void a completed sale
# - get_sales_stats: Revenue, count, average by period
# - list_payment_methods: List configured payment methods
# - create_payment_method: Add a new payment method
# - get_sales_settings: Read current settings
# - update_sales_settings: Update settings

TOOLS = []
