import copy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from wheel import patcher as p
from wheel.g6 import variants
from wheel.plan_guard import IntegrityError


def proposal():
    return {'old_text':'if (prior != null && request.amountMinorUnits() > 2500) {',
            'new_text':'if (prior != null) {','reason':'Reuse the existing effect for identical retry keys.'}


def test_only_reviewed_restoration_can_be_applied():
    policy=p.protocol();java,_=variants()
    assert p.apply_proposal(proposal(),java['M1'],policy)==java['base']
    for text in ('if (false) {','if (prior != null && request.amountMinorUnits() == 2500) {','return null;'):
        bad=proposal();bad['new_text']=text
        with pytest.raises(IntegrityError):p.apply_proposal(bad,java['M1'],policy)
    bad=proposal();bad['path']='wheel/verifier.py'
    with pytest.raises(IntegrityError):p.apply_proposal(bad,java['M1'],policy)
    with pytest.raises(IntegrityError):p.apply_proposal(proposal(),java['M1']+'// extra edit',policy)


def test_incomplete_or_non_tool_proposal_is_rejected():
    client=Mock()
    client.chat.completions.create.return_value=SimpleNamespace(choices=[SimpleNamespace(finish_reason='length')])
    with pytest.raises(IntegrityError):p.propose(client,{},[])
    assert client.chat.completions.create.call_count==1


def test_origin_hash_is_checked_before_parsing(tmp_path):
    file=tmp_path/'origin.zip';file.write_bytes(b'not an origin')
    with pytest.raises(IntegrityError):p.load_origin(file,p.protocol())
