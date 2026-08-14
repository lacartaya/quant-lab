from collections.abc import MutableMapping
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest

from quant.domain import Strategy, StrategyVersion

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_strategy_construction() -> None:
    strategy = Strategy(uuid4(), "Trend", "Logical concept", "momentum", NOW)
    assert strategy.name == "Trend"


def make_version(*, version: str = "1", git_commit: str = "abc123") -> StrategyVersion:
    return StrategyVersion(uuid4(), uuid4(), version, git_commit, {"window": 20}, NOW)


def test_strategy_version_is_immutable_and_copies_parameters() -> None:
    parameters: dict[str, object] = {"window": 20}
    version = StrategyVersion(uuid4(), uuid4(), "1", "abc123", parameters, NOW)
    parameters["window"] = 50
    assert version.parameters["window"] == 20
    field_name = "version"
    with pytest.raises(FrozenInstanceError):
        setattr(version, field_name, "2")
    with pytest.raises(TypeError):
        cast(MutableMapping[str, object], version.parameters)["window"] = 10


@pytest.mark.parametrize(("version", "commit"), [("", "abc"), ("1", "")])
def test_strategy_version_requires_version_and_commit(
    version: str, commit: str
) -> None:
    with pytest.raises(ValueError):
        make_version(version=version, git_commit=commit)
