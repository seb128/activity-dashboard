import pytest
from activity_dashboard.adapters import gmail as gmail_adapter


def test_name_constant():
    assert gmail_adapter.NAME == "gmail"


def test_fetch_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        gmail_adapter.fetch(subject=None, settings=None)
