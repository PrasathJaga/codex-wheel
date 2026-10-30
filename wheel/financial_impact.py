"""Observed synthetic refund amounts, kept per world; no frequency inference."""

def observed(document):
    authorized = document['plan']['fixture'].get('amount_minor_units')
    if type(authorized) is not int or authorized <= 0:
        raise ValueError('Invalid authorized minor units')
    currency = document['plan']['fixture'].get('currency', 'USD')
    if currency != 'USD':
        raise ValueError('Only the supported USD refund domain is admitted')
    results = []
    for index, world in enumerate(document['worlds']):
        row = {'world': world['world'], 'trial': world['trial'], 'record_pointer': '/worlds/' + str(index),
               'status': world['status'], 'currency': 'USD', 'authorized_minor_units': authorized,
               'committed_minor_units': None, 'excess_minor_units': None, 'shortfall_minor_units': None}
        if world['status'] == 'completed':
            effects = world.get('effects')
            if not isinstance(effects, list): raise ValueError('Missing ledger effects')
            if any(e.get('currency') != 'USD' or type(e.get('amount_minor_units')) is not int
                   or e['amount_minor_units'] <= 0 for e in effects):
                raise ValueError('Invalid or mixed-currency ledger')
            if len({e['effect_id'] for e in effects}) != len(effects):
                raise ValueError('Duplicate ledger identity')
            total = sum(e['amount_minor_units'] for e in effects)
            row.update(committed_minor_units=total, excess_minor_units=max(0, total-authorized),
                       shortfall_minor_units=max(0, authorized-total))
        results.append(row)
    return results
