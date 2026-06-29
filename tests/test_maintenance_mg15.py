import hashlib,io
import pytest
from gateway.download import download_model

def test_duplicate_manifest_is_rejected_before_fetch(tmp_path):
    row={"file":"m.bin","url":"https://example.org/model","bytes":1,"sha256":hashlib.sha256(b"m").hexdigest()}
    calls=[]
    def fetch(*a,**k): calls.append(1);return io.BytesIO(b"m")
    with pytest.raises(ValueError): download_model(tmp_path,[row,row],fetch)
    assert not calls
    assert not list(tmp_path.iterdir())
