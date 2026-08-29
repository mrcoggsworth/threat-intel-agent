---
name: python-dev-workflow
description: Procedures, type-safety rules, linting standards, and CI verification workflows for Python, FastAPI, SQLAlchemy, and frontend development tasks in CTI-Hermes.
---

# Python Development & CI Verification Standards

Use this skill when developing, refactoring, or reviewing Python code, SQLAlchemy models, Pydantic contracts, Alembic migrations, or Web UI components in this repository.

---

## 1. Type Annotations & Mypy Strict Compliance

### Fully Parameterize Generic Types
In Python 3.9+, never use bare collection types like `dict` or `list` in type annotations:
```python
# ❌ Incorrect (fails mypy)
typed_queries: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)

# ✅ Correct (fully parameterized)
from typing import Any

typed_queries: Mapped[list[dict[str, Any]]] = mapped_column(
    JSONB, default=list, nullable=False
)
```

### Future Annotations & Tuples in Contracts
* Include `from __future__ import annotations` at the top of every module.
* Prefer immutable `tuple[...]` over `list[...]` in Pydantic domain contracts.
* Always specify types for dictionary keys and values (e.g., `dict[str, Any]`, `dict[str, str]`).

---

## 2. Pydantic Domain Contracts & Backwards Compatibility

When extending or enriching contracts (e.g. `ThreatHunt`, `ReportBundle`):
1. **Never break existing consumers**: All new fields must have default values (`default=()`, `default=None`, `default_factory=...`).
2. **Preserve summary fields**: If adding structured deep-dive models (e.g., `execution_phases: tuple[HuntPhase, ...]`), keep the summary field (e.g., `procedure: tuple[str, ...]`) populated for summary renderers, CLI outputs, and modals.
3. **Export from `__init__.py`**: When creating new models, add them to `__all__` in `src/hermes_cti/models/__init__.py`.

---

## 3. Database Models & Alembic Migrations

When modifying database models in `src/hermes_cti/db/models.py`:
1. **Match JSONB Typing**: Use `Mapped[list[dict[str, Any]]]` or `Mapped[dict[str, Any]]` for arbitrary structured JSONB fields.
2. **Create Migration Script**:
   * Add a new file in `alembic/versions/` named sequentially (e.g., `0014_in_depth_threat_hunt_playbooks.py`).
   * Set `revision` and `down_revision` properly.
   * Use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ... JSONB NOT NULL DEFAULT '[]'::jsonb`.
   * Implement both `upgrade()` and `downgrade()`.
3. **Repository Persistence Layer (`repository.py`)**:
   * Serialize sub-models with `.model_dump(mode="json")` when storing Pydantic objects into SQLAlchemy JSONB columns.

---

## 4. Linting & Formatting Standards (Ruff)

### Line Length Constraints (88 chars)
Break long string literals across multiple lines using parentheses:
```python
# ❌ Incorrect (exceeds 88 characters)
query = "DeviceProcessEvents | where FileName =~ 'rundll32.exe' and ProcessCommandLine has 'setup.dll'"

# ✅ Correct
query = (
    "DeviceProcessEvents | where FileName =~ 'rundll32.exe' "
    "and ProcessCommandLine has 'setup.dll'"
)
```

### Unused Imports & Cleanliness
* Remove unused imports and variables before committing.
* Never leave debug print statements or ad-hoc introspection scripts (`introspect_temp.py`).

---

## 5. Web UI & Asset Compilation

When modifying templates (`src/hermes_cti/portal/templates/`):
1. **Decouple Views**:
   * Keep modal partials (`partials/hunt_modal.html`, `partials/attack_modal.html`) compact and focused on rapid play-by-play triage.
   * Provide rich, multi-phase operational consoles on dedicated pages (`/reports/{slug}/hunt`).
2. **Rebuild CSS**:
   * Run `npm run build:css` after introducing new Tailwind classes to regenerate `src/hermes_cti/portal/static/portal.css`.
3. **Clipboard & Interactive Controls**:
   * Attach `data-copy-target` to copy buttons inside `.detection`, `.hunt-query-card`, or `[data-copy-container]`.

---

## 6. Mandatory Pre-Commit & Pre-Push Verification Checklist

Always run this full check sequence before committing and pushing code:

```bash
# 1. Format code with Ruff
.venv/bin/ruff format .

# 2. Check and auto-fix lints
.venv/bin/ruff check --fix .

# 3. Verify static type safety with mypy
.venv/bin/mypy src

# 4. Run test suite with pytest
.venv/bin/pytest

# 5. Build CSS assets (if HTML/CSS changed)
npm run build:css
```
