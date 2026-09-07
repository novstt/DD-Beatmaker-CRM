from decimal import Decimal


def audit_split_total(price, splits):
    price = Decimal(str(price))
    total_pct = sum((Decimal(str(x.get('percent', 0))) for x in splits), Decimal('0'))
    total_amount = sum((Decimal(str(x.get('amount', 0))) for x in splits), Decimal('0'))
    return {
        'percent_total': total_pct,
        'amount_total': total_amount,
        'price': price,
        'balanced': total_pct == Decimal('100.00') and total_amount == price,
    }
