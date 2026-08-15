import hashlib
import json
import math
from collections.abc import Sequence

from quant.domain import HypothesisStatus
from quant.domain.knowledge import (
    KnowledgeRecord,
    PriorArtCheckResult,
    PriorArtConfiguration,
    PriorArtDisposition,
    PriorArtMatch,
    PriorArtMatchType,
    ReconsiderationCondition,
    ResearchSignature,
)


def normalize_signature(value: ResearchSignature) -> dict[str, object]:
    return {
        "strategy_family": _text(value.strategy_family),
        "market": _text(value.market),
        "instrument": _text(value.instrument),
        "timeframe": _text(value.timeframe),
        "parameters": {key: value.parameters[key] for key in sorted(value.parameters)},
        "execution_model": _optional_text(value.execution_model),
        "cost_model": _optional_text(value.cost_model),
        "regime_scope": _optional_text(value.regime_scope),
    }


def research_fingerprint(value: ResearchSignature) -> str:
    return _fingerprint(normalize_signature(value))


def check_prior_art(
    candidate: ResearchSignature,
    records: Sequence[KnowledgeRecord],
    configuration: PriorArtConfiguration,
) -> PriorArtCheckResult:
    candidate_normalized = normalize_signature(candidate)
    candidate_hash = _fingerprint(candidate_normalized)
    matches: list[PriorArtMatch] = []
    for record in sorted(records, key=lambda item: (item.created_at, str(item.id))):
        match_type, evidence = _match(candidate, record.signature, configuration)
        if match_type is None:
            continue
        conditions_met = _conditions_met(record, candidate)
        if match_type is PriorArtMatchType.EXACT:
            disposition = PriorArtDisposition.DUPLICATE
        elif (
            record.status is HypothesisStatus.REJECTED
            and not conditions_met
            and match_type is PriorArtMatchType.SIMILAR_PARAMETERS
        ):
            disposition = PriorArtDisposition.REJECTED_PRIOR_ART
        elif record.status is HypothesisStatus.REJECTED and conditions_met:
            disposition = PriorArtDisposition.RECONSIDERATION_CONDITION_MET
        else:
            disposition = PriorArtDisposition.POTENTIAL_PRIOR_ART
        matches.append(
            PriorArtMatch(
                hypothesis_id=record.hypothesis_id,
                knowledge_record_id=record.id,
                match_type=match_type,
                disposition=disposition,
                similarity_evidence={
                    **evidence,
                    "conditions_met": [item.value for item in conditions_met],
                },
                status=record.status,
                reconsideration_conditions=record.reconsideration_conditions,
            )
        )
    material = {
        "candidate": candidate_normalized,
        "configuration": {
            "numeric_parameter_relative_tolerance": (
                configuration.numeric_parameter_relative_tolerance
            )
        },
        "matches": [
            {
                "hypothesis_id": str(item.hypothesis_id),
                "knowledge_record_id": str(item.knowledge_record_id),
                "match_type": item.match_type.value,
                "disposition": item.disposition.value,
                "evidence": dict(item.similarity_evidence),
            }
            for item in matches
        ],
    }
    return PriorArtCheckResult(
        candidate_hash, configuration, tuple(matches), _fingerprint(material)
    )


def _match(
    candidate: ResearchSignature,
    existing: ResearchSignature,
    configuration: PriorArtConfiguration,
) -> tuple[PriorArtMatchType | None, dict[str, object]]:
    candidate_normalized = normalize_signature(candidate)
    existing_normalized = normalize_signature(existing)
    if candidate_normalized == existing_normalized:
        return PriorArtMatchType.EXACT, {"identical_signature": True}
    same_family = _text(candidate.strategy_family) == _text(existing.strategy_family)
    if not same_family:
        return None, {}
    same_domain = all(
        _text(left) == _text(right)
        for left, right in (
            (candidate.market, existing.market),
            (candidate.instrument, existing.instrument),
            (candidate.timeframe, existing.timeframe),
        )
    )
    parameter_evidence = _parameter_similarity(candidate, existing, configuration)
    if same_domain and parameter_evidence["similar"]:
        return PriorArtMatchType.SIMILAR_PARAMETERS, {
            "same_domain": True,
            **parameter_evidence,
        }
    if same_domain:
        return PriorArtMatchType.SAME_DOMAIN, {
            "same_domain": True,
            **parameter_evidence,
        }
    return PriorArtMatchType.SAME_STRATEGY_FAMILY, {
        "same_domain": False,
        "same_market": _text(candidate.market) == _text(existing.market),
        "same_instrument": _text(candidate.instrument) == _text(existing.instrument),
        "same_timeframe": _text(candidate.timeframe) == _text(existing.timeframe),
    }


def _parameter_similarity(
    candidate: ResearchSignature,
    existing: ResearchSignature,
    configuration: PriorArtConfiguration,
) -> dict[str, object]:
    candidate_names = set(candidate.parameters)
    existing_names = set(existing.parameters)
    if candidate_names != existing_names:
        return {"similar": False, "same_parameter_names": False, "distances": {}}
    distances: dict[str, float] = {}
    similar = True
    for name in sorted(candidate_names):
        left, right = candidate.parameters[name], existing.parameters[name]
        if isinstance(left, bool) or isinstance(right, bool):
            close = left == right
        elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
            denominator = max(abs(float(left)), abs(float(right)), 1.0)
            distance = abs(float(left) - float(right)) / denominator
            distances[name] = distance
            close = (
                math.isfinite(distance)
                and distance <= configuration.numeric_parameter_relative_tolerance
            )
        else:
            close = left == right
        similar = similar and close
    return {"similar": similar, "same_parameter_names": True, "distances": distances}


def _conditions_met(
    record: KnowledgeRecord, candidate: ResearchSignature
) -> tuple[ReconsiderationCondition, ...]:
    existing = record.signature
    checks = {
        ReconsiderationCondition.NEW_MARKET: _text(candidate.market)
        != _text(existing.market),
        ReconsiderationCondition.NEW_TIMEFRAME: _text(candidate.timeframe)
        != _text(existing.timeframe),
        ReconsiderationCondition.NEW_EXECUTION_MODEL: _optional_text(
            candidate.execution_model
        )
        != _optional_text(existing.execution_model),
        ReconsiderationCondition.DIFFERENT_COST_MODEL: _optional_text(
            candidate.cost_model
        )
        != _optional_text(existing.cost_model),
        ReconsiderationCondition.DIFFERENT_REGIME_SCOPE: _optional_text(
            candidate.regime_scope
        )
        != _optional_text(existing.regime_scope),
        ReconsiderationCondition.MATERIALLY_NEW_STRATEGY_LOGIC: False,
        ReconsiderationCondition.MATERIALLY_NEW_EVIDENCE: False,
    }
    return tuple(
        condition
        for condition in record.reconsideration_conditions
        if checks[condition]
    )


def _text(value: str) -> str:
    return " ".join(value.casefold().split())


def _optional_text(value: str | None) -> str | None:
    return _text(value) if value is not None else None


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(encoded.encode()).hexdigest()
