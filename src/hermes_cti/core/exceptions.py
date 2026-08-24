"""Explicit application exception hierarchy."""


class HermesError(Exception):
    """Base class for expected CTI-Hermes application failures."""


class ConfigurationError(HermesError):
    """Raised when required application configuration is missing or invalid."""


class DependencyUnavailableError(HermesError):
    """Raised when a required runtime dependency cannot be reached."""


class ReadinessError(HermesError):
    """Raised when the service cannot safely accept work."""


class CLIError(HermesError):
    """Raised for an expected command-line operation failure."""
