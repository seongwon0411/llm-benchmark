from decimal import Decimal, ROUND_HALF_UP

def calculate_invoice(items, tax_rate=0.10, member=False):
    # items: list of integer won amounts
    subtotal = sum(items)
    discount = 0
    if subtotal >= 100000:
        discount += subtotal * 0.10
    if member:
        discount += (subtotal - discount) * 0.05  # 회원할인은 금액할인 후 적용
    taxable = subtotal - discount
    total = Decimal(str(taxable)) * Decimal(str(1 + tax_rate))
    return int(total.to_integral_value(rounding=ROUND_HALF_UP))