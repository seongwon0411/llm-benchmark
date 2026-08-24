from decimal import Decimal, ROUND_HALF_UP
def calculate_invoice(items, tax_rate=Decimal('0.10'), member=False):
    # items: list of integer won amounts
    tax_rate = Decimal(tax_rate)  # Ensure tax_rate is a Decimal
    subtotal = sum(items)
    taxable = Decimal(subtotal)
    if taxable >= 100000:
        taxable *= Decimal('0.90')  # Apply volume discount first
    if member:
        taxable *= Decimal('0.95')  # Then apply member discount
    total = taxable * (Decimal('1') + tax_rate)
    return total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
