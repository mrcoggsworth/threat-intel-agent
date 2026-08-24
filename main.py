"""Compatibility wrapper for the former repository-root entrypoint.

Use ``hermes-cti`` or the declared package entrypoints for new invocations.
"""

from hermes_cti.cli.main import run

if __name__ == "__main__":
    run()
