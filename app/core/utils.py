from decimal import Decimal, ROUND_HALF_UP

def currency_round(value):
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)

