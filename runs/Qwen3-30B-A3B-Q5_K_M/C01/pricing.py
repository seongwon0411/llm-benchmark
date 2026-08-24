from decimal import Decimal, ROUND_HALF_UP

def calculate_invoice(items, tax_rate=0.10, member=False):
    subtotal = sum(items)
    discount = Decimal('0')
    if subtotal >= 100000:
        volume_discount = Decimal(str(subtotal)) * Decimal('0.10')
        discount += volume_discount
    if member:
        discounted_subtotal = Decimal(str(subtotal - discount))
        member_discount = discounted_subtotal * Decimal('0.05')
        discount += member_discount
    taxable = Decimal(str(subtotal)) - discount
    tax_rate_decimal = Decimal(str(tax_rate))
    total = taxable * (1 + tax_rate_decimal)
    return total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
