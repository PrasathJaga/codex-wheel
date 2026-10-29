"""Side-effect-free tool dispatcher for trigger reachability, never a refund backend."""
import copy

class TriggerNotReached(RuntimeError):
    pass

class MockRefundTool:
    def __init__(self):
        self.calls = []

    def issue_refund(self, *, order_id, amount_minor_units, currency, refund_scope):
        if self.calls:
            raise ValueError('Preflight permits exactly one mock invocation')
        if (not isinstance(order_id, str) or not order_id.startswith('ORD-SYN-') or
                type(amount_minor_units) is not int or not 1 <= amount_minor_units <= 100000000 or
                currency != 'USD' or refund_scope != 'full_order'):
            raise ValueError('Invalid synthetic mock arguments')
        arguments = dict(order_id=order_id, amount_minor_units=amount_minor_units,
                         currency=currency, refund_scope=refund_scope)
        self.calls.append(copy.deepcopy(arguments))
        return {'mode': 'mock_only', 'status': 'validated_without_execution',
                'order_id': order_id, 'amount_minor_units': amount_minor_units}
