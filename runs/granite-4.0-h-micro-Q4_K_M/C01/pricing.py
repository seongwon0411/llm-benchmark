from decimal import Decimal, ROUND_HALF_UP

def calculate_invoice(items, tax_rate=0.10, member=False):
    # items: list of integer won amounts
    subtotal = sum(items)
    discount = 0
    if subtotal >= 100000:
        discount += subtotal * 0.10
    if member:
        discount += subtotal * 0.05  # Apply after volume discount
    taxable = subtotal - discount
    total = taxable * (1 + tax_rate)
    return Decimal(str(taxable * (1 + tax_rate)))
