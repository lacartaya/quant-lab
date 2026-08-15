from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from quant.domain import HypothesisStatus
from quant.domain.knowledge import (
    EvidenceKind,
    EvidenceReference,
    KnowledgeRecord,
    PriorArtCheckResult,
    PriorArtConfiguration,
    PriorArtDisposition,
    PriorArtMatch,
    PriorArtMatchType,
    ReconsiderationCondition,
    ResearchSignature,
)
from quant.knowledge import check_prior_art, research_fingerprint

NOW = datetime(2020, 1, 1, tzinfo=UTC)
HYPOTHESIS_ID = UUID("00000000-0000-0000-0000-000000000001")
RECORD_ID = UUID("00000000-0000-0000-0000-000000000002")
CONFIGURATION = PriorArtConfiguration(numeric_parameter_relative_tolerance=0.05)


def signature(
    *,
    market: str = "US_EQUITIES",
    instrument: str = "SPY",
    timeframe: str = "1D",
    short_window: int = 50,
    long_window: int = 200,
) -> ResearchSignature:
    return ResearchSignature(
        strategy_family="moving_average_trend",
        market=market,
        instrument=instrument,
        timeframe=timeframe,
        parameters={"short_window": short_window, "long_window": long_window},
        execution_model="backtest-engine-v1",
        cost_model="percentage-fee-v1",
    )


def rejected_record(
    value: ResearchSignature | None = None,
    conditions: tuple[ReconsiderationCondition, ...] = (),
) -> KnowledgeRecord:
    value = value or signature()
    return KnowledgeRecord(
        id=RECORD_ID,
        hypothesis_id=HYPOTHESIS_ID,
        derived_from_hypothesis_id=None,
        status=HypothesisStatus.REJECTED,
        signature=value,
        tested_start_at=datetime(2010, 1, 1, tzinfo=UTC),
        tested_end_at=datetime(2020, 1, 1, tzinfo=UTC),
        summary="No robust out-of-sample edge",
        rejection_reason="OOS and stress evidence deteriorated",
        reconsideration_conditions=conditions,
        reconsideration_rationale=None,
        evidence_refs=(
            EvidenceReference(
                EvidenceKind.VALIDATION_RUN,
                UUID("00000000-0000-0000-0000-000000000005"),
            ),
        ),
        research_fingerprint=research_fingerprint(value),
        created_at=NOW,
    )


def single_match(
    candidate: ResearchSignature, record: KnowledgeRecord | None = None
) -> tuple[PriorArtCheckResult, PriorArtMatch]:
    result = check_prior_art(candidate, [record or rejected_record()], CONFIGURATION)
    assert len(result.matches) == 1
    return result, result.matches[0]


def test_exact_duplicate_is_deterministically_detected() -> None:
    result, match = single_match(signature())
    assert result.duplicate_detected
    assert match.match_type is PriorArtMatchType.EXACT
    assert match.disposition is PriorArtDisposition.DUPLICATE


@pytest.mark.parametrize(
    ("candidate", "expected_change"),
    [
        (signature(market="EU_EQUITIES", instrument="DAX"), "same_market"),
        (signature(timeframe="1H"), "same_timeframe"),
    ],
)
def test_domain_changes_are_family_prior_art_not_duplicates(
    candidate: ResearchSignature, expected_change: str
) -> None:
    result, match = single_match(candidate)
    assert not result.duplicate_detected
    assert match.match_type is PriorArtMatchType.SAME_STRATEGY_FAMILY
    assert match.similarity_evidence[expected_change] is False


def test_trivial_parameter_variant_is_blocked_rejected_prior_art() -> None:
    result, match = single_match(signature(short_window=51))
    assert match.match_type is PriorArtMatchType.SIMILAR_PARAMETERS
    assert match.disposition is PriorArtDisposition.REJECTED_PRIOR_ART
    assert result.blocked_by_rejected_prior_art


def test_material_parameter_change_is_not_near_equivalent() -> None:
    result, match = single_match(signature(short_window=10, long_window=300))
    assert match.match_type is PriorArtMatchType.SAME_DOMAIN
    assert match.disposition is PriorArtDisposition.POTENTIAL_PRIOR_ART
    assert not result.blocked_by_rejected_prior_art


def test_declared_new_market_condition_permits_reconsideration() -> None:
    record = rejected_record(conditions=(ReconsiderationCondition.NEW_MARKET,))
    _, match = single_match(signature(market="EU_EQUITIES", instrument="DAX"), record)
    assert match.disposition is PriorArtDisposition.RECONSIDERATION_CONDITION_MET
    assert match.similarity_evidence["conditions_met"] == ["new_market"]


def test_same_domain_does_not_satisfy_new_market_condition() -> None:
    record = rejected_record(conditions=(ReconsiderationCondition.NEW_MARKET,))
    result, match = single_match(signature(short_window=51), record)
    assert match.disposition is PriorArtDisposition.REJECTED_PRIOR_ART
    assert result.blocked_by_rejected_prior_art


def test_prior_art_fingerprint_and_order_are_stable() -> None:
    older = rejected_record()
    newer = replace(
        older,
        id=UUID("00000000-0000-0000-0000-000000000003"),
        hypothesis_id=UUID("00000000-0000-0000-0000-000000000004"),
        created_at=datetime(2021, 1, 1, tzinfo=UTC),
    )
    first = check_prior_art(signature(), [newer, older], CONFIGURATION)
    second = check_prior_art(signature(), [older, newer], CONFIGURATION)
    assert first == second
    assert first.fingerprint == second.fingerprint
