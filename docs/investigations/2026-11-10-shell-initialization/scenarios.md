# Startup scenarios and HOME fixture scope

Date: 2026-11-10

Status: scenario scope and guest-native harness architecture approved; the
shared executable definitions are in
[`tests/shell/scenarios.py`](../../../tests/shell/scenarios.py).
Pending cases below are registered but skipped until their launch steps or
transport exist.

## Scenario matrix

Apply the precedence requirements in decisions
[0003](../../design/decisions/0003-preserve-caller-path-overrides.md) and
[0004](../../design/decisions/0004-default-path-ordering.md).

| ID | Scenario | Expected behavior |
|----|----------|-------------------|
| S01 | Fresh interactive login shell | Approved default ordering |
| S02 | Nested interactive login shell | Same default precedence; startup introduces no additional occurrences of managed paths |
| S03 | Interactive non-login shell (`bash`) | Same PATH policy; prompt functions and aliases, including `codetree` and `jqless`, available in the new process |
| S04 | Caller prepends arbitrary directories | Overrides remain ahead of defaults, in caller order, without activation markers |
| S05 | Caller prepends a default-group directory | Explicit override wins over its default category placement; launch steps pending |
| S06 | Activated environment or runner-supplied PATH | Supplied precedence survives child-shell startup; launch steps pending |
| S07 | VS Code/Herdr-like inherited environment | Reinitialization preserves launcher additions and restores default precedence without displacing caller overrides; launch steps pending |
| S07-resolve | Modeled VS Code environment resolver (`-i -l -c`) | Interactive login state with `VSCODE_RESOLVING_ENVIRONMENT=1` |
| S08-c | Inherited non-interactive non-login child | Inherits environment; no interactive initialization or unsolicited dotfiles output |
| S08-login-c | Inherited non-interactive login child | Login environment loaded; no interactive initialization or unsolicited dotfiles output |
| S08-source-rc | Inherited non-interactive child explicitly sources `.bashrc` | No interactive initialization or unsolicited dotfiles output |
| S08-fresh-c | Fresh non-interactive non-login shell | No interactive initialization or unsolicited dotfiles output |
| S08-fresh-login-c | Fresh non-interactive login shell | Login environment loaded; no interactive initialization or unsolicited dotfiles output |
| S09-noexec | Fresh syntax-only check (`bash -n script.sh`) | Valid script exits 0 without output; invalid script reports a syntax error; neither the script nor `BASH_ENV` executes |
| SSH-login | Modeled interactive SSH login | Pending: no sshd transport |
| SSH-cmd | Modeled SSH remote command | Shell mode and expectations pending; no sshd transport |
| SSH-tty | Modeled SSH pseudo-terminal command | Shell mode and expectations pending; no sshd transport |

S04-S06 should cover both login and non-login children. S08 distinguishes
inherited and fresh non-interactive launches, login from non-login, and an
explicit non-interactive source of `.bashrc`. Unsolicited dotfiles output is
compared against a matched system-only control. Exact environment-loading
expectations for remote commands remain open.

S09 is the only syntax-only scenario. Every other scenario observes process
state through the shared `-c` probe; under `-n` no command runs, so S09
observes only exit status, raw output, and fixture sentinel files written by
the script and by a `BASH_ENV` script. It does not claim any shell state. An
ordinary run of the same valid script is the positive control proving both
sentinels can be written. See the
[harness README](../../../tests/shell/README.md#observation-kinds).

Also cover repeated sourcing, paths containing spaces, and missing optional
tools. Do not equate equivalent precedence with byte-for-byte identical PATHs.
Check actual command resolution with colliding fixture executables as well as
PATH contents.

## Proposed fixture architecture

Create temporary HOME directories and a controlled inherited environment for
each case. Supply synthetic executable directories for resolution checks; never
fetch packages during scenarios or source live local overrides. The revised
[harness proposal](fixture-harness-design.md) places acceptance inside disposable
real-OS guests, where installed Homebrew/version managers may run normally.

Maintain a distinction between:

- Characterization: capture the existing framework's behavior, including known
  failures. Do not silently bless that behavior as the acceptance contract.
- Acceptance: assert approved expectations against a candidate startup design.
- Integration: exercise actual platform startup separately from simulated
  startup mutations.

The harness must not repair PATH itself before assertions or replace the
framework with a successful test-only implementation.

## Isolation limits to address before creating fixtures

A temporary HOME is not a complete sandbox. Login Bash still reads
`/etc/profile`, and the framework can invoke Homebrew at absolute paths.
Do not run the live framework under a different HOME and assume it is isolated.

For host-only tests, a controlled dependency boundary would be required for
Homebrew/version-manager calls and system PATH mutation. The revised proposal
instead uses disposable guests without requiring that production change.
Reproducing `path_helper` and Homebrew ordering in a
fixture is a simulation, not verification of the full platform startup chain.
An actual macOS login integration check must identify its host dependencies and
must not modify `/etc/profile` or `/etc/paths*`.

Launcher simulations cannot verify the real VS Code/Herdr shell launch chain.
S07 may expose ambiguity between stale inherited order and caller intent. Report
that ambiguity rather than inventing provenance from PATH alone.

## Remaining fixture-design decisions

- Supported Bash versions and initial Linux targets.
- Harness runner, dependency-isolation mechanism, and integration-test boundary.
- Whether missing managed directories are omitted or retained.
- Whether pre-existing duplicates are normalized, and how empty/relative PATH
  entries are treated. The approved scope prohibits introducing new managed-path
  duplicates; it does not yet define global normalization.
- How caller intent survives system login mutations without classifying only
  recognized environment managers.
- Within-group order for multiple application directories.

These are not reasons to reopen approved precedence. They define the remaining
fixture and startup design work before implementation.
