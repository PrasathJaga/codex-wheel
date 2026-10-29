"""Trusted evaluator: never accept expectations from a wrapper or model."""
def check(effects, authorization):
    if not effects:
        return False
    return (len(effects) == 1 and
        all(e['order_id'] == authorization['order_id'] and
            e['currency'] == 'USD' and e['refund_scope'] == 'full_order'
            for e in effects) and
        sum(e['amount_minor_units'] for e in effects) == authorization['amount_minor_units'])
