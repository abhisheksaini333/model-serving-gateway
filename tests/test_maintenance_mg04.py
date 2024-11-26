import pytest
from gateway.registry import BackendSpec

@pytest.mark.parametrize("field,bad", [("capacity",True),("max_input_tokens",1.5),("max_output_tokens","100"),("revision"," ")])
def test_backend_limits_and_revision_are_explicit(field,bad):
    spec={"name":"b","model":"m","revision":"r"};spec[field]=bad
    with pytest.raises(ValueError): BackendSpec(**spec)
