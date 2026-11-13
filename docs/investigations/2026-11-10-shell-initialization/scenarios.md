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
| S09-env-c | Fresh `BASH_ENV=file bash -c …` | Silent sentinel executes; no standard user startup |
| S09-env-script | Fresh `BASH_ENV=file bash "probe script.bash" …` | Real script argv, sentinel executes once before the probe; no wrapper Bash |
| S09-env-login-c | Fresh `BASH_ENV=file bash -l -c …` | Login files precede sentinel; sentinel captures sourced exports/local state |
| S09-env-interactive | Fresh `BASH_ENV=file bash -i -c …` | Sentinel ignored; normal interactive rc |
| S09-env-inherited-c | Login parent → `BASH_ENV=file bash -c …` | Child inherits exports, runs sentinel, does not inherit ordinary functions |
| S10-noprofile-i | Fresh `bash --noprofile -i -l -c …` | No automatic profiles or ordinary user rc; no tracked interactive modules |
| S10-noprofile-env | Fresh `BASH_ENV=file bash --noprofile -l -c …` | Sentinel still runs; no profile exports/PATH initialization |
| S11-norc-i | Fresh `bash --norc -i -c …` | No ordinary user rc or tracked interactive modules |
| S11-norc-login | Fresh `bash --norc -i -l -c …` | Login profile still explicitly sources `.bashrc`; tracked exports and interactive modules load |
| S12-rcfile-i | Fresh `bash --rcfile file -i -c …` | Only alternative user rc selected; tracked interactive modules absent |
| S12-rcfile-login | Fresh `bash --rcfile file -i -l -c …` | Alternative rc ignored; profile may explicitly source ordinary `.bashrc` |
| S12-norc-rcfile | Fresh `bash --norc --rcfile file -i -c …` | `--norc` takes precedence; neither automatic user rc runs |
| SSH-login | Modeled interactive SSH login | Pending: no sshd transport |
| SSH-cmd | Modeled SSH remote command | Shell mode and expectations pending; no sshd transport |
| SSH-tty | Modeled SSH pseudo-terminal command | Shell mode and expectations pending; no sshd transport |

S04-S06 should cover both login and non-login children. S08 distinguishes
inherited and fresh non-interactive launches, login from non-login, and an
explicit non-interactive source of `.bashrc`. Unsolicited dotfiles output is
compared against a matched system-only control. Exact environment-loading
expectations for remote commands remain open.

S09–S12 are invocation variations, not measured application or terminal sessions.
They run across every existing configuration axis in both suites, extending the
fixture inputs described by decision 0008 without revising that published ADR.
The Bash suite retains standard startup-file markers; the dotfiles suite retains
real tracked modules and system providers. Named BASH_ENV/rcfile inputs are
silent, synthetic, fixture-owned files with spaces in their paths, not module
or system-file replacements. Controls receive equivalent invocation inputs.
Probe records retain sentinel markers and the state seen before its execution.
Additional Bash cases prove explicit profile-to-rc dispatch under both `--norc`
and login `--rcfile`; the 16 combinations determine whether a profile and rc
are present. No syntax-only invocation is a scenario.

S05–S07 PATH launch steps, SSH transport, and PTY-backed interaction remain
deferred. Interactive command probes do not exercise prompt rendering, keyboard
bindings, or terminal job control. See the [harness coverage limits and
verification evidence](../../../tests/shell/README.md).

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
