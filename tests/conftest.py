"""Shared pytest fixtures for the repository suite.

The ephemeral PostgreSQL fixtures are owned by the Phase 4 persistence suite;
they are re-exported here so later suites (candidate ledger, publication
gating) consume them as fixtures instead of importing symbols and shadowing
parameter names.
"""

from __future__ import annotations

from tests.test_phase4 import (  # noqa: F401
    database,
    postgres_settings,
)
