import asyncio
import pytest
from gateway.admission import Admission

@pytest.mark.parametrize("args", [(True,1),(1.5,1),(1,True),(1,1.5)])
def test_admission_limits_are_integers(args):
    with pytest.raises(ValueError): Admission(*args)

def test_nonfinite_deadline_never_takes_capacity():
    async def scenario():
        admission=Admission(1,1)
        with pytest.raises(ValueError): await admission.acquire("tenant",float("nan"))
        assert admission.active == 0
    asyncio.run(scenario())
