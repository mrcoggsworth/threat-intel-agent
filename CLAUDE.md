# CLAUDE.md - Project Conventions for Claude Agent

## Environment Setup & Build Commands
- **Python Version:** Python 3.12+
- **Package Management:** `uv`
- **Virtual Environment:** `uv venv` -> `source .venv/bin/activate`
- **Install Dependencies:** `uv pip install -r requirements.txt`
- **Run Agent:** `uv run main.py`
- **Run Tests:** `pytest`

## Code Style & Guidelines
- Use explicit type annotations for function signatures.
- Prefer dataclasses or Pydantic models for structured CTI data.
- Ensure all IOC regex matching handles obfuscated or defanged indicators (e.g. `192[.]168[.]1[.]1`, `example[.]com`).
