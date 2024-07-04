import pytest
from gateway.contracts import Usage
from gateway.cache import CacheEntry

@pytest.mark.parametrize("bad", [True,1.5,"2"])
def test_token_usage_is_not_coerced(bad):
    with pytest.raises(ValueError): Usage(input_tokens=bad,output_tokens=1)
    with pytest.raises(ValueError): CacheEntry(text="x",input_tokens=1,output_tokens=bad,backend="b",finish_reason="stop")
