from __future__ import annotations

import pytest


@pytest.mark.qgis_integration
def test_qgis_runtime_is_available():
    import qgis  # noqa: F401

    assert qgis is not None
