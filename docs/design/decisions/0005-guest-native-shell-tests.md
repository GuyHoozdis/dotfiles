# 0005: Guest-native shell tests with local Tart orchestration

Date: 2026-11-11

Status: accepted harness architecture; implementation plan pending review.

## Decision

Run pytest/uv HOME fixtures inside disposable real-OS guests. Use a thin local
Tart driver for clone, boot, guest-agent execution, source transfer, artifact
retrieval, and cleanup. Keep scenario assertions independent of Tart so future
GitHub-hosted jobs can invoke them directly.

Start with the recorded macOS Bash 3.2 and Ubuntu Bash 5.2 baselines. Implement
S01-S04 first, with characterization distinct from failing policy acceptance.
The harness must not repair PATH or weaken approved expectations.

## Rationale

Both [macOS](../../investigations/2026-11-10-shell-initialization/tart-experiment.md)
and [Ubuntu](../../investigations/2026-11-10-shell-initialization/tart-ubuntu-experiment.md)
experiments established direct guest-agent execution and disposable-clone reset.
Real system startup avoids a simulation of the behavior under investigation.
Cirrus CLI and Testcontainers add no demonstrated benefit to this increment.

## Boundaries

No production startup fix, XDG migration, package-management redesign, or Actions
workflow is approved by this decision. Preserve stopped baselines and caches;
never mount the live HOME, forward credentials, or prune unrelated VMs.

The [approved harness design](../../investigations/2026-11-10-shell-initialization/fixture-harness-design.md)
defines details and the unresolved startup-policy boundaries.

## Source

The user selected: "Approve the design and prepare the implementation plan".
