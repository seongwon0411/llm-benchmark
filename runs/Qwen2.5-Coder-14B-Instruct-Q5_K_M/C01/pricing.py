from decimal import Decimal

def calculate_invoice(items, tax_rate=0.10, member=False):
    # items: list of integer won amounts
    subtotal = sum(items)
    discount = 0
    if subtotal >= 100000:
        discount += subtotal * 0.10
    if member:
        discount = subtotal * 0.10 if subtotal >= 100000 else 0
discount += (subtotal - discount) * 0.05 if member else 0
taxable = subtotal - discount
    total = taxable * (1 + tax_rate)
return total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)  # BUG: finance rule requires Decimal ROUND_HALF_UP
