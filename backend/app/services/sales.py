"""Allocate cashier offers across categories in integer sen."""


def category_sales(items, paid_total):
    original = {code: 0 for code in ('MAINS', 'SNACKS', 'DRINKS', 'BEER')}
    for item in items:
        code = item['category_code']
        original[code] = original.get(code, 0) + item['line_total']
    subtotal = sum(original.values())
    if not subtotal or subtotal == paid_total:
        return original
    result = {code: value * paid_total // subtotal for code, value in original.items()}
    # Largest remainders keep the category totals equal to actual receipts exactly.
    remainder = paid_total - sum(result.values())
    ranked = sorted(original, key=lambda code: (-(original[code] * paid_total % subtotal), code))
    for code in ranked[:remainder]:
        result[code] += 1
    return result
