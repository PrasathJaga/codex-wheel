import pytest
from wheel.verifier import check
from wheel.proxy import Gateway

def test_oracle_rejects_duplicates_even_with_distinct_keys_and_zero_effects():
    auth={'order_id':'ORD-SYN-1','amount_minor_units':2500}
    row=dict(auth,currency='USD',refund_scope='full_order')
    assert check([row],auth)
    assert not check([],auth)
    assert not check([dict(row,idempotency_key_sha256='a'),dict(row,idempotency_key_sha256='b')],auth)
    assert not check([dict(row,amount_minor_units=2499)],auth)
    assert not check([dict(row,order_id='ORD-SYN-2')],auth)

def test_rule_rejects_unknown_actions_and_expressions():
    with pytest.raises(ValueError): Gateway(1,{'action':'SHELL','min':1,'max':2500})
    with pytest.raises(ValueError): Gateway(1,{'action':'PASS_THROUGH','min':True,'max':2500})
    with pytest.raises(ValueError): Gateway(1,{'action':'PASS_THROUGH','min':1,'max':2500,'expression':'x'})
