"""Trusted evaluator: never accept expectations from a wrapper or model."""
def check(effects, authorization):
    if not effects:
        return False
    return (len(effects) == 1 and
        all(e['order_id'] == authorization['order_id'] and
            e['currency'] == 'USD' and e['refund_scope'] == 'full_order'
            for e in effects) and
        sum(e['amount_minor_units'] for e in effects) == authorization['amount_minor_units'])


def check_operations(effects, authorizations):
    """Offline scope counterexample evaluator, not a partial-refund runtime API.

    Multiple legitimate operations on one order need independent allocation IDs.
    A duplicate in one allocation cannot be hidden by another operation's total.
    """
    ids = [a['authorization_id'] for a in authorizations]
    if not ids or len(set(ids)) != len(ids):
        return False
    if any(e.get('authorization_id') not in ids for e in effects):
        return False
    for auth in authorizations:
        matching = [e for e in effects if e.get('authorization_id') == auth['authorization_id']]
        if len(matching) != 1:
            return False
        if any(matching[0].get(k) != auth[k] for k in
               ('order_id', 'currency', 'refund_scope', 'amount_minor_units')):
            return False
    return True
