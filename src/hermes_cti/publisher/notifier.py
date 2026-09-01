"""Multi-platform webhook notifiers and async webhook dispatcher for threat alerts.

Formats and dispatches threat alerts to:
- Slack (Block Kit)
- Microsoft Teams (Adaptive Cards)
- Discord (Embeds)
- Generic JSON webhooks
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

from hermes_cti.models.contracts import Severity
from hermes_cti.reporting.contracts import ReportBundle

# Severity color mapping (Hex, Teams Theme, and Discord Decimal)
SEVERITY_COLORS = {
    Severity.CRITICAL: {
        "hex": "#e11d48",
        "teams": "D32F2F",
        "discord": 14753096,
        "label": "CRITICAL",
        "emoji": "🚨",
    },
    Severity.HIGH: {
        "hex": "#ea580c",
        "teams": "E65100",
        "discord": 15358092,
        "label": "HIGH",
        "emoji": "⚠️",
    },
    Severity.MEDIUM: {
        "hex": "#0284c7",
        "teams": "1976D2",
        "discord": 165063,
        "label": "MEDIUM",
        "emoji": "ℹ️",
    },
    Severity.LOW: {
        "hex": "#059669",
        "teams": "388E3C",
        "discord": 366185,
        "label": "LOW",
        "emoji": "✅",
    },
    Severity.INFO: {
        "hex": "#64748b",
        "teams": "757575",
        "discord": 6583435,
        "label": "INFO",
        "emoji": "🔔",
    },
}


def _extract_report_fields(
    bundle: Any,
) -> tuple[str, str, Any, float, list[str], list[str], list[str]]:
    """Helper to extract common report attributes from bundle, model, or dict."""
    headline = getattr(bundle, "headline", "") or ""
    summary = (
        getattr(bundle, "executive_summary", "") or getattr(bundle, "summary", "") or ""
    )
    severity = getattr(bundle, "severity", "medium")
    confidence = float(getattr(bundle, "confidence", 0.9))

    cves: list[str] = []
    if hasattr(bundle, "vulnerabilities") and bundle.vulnerabilities:
        cves = [
            v.cve_id if hasattr(v, "cve_id") else str(v) for v in bundle.vulnerabilities
        ]
    elif hasattr(bundle, "primary_cves") and bundle.primary_cves:
        cves = list(bundle.primary_cves)

    iocs: list[str] = []
    if hasattr(bundle, "iocs") and bundle.iocs:
        iocs = [
            i.display_value if hasattr(i, "display_value") else str(i)
            for i in bundle.iocs
        ]

    techniques: list[str] = []
    if hasattr(bundle, "attack_mappings") and bundle.attack_mappings:
        techniques = [
            t.attack_id if hasattr(t, "attack_id") else str(t)
            for t in bundle.attack_mappings
        ]
    elif hasattr(bundle, "attack_techniques") and bundle.attack_techniques:
        techniques = list(bundle.attack_techniques)

    return headline, summary, severity, confidence, cves, iocs, techniques


class SlackNotifier:
    """Slack Block Kit payload builder."""

    def build_payload(
        self,
        headline: str,
        summary: str,
        severity: Severity | str,
        confidence: float,
        report_url: str | None = None,
        cves: list[str] | None = None,
        iocs: list[str] | None = None,
        techniques: list[str] | None = None,
    ) -> dict[str, Any]:
        sev = Severity(severity.lower()) if isinstance(severity, str) else severity
        sev_meta = SEVERITY_COLORS.get(
            sev, {"hex": "#0284c7", "label": str(sev).upper(), "emoji": "🚨"}
        )
        conf_pct = (
            f"{int(confidence * 100)}%" if confidence <= 1.0 else f"{int(confidence)}%"
        )

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": (
                        f"{sev_meta['emoji']} Hermes Threat Alert: {headline[:140]}"
                    ),
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Severity:* `{sev_meta['label']}`  |  "
                        f"*Confidence:* `{conf_pct}`"
                    ),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Executive Summary*\n{summary}",
                },
            },
        ]

        fields: list[dict[str, Any]] = []
        if cves:
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*CVEs:*\n{', '.join(cves[:5])}",
                }
            )
        if techniques:
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*MITRE ATT&CK:*\n{', '.join(techniques[:5])}",
                }
            )
        if iocs:
            ioc_str = ", ".join(f"`{ioc}`" for ioc in iocs[:5])
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*Sample IOCs:*\n{ioc_str}",
                }
            )

        if fields:
            blocks.append(
                {
                    "type": "section",
                    "fields": fields[:10],
                }
            )

        if report_url:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "View Full Report & Playbook",
                                "emoji": True,
                            },
                            "url": report_url,
                            "style": (
                                "primary"
                                if sev in {Severity.CRITICAL, Severity.HIGH}
                                else "default"
                            ),
                        }
                    ],
                }
            )

        return {"blocks": blocks}

    @staticmethod
    def format_block_kit(
        title: str,
        summary: str,
        severity: str,
        report_url: str = "",
    ) -> dict[str, Any]:
        """Legacy helper matching format_block_kit."""
        notifier = SlackNotifier()
        return notifier.build_payload(
            headline=title,
            summary=summary,
            severity=severity,
            confidence=0.9,
            report_url=report_url or None,
        )

    def build_payload_from_report(
        self, bundle: Any, report_url: str | None = None
    ) -> dict[str, Any]:
        headline, summary, severity, confidence, cves, iocs, techniques = (
            _extract_report_fields(bundle)
        )
        return self.build_payload(
            headline=headline,
            summary=summary,
            severity=severity,
            confidence=confidence,
            report_url=report_url,
            cves=cves,
            iocs=iocs,
            techniques=techniques,
        )


class TeamsNotifier:
    """Microsoft Teams Adaptive Card / MessageCard payload builder."""

    def build_payload(
        self,
        headline: str,
        summary: str,
        severity: Severity | str,
        confidence: float,
        report_url: str | None = None,
        cves: list[str] | None = None,
        iocs: list[str] | None = None,
        techniques: list[str] | None = None,
    ) -> dict[str, Any]:
        sev = Severity(severity.lower()) if isinstance(severity, str) else severity
        sev_meta = SEVERITY_COLORS.get(
            sev, {"teams": "1976D2", "label": str(sev).upper(), "emoji": "🚨"}
        )
        conf_pct = (
            f"{int(confidence * 100)}%" if confidence <= 1.0 else f"{int(confidence)}%"
        )

        facts: list[dict[str, str]] = [
            {"title": "Severity", "value": str(sev_meta["label"])},
            {"title": "Confidence", "value": conf_pct},
        ]
        if cves:
            facts.append({"title": "CVEs", "value": ", ".join(cves[:5])})
        if techniques:
            facts.append({"title": "MITRE ATT&CK", "value": ", ".join(techniques[:5])})
        if iocs:
            facts.append({"title": "Sample IOCs", "value": ", ".join(iocs[:5])})

        body: list[dict[str, Any]] = [
            {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "text": f"{sev_meta['emoji']} Hermes Threat Alert: {headline[:140]}",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": summary,
                "wrap": True,
            },
            {
                "type": "FactSet",
                "facts": facts,
            },
        ]

        actions: list[dict[str, Any]] = []
        if report_url:
            actions.append(
                {
                    "type": "Action.OpenUrl",
                    "title": "View Full Report & Playbook",
                    "url": report_url,
                }
            )

        card: dict[str, Any] = {
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": body,
        }
        if actions:
            card["actions"] = actions

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }

    @staticmethod
    def format_card(
        title: str,
        summary: str,
        severity: str,
        facts: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Legacy connector card formatter."""
        theme_color = SEVERITY_COLORS.get(
            (
                Severity(severity.lower())
                if severity.lower() in Severity._value2member_map_
                else Severity.INFO
            ),
            {"teams": "1976D2"},
        )["teams"]

        sections: list[dict[str, Any]] = [
            {
                "activityTitle": f"CTI Alert: {title}",
                "activitySubtitle": f"Severity: {severity.upper()}",
                "text": summary,
                "facts": facts or [],
                "markdown": True,
            }
        ]

        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": theme_color,
            "summary": f"CTI Alert: {title}",
            "sections": sections,
        }

    def build_payload_from_report(
        self, bundle: Any, report_url: str | None = None
    ) -> dict[str, Any]:
        headline, summary, severity, confidence, cves, iocs, techniques = (
            _extract_report_fields(bundle)
        )
        return self.build_payload(
            headline=headline,
            summary=summary,
            severity=severity,
            confidence=confidence,
            report_url=report_url,
            cves=cves,
            iocs=iocs,
            techniques=techniques,
        )


