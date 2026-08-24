---
name: test-ci-diagnosis
description: Diagnose failures with focused reproduction and regression evidence.
---

# Test and CI diagnosis

Reproduce with the smallest deterministic command. Add a failing test or
fixture before changing behavior, preserve the failure output without secrets,
then run relevant formatting, lint, typing, unit/integration, contract, build,
and CI checks. Report unavailable tools explicitly.
