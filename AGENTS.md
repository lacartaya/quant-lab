# Quant Lab repository guidance

Quant Lab separates deterministic quantitative domain code from applications,
infrastructure, and AI functionality.

- Put domain code in `quant/`. It must not depend on application frameworks,
  databases, broker SDKs, market-data SDKs, or AI provider SDKs.
- Put application entry points in `apps/`, AI functionality in `agents/`, and
  deployment or operational assets in `infra/`.
- Keep experiments in `experiments/`; production code must not depend on them.
- Prefer small, explicit additions over speculative abstractions.
- Run `ruff check .`, `mypy .`, and `pytest` before completing changes.
