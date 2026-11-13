# 0008: Separate Bash and dotfiles suites over shared scenarios

Date: 2026-11-12

Status: accepted and implemented.

## Context

Bash's standard startup-file selection and the state produced by our dotfiles
are different questions. They need comparable coverage of the same shell
launches without treating observed behavior as the expected policy.

The user stated:

> “For as long as we have separated init files … I want the `dotfiles` test suite to validate that, for all defined scenarios, the resulting state is what was expected.”
>
> “The bash test suite should only use the standard init files and run the defined scenarios over the various combinations of those init files.”
>
> “Both test suites should share the scenario definitions and run all of the scenarios for all of the configurations they define.”

## Decision

Keep a shared [scenario registry](../../../tests/shell/scenarios.py). The Bash
suite characterizes standard startup-file combinations without the dotfiles;
the dotfiles suite checks expected state across tracked, synthetic-local, and
space-containing HOME configurations. Both parameterize all registered
scenarios. Scenarios without launch steps are explicitly skipped: S05–S07
await definitions, and the SSH scenarios await an sshd transport.

Use the guest-native boundary in [decision 0005](0005-guest-native-shell-tests.md):
run against real system startup in disposable macOS and Ubuntu guests.
Examples model shell launches rather than launching VS Code or SSH.

Confirmed expectations:

- E1: interactive children receive per-shell settings.
- E2: dotfiles add no output compared with a matched system-only control;
  retain raw output artifacts for diagnosis.
- E3: Homebrew availability is an image property: present on the pinned macOS
  image and absent on the pinned Ubuntu image.

## Alternatives

- One combined suite: obscures whether failures arise from Bash startup-file
  semantics or the dotfiles' expected state.
- Separate per-suite scenario lists: allows the suites' launch coverage to
  drift and makes comparison unreliable.

## Consequences

- Shared scenarios exercise both suites across their own configuration axes;
  pending scenarios remain visible as skips, not passing coverage.
- Guest system startup remains observable, while PTY-dependent behavior and
  actual application and SSH launch chains remain outside this scope.
- Acceptance keeps approved PATH policy visible even when it fails; see the
  [harness results](../../../tests/shell/README.md#baselines-and-current-results).
