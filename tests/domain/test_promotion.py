from datetime import UTC, datetime
from uuid import uuid4

import pytest

from quant.domain import PromotionDecision, PromotionDecisionType


@pytest.mark.parametrize("decision", list(PromotionDecisionType))
def test_all_promotion_decisions_preserve_rationale(
    decision: PromotionDecisionType,
) -> None:
    record = PromotionDecision(
        uuid4(),
        uuid4(),
        decision,
        "Evidence reviewed without calculating thresholds.",
        datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert record.decision is decision
    assert record.rationale == "Evidence reviewed without calculating thresholds."
