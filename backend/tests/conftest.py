from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.data.bootstrap import bootstrap_sample_data
from app.data.factory import get_repository


@pytest.fixture()
def repo():
    r = get_repository()
    if hasattr(r, "clear"):
        r.clear()
    bootstrap_sample_data(r)
    return r