class DiscordNotifier:
    """Discord Embed payload builder."""

    def build_payload(
        self,
        headline: str,
        summary: str,
        severity: Severity | str,
        confidence: float,
        report_url: str | None = None,
        cves: list[str] | None = None,
        iocs: list[str] | None = None,
        techniques: list[str] | None = None,
    ) -> dict[str, Any]:
        sev = Severity(severity.lower()) if isinstance(severity, str) else severity
        sev_meta = SEVERITY_COLORS.get(
            sev, {"discord": 165063, "label": str(sev).upper(), "emoji": "🚨"}
        )
        conf_pct = (
            f"{int(confidence * 100)}%" if confidence <= 1.0 else f"{int(confidence)}%"
        )

        fields: list[dict[str, Any]] = [
            {"name": "Severity", "value": sev_meta["label"], "inline": True},
            {"name": "Confidence", "value": conf_pct, "inline": True},
        ]
        if cves:
            fields.append(
                {"name": "CVEs", "value": ", ".join(cves[:5]), "inline": False}
            )
        if techniques:
            fields.append(
                {
                    "name": "MITRE ATT&CK",
                    "value": ", ".join(techniques[:5]),
                    "inline": False,
                }
            )
        if iocs:
            fields.append(
                {
                    "name": "Sample IOCs",
                    "value": "\n".join(f"`{ioc}`" for ioc in iocs[:5]),
                    "inline": False,
                }
            )

        embed: dict[str, Any] = {
            "title": f"{sev_meta['emoji']} Hermes Threat Alert: {headline[:250]}",
            "description": summary[:2000],
            "color": sev_meta["discord"],
            "fields": fields,
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "footer": {"text": "CTI-Hermes Autonomous Threat Intelligence"},
        }
        if report_url:
            embed["url"] = report_url

        return {
            "username": "Hermes CTI",
            "embeds": [embed],
        }

    @staticmethod
    def format_embed(
        title: str,
        summary: str,
        severity: str,
        iocs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Legacy discord embed formatter."""
        notifier = DiscordNotifier()
        return notifier.build_payload(
            headline=title,
            summary=summary,
            severity=severity,
            confidence=0.9,
            iocs=iocs,
        )

    def build_payload_from_report(
        self, bundle: Any, report_url: str | None = None
    ) -> dict[str, Any]:
        headline, summary, severity, confidence, cves, iocs, techniques = (
            _extract_report_fields(bundle)
        )
        return self.build_payload(
            headline=headline,
            summary=summary,
            severity=severity,
            confidence=confidence,
            report_url=report_url,
            cves=cves,
            iocs=iocs,
            techniques=techniques,
        )


class WebhookDispatcher:
    """Dispatches async HTTP POST requests to webhooks with rate limiting."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        http_client: httpx.AsyncClient | None = None,
        rate_limit_delay: float = 0.0,
        timeout: float = 10.0,
    ) -> None:
        self._client = client or http_client
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout

    async def dispatch(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> bool:
        """Send webhook POST payload and verify status code 2xx."""
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)

        req_timeout = timeout if timeout is not None else self.timeout

        # Rate limiting delay
        if self.rate_limit_delay > 0:
            await asyncio.sleep(self.rate_limit_delay)

        if self._client is not None:
            response = await self._client.post(
                url, json=payload, headers=req_headers, timeout=req_timeout
            )
            return 200 <= response.status_code < 300

        async with httpx.AsyncClient(timeout=req_timeout) as client:
            response = await client.post(url, json=payload, headers=req_headers)
            return 200 <= response.status_code < 300


