import pytest
from gateway.contracts import GenerationRequest

@pytest.mark.parametrize("field,bad", [("max_new_tokens",True),("max_new_tokens",2.5),("timeout_ms","1000"),("timeout_ms",100.5)])
def test_request_limits_require_integers(field,bad):
    with pytest.raises(ValueError): GenerationRequest(model="m",prompt="hello",**{field:bad})
