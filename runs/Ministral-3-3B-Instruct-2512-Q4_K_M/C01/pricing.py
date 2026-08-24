from decimal import Decimal, ROUND_HALF_UP

def calculate_invoice(items, tax_rate=0.10, member=False):
    subtotal = sum(items)
    discount = 0
    if subtotal >= 100000:
        discount += subtotal * Decimal('0.10')
    if member:
        discount += subtotal * Decimal('0.05')
    taxable = subtotal - discount
    total = taxable * (Decimal(str(tax_rate)) + Decimal('1'))
    return int(total.quantize(Decimal('0'), rounding=ROUND_HALF_UP))  # tax_rate는 Decimal로 계산
    return int(total.to_round(Decimal('0'), rounding=ROUND_HALF_UP))