class ThreatNotifier:
    """Unified notifier facade managing Slack, Teams, Discord, and Webhooks."""

    def __init__(
        self,
        slack_notifier: SlackNotifier | None = None,
        teams_notifier: TeamsNotifier | None = None,
        discord_notifier: DiscordNotifier | None = None,
        dispatcher: WebhookDispatcher | None = None,
    ) -> None:
        self.slack = slack_notifier or SlackNotifier()
        self.teams = teams_notifier or TeamsNotifier()
        self.discord = discord_notifier or DiscordNotifier()
        self.dispatcher = dispatcher or WebhookDispatcher()

    async def notify_slack(
        self, webhook_url: str, bundle: ReportBundle, report_url: str | None = None
    ) -> bool:
        payload = self.slack.build_payload_from_report(bundle, report_url=report_url)
        return await self.dispatcher.dispatch(webhook_url, payload)

    async def notify_teams(
        self, webhook_url: str, bundle: ReportBundle, report_url: str | None = None
    ) -> bool:
        payload = self.teams.build_payload_from_report(bundle, report_url=report_url)
        return await self.dispatcher.dispatch(webhook_url, payload)

    async def notify_discord(
        self, webhook_url: str, bundle: ReportBundle, report_url: str | None = None
    ) -> bool:
        payload = self.discord.build_payload_from_report(bundle, report_url=report_url)
        return await self.dispatcher.dispatch(webhook_url, payload)

    async def notify_generic_webhook(
        self,
        webhook_url: str,
        bundle: ReportBundle,
        extra_data: dict[str, Any] | None = None,
    ) -> bool:
        payload: dict[str, Any] = (
            bundle.model_dump(mode="json")
            if hasattr(bundle, "model_dump")
            else dict(bundle)
        )
        if extra_data:
            payload["extra"] = extra_data
        return await self.dispatcher.dispatch(webhook_url, payload)
