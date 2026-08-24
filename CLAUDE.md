# CLAUDE.md - Project Conventions for Claude Agent

## Environment Setup & Build Commands

- **Python Version:** Python 3.12+
- **Package Management:** `uv` with committed `uv.lock`
- **Install Dependencies:** `uv sync --frozen`
- **Run API:** `uv run hermes-cti-api`
- **Run CLI:** `uv run hermes-cti version`, `doctor`, or `sources validate`
- **Run Tests:** `uv run pytest`

## Code Style & Guidelines

- Use explicit type annotations for function signatures.
- Use Pydantic contracts for data exchanged between pipeline boundaries.
- Keep source configuration validation offline and deterministic. Keep ingestion tests transport-mocked and free of live internet access.
- Keep Phase 2 free of database tables, provider credentials,
  and scoring formulas. Phase 5 provider credentials remain runtime-only and
  enrichment tests use mocked transports without live internet.
