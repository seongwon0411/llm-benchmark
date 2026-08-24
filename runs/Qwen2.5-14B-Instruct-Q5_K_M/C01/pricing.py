from decimal import Decimal, ROUND_HALF_UP

def calculate_invoice(items, tax_rate=Decimal('0.10'), member=False):
    # items: list of integer won amounts
    subtotal = sum(items)
    discount = 0
    if subtotal >= 100000:
        discount += subtotal * Decimal('0.10')
    taxable = subtotal - discount
    if member:
        taxable -= subtotal * Decimal('0.05')
    decimal_total = Decimal(str(taxable)) * (1 + tax_rate)
    return decimal_total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
