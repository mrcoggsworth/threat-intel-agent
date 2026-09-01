"""Detection rule generation, validation, and hunt playbooks."""

from __future__ import annotations

from hermes_cti.playbooks.hunt_playbook import (
    HuntPlaybookGenerator,
    generate_hunt_playbook,
)
from hermes_cti.playbooks.rule_generator import (
    DetectionRuleBundle,
    RuleGenerator,
    generate_defender_kql,
    generate_elastic_kql,
    generate_sigma_rule,
    generate_splunk_spl,
    generate_yara_rule,
)
from hermes_cti.playbooks.validators import (
    RuleValidator,
    validate_sigma_rule,
    validate_yara_rule,
)

__all__ = [
    "DetectionRuleBundle",
    "HuntPlaybookGenerator",
    "RuleGenerator",
    "RuleValidator",
    "generate_defender_kql",
    "generate_elastic_kql",
    "generate_hunt_playbook",
    "generate_sigma_rule",
    "generate_splunk_spl",
    "generate_yara_rule",
    "validate_sigma_rule",
    "validate_yara_rule",
]
