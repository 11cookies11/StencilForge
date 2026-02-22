from __future__ import annotations

import pytest

from stencilforge.pipeline.engine import get_model_engine


@pytest.mark.parametrize("name", ["cadquery", "trimesh", "sfmesh", "SFMESH"])
def test_get_model_engine_supported(name: str) -> None:
    engine = get_model_engine(name)
    assert engine.name in {"cadquery", "trimesh", "sfmesh"}


def test_get_model_engine_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unsupported model backend"):
        get_model_engine("unknown")
