# Shell initialization investigation

- [Initial context and observations](context.md)
- [Requirements and workstreams](requirements.md)
- [Reference repository and tool survey](reference-survey.md)
- [Approaches and smallest useful changes](options.md)
- [Open questions](open-questions.md)
- [Approved scenario scope and proposed HOME fixtures](scenarios.md)
- [HOME fixture harness proposal](fixture-harness-design.md)
- [Harness implementation plan](../../plans/2026-11-11-shell-fixture-harness/plan.md)
- [Shell startup harness: usage and current results](../../../tests/shell/README.md)
- [Execution environments: fixtures, hosted runners, and local VMs](execution-environments.md)
- [Local Tart macOS experiment and findings](tart-experiment.md)
- [Local Tart Ubuntu experiment and findings](tart-ubuntu-experiment.md)
- [Bash startup reference](../../reference/bash-startup.md)
- [macOS system and Apple Terminal startup synopsis](../../reference/macos-terminal-startup.md)
- [Confirmed constraints and decisions](../../design/decisions/README.md)

Status: The guest-native harness is implemented. Characterization passes on
the pinned macOS and Ubuntu baselines. Acceptance fails only on the expected
startup-policy assertions: managed order, duplicate Go entries in nested
logins, `exists_in_path` missing in interactive non-login children, and caller
paths displaced in login shells. macOS also duplicates `/opt/homebrew/bin`. See
the [harness README](../../../tests/shell/README.md). Production startup changes
remain unapproved and no shell initialization changes have been made. Remaining
policy questions are in [Open questions](open-questions.md).
