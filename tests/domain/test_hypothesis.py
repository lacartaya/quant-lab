from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from quant.domain import Hypothesis, HypothesisStatus


def make_hypothesis(
    *,
    title: str = "Momentum persists over medium horizons",
    market: str = "US equities",
    timeframe: str = "daily",
    status: HypothesisStatus = HypothesisStatus.ACTIVE_RESEARCH,
    reconsideration_conditions: str | None = None,
) -> Hypothesis:
    return Hypothesis(
        id=uuid4(),
        title=title,
        description="A falsifiable research statement.",
        rationale="Behavioral persistence may exist.",
        strategy_family="momentum",
        market=market,
        timeframe=timeframe,
        expected_benefit="Positive risk-adjusted returns",
        expected_tradeoff="Turnover",
        success_criteria="Pre-registered criteria",
        rejection_criteria="Pre-registered rejection criteria",
        status=status,
        reconsideration_conditions=reconsideration_conditions,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_hypothesis_construction_and_statuses() -> None:
    hypothesis = make_hypothesis()
    assert hypothesis.title == "Momentum persists over medium horizons"
    assert set(HypothesisStatus) == {
        HypothesisStatus.KNOWN_REPLICATED,
        HypothesisStatus.ACTIVE_RESEARCH,
        HypothesisStatus.VALIDATED_INTERNAL,
        HypothesisStatus.REJECTED,
        HypothesisStatus.RETIRED,
    }


def test_rejected_hypothesis_preserves_context() -> None:
    hypothesis = make_hypothesis(
        status=HypothesisStatus.REJECTED,
        market="European equities",
        timeframe="hourly",
        reconsideration_conditions="Re-test with a longer sample",
    )
    assert hypothesis.market == "European equities"
    assert hypothesis.timeframe == "hourly"
    assert hypothesis.reconsideration_conditions == "Re-test with a longer sample"


def test_empty_hypothesis_title_is_rejected() -> None:
    with pytest.raises(ValueError, match="title cannot be empty"):
        make_hypothesis(title="  ")


def test_hypothesis_is_immutable() -> None:
    hypothesis = make_hypothesis()
    field_name = "title"
    with pytest.raises(FrozenInstanceError):
        setattr(hypothesis, field_name, "Changed")
