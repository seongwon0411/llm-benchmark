from decimal import Decimal, ROUND_HALF_UP

def calculate_invoice(items, tax_rate=0.10, member=False):
    # items: list of integer won amounts
    subtotal = sum(items)
    discount = 0
    if subtotal >= 100000:
        discount += subtotal * 0.10  # Volume discount applied first
    if member:
        discount += (subtotal - discount) * 0.05  # Member discount applied after volume discount
    taxable = subtotal - discount
    total = Decimal(str(taxable)) * (Decimal('1') + Decimal(str(tax_rate)))
    return int(total.to_integral_value(rounding=ROUND_HALF_UP))
