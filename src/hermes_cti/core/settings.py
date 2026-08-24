"""Typed runtime settings with YAML defaults and environment overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from hermes_cti import __version__


class Settings(BaseSettings):
    """Runtime settings.

    ``HERMES_<FIELD_NAME>`` environment variables take precedence over the
    optional YAML file when loaded with :func:`load_settings`.
    """

    model_config = SettingsConfigDict(
        env_prefix="HERMES_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Hermes CTI"
    app_version: str = __version__
    environment: str = "development"
    log_level: str = "INFO"
    database_url: SecretStr | None = None
    database_required: bool = True
    database_connect_timeout_seconds: float = 2.0
    database_pool_size: int = 5
    database_max_overflow: int = 0
    schedule_timezone: str = "UTC"
    schedule_hour: int = 2
    daily_run_stale_after_seconds: int = 86_400
    request_id_header: str = "X-Request-ID"
    max_concurrency: int = 5
    http_timeout_seconds: float = 30.0
    http_connect_timeout_seconds: float = 10.0
    http_read_timeout_seconds: float = 30.0
    http_write_timeout_seconds: float = 10.0
    http_pool_timeout_seconds: float = 10.0
    http_max_redirects: int = 5
    http_verify_tls: bool = True
    http_user_agent: str = (
        "CTI-Hermes/0.1.0 (+https://github.com/mrcoggsworth/threat-intel-agent)"
    )
    http_max_retries: int = 3
    http_retry_backoff_seconds: float = 0.5
    http_retry_max_delay_seconds: float = 30.0
    http_retry_jitter_seconds: float = 0.25
    max_response_bytes: int = 10_485_760
    portal_output_dir: str = "./portal"
    secret_key: SecretStr | None = None
    admin_token: SecretStr | None = None
    enrichment_enabled: bool = True
    enrichment_cache_ttl_seconds: int = 86_400
    enrichment_stale_if_error_seconds: int = 604_800
    provider_timeout_seconds: float = 20.0
    provider_max_retries: int = 2
    provider_max_response_bytes: int = 20_971_520
    provider_concurrency: int = 2
    cisa_kev_url: str = (
        "https://www.cisa.gov/sites/default/files/feeds/"
        "known_exploited_vulnerabilities.json"
    )
    epss_url: str = "https://api.first.org/data/v1/epss"
    nvd_url: str = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    nvd_api_key: SecretStr | None = None
    virustotal_enabled: bool = False
    virustotal_api_key: SecretStr | None = None
    virustotal_url: str = "https://www.virustotal.com/api/v3"
    otx_enabled: bool = False
    otx_api_key: SecretStr | None = None
    otx_url: str = "https://otx.alienvault.com/api/v1"
    abuseipdb_enabled: bool = False
    abuseipdb_api_key: SecretStr | None = None
    abuseipdb_url: str = "https://api.abuseipdb.com/api/v2"


def _default_config_path() -> Path:
    """Return the repository config path when running from a checkout."""

    current = Path.cwd() / "config" / "settings.yaml"
    if current.is_file():
        return current
    return Path(__file__).resolve().parents[3] / "config" / "settings.yaml"


def _yaml_values(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("settings YAML must contain a mapping")

    agent = loaded.get("agent", {})
    ingestion = loaded.get("ingestion", {})
    publisher = loaded.get("publisher", {})
    scheduler = loaded.get("scheduler", {})
    enrichment = loaded.get("enrichment", {})
    if not all(
        isinstance(section, dict)
        for section in (agent, ingestion, publisher, scheduler, enrichment)
    ):
        raise ValueError("settings YAML sections must contain mappings")
    return {
        "app_name": agent.get("name", "Hermes CTI"),
        "app_version": agent.get("version", __version__),
        "log_level": agent.get("log_level", "INFO"),
        "max_concurrency": agent.get("max_threads", 5),
        "http_timeout_seconds": ingestion.get("timeout_seconds", 30.0),
        "http_connect_timeout_seconds": ingestion.get("connect_timeout_seconds", 10.0),
        "http_read_timeout_seconds": ingestion.get("read_timeout_seconds", 30.0),
        "http_write_timeout_seconds": ingestion.get("write_timeout_seconds", 10.0),
        "http_pool_timeout_seconds": ingestion.get("pool_timeout_seconds", 10.0),
        "http_max_redirects": ingestion.get("max_redirects", 5),
        "http_verify_tls": ingestion.get("verify_tls", True),
        "http_user_agent": ingestion.get(
            "user_agent",
            "CTI-Hermes/0.1.0 (+https://github.com/mrcoggsworth/threat-intel-agent)",
        ),
        "http_max_retries": ingestion.get("max_retries", 3),
        "http_retry_backoff_seconds": ingestion.get("retry_backoff_seconds", 0.5),
        "http_retry_max_delay_seconds": ingestion.get("retry_max_delay_seconds", 30.0),
        "http_retry_jitter_seconds": ingestion.get("retry_jitter_seconds", 0.25),
        "portal_output_dir": publisher.get("portal_output_dir", "./portal"),
        "schedule_timezone": scheduler.get("timezone", "UTC"),
        "schedule_hour": scheduler.get("hour", 2),
        "daily_run_stale_after_seconds": scheduler.get("stale_after_seconds", 86_400),
        "enrichment_enabled": enrichment.get("enabled", True),
        "enrichment_cache_ttl_seconds": enrichment.get("cache_ttl_seconds", 86_400),
        "enrichment_stale_if_error_seconds": enrichment.get(
            "stale_if_error_seconds", 604_800
        ),
        "provider_timeout_seconds": enrichment.get("timeout_seconds", 20.0),
        "provider_max_retries": enrichment.get("max_retries", 2),
        "provider_max_response_bytes": enrichment.get("max_response_bytes", 20_971_520),
        "provider_concurrency": enrichment.get("concurrency", 2),
        "cisa_kev_url": enrichment.get(
            "cisa_kev_url",
            "https://www.cisa.gov/sites/default/files/feeds/"
            "known_exploited_vulnerabilities.json",
        ),
        "epss_url": enrichment.get("epss_url", "https://api.first.org/data/v1/epss"),
        "nvd_url": enrichment.get(
            "nvd_url", "https://services.nvd.nist.gov/rest/json/cves/2.0"
        ),
        "virustotal_enabled": enrichment.get("virustotal_enabled", False),
        "virustotal_url": enrichment.get(
            "virustotal_url", "https://www.virustotal.com/api/v3"
        ),
        "otx_enabled": enrichment.get("otx_enabled", False),
        "otx_url": enrichment.get("otx_url", "https://otx.alienvault.com/api/v1"),
        "abuseipdb_enabled": enrichment.get("abuseipdb_enabled", False),
        "abuseipdb_url": enrichment.get(
            "abuseipdb_url", "https://api.abuseipdb.com/api/v2"
        ),
    }


def load_settings(config_path: Path | None = None) -> Settings:
    """Load YAML defaults and overlay explicitly supplied environment values."""

    path_value = os.getenv("HERMES_CONFIG_FILE")
    if config_path is not None:
        path = config_path
    elif path_value:
        path = Path(path_value)
    else:
        path = _default_config_path()
    values = _yaml_values(path)
    for field_name in Settings.model_fields:
        env_name = f"HERMES_{field_name.upper()}"
        if env_name in os.environ:
            values[field_name] = os.environ[env_name]
    return Settings.model_validate(values)
