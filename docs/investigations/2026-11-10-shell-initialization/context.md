# Initial context: shell initialization

Captured on 2026-11-10. Repository observations refer to baseline commit `5ac3a0d`,
unless explicitly described as live-system metadata.

## Purpose and boundaries

Investigate the dotfiles shell initialization framework before jointly exploring
redesigns, evaluating alternatives, and deciding how to proceed.

- Keep the manually managed Copilot release symlink and
  `alias copilot='copilot --no-auto-update'` workflow.
- Do not update, uninstall, or otherwise change installed applications.
- The user intends to uninstall the Homebrew Copilot installation themselves,
  after initial evidence has been captured.
- Do not implement shell changes or select a redesign during this initial capture.
- Preserve unrelated changes in the original checkout.

## User-reported background

macOS terminal sessions normally start Bash as a login shell in this setup.
iTerm2 is configured to follow that behavior. The shell framework was designed
years ago around `.bash_login` as its entrypoint.

Starting another login shell from an existing initialized shell reruns startup
logic that constructs PATH. Some entries are duplicated or prepended again,
changing executable resolution order.

Reproduction supplied by the user:

1. Start a new Bash terminal session and confirm `SHLVL=1`.
2. Record PATH, one entry per line: `printf '%s\n' "${PATH//:/$'\n'}"`.
3. Run `bash -l` and confirm `SHLVL=2`.
4. Record PATH again and compare duplicates and ordering.

The SHLVL values describe this reported scenario, not a general rule for detecting
whether initialization should run.

## Herdr and Copilot symptom

The user installed the Herdr CLI, not the `-app` variant, and launched it from an
iTerm2 Bash session. A terminal inside Herdr reports `SHLVL=2`. Copilot launched
there no longer has the expected vi keybindings; `/vim` was unavailable, although
it was available outside Herdr.

There are two Copilot executable locations:

- `~/.local/bin/copilot`: manually managed release symlink, intended to take
  precedence.
- `/opt/homebrew/bin/copilot`: Homebrew-managed installation.

PATH reordering is a working explanation for selecting the unintended executable.
It is not yet a confirmed explanation for the missing `/vim` command.

### Prior-session handoff (not reverified here)

- Environment: macOS, Herdr 0.9.5.
- Herdr configuration normally lives at `~/.config/herdr/config.toml`;
  `HERDR_CONFIG_PATH` can override it.
- Herdr starts login shells by default on macOS, according to the handoff.
- Outside Herdr, `which -a copilot` found the personal executable before Homebrew.
- Both executables reportedly returned Copilot CLI 1.0.108 despite differently
  named installation directories.
- Executable resolution, actual version, PATH, and `COPILOT_HOME` inside Herdr
  were not verified.
- Reported Herdr Escape-key issues do not by themselves explain an unavailable
  `/vim` command.

Prior session: `f2bf2b93-37c3-4091-a1c8-756255191183`.
Prior working directory: `~/Development/shi-github/aiml-dev-infrastructure`.
Prior session state:
`~/.copilot/session-state/f2bf2b93-37c3-4091-a1c8-756255191183`.

## Initial repository observations

1. `etc/bash_login.bash` (since renamed to `etc/bash_profile.bash` and split by
   decision 0007), lines 61-67,
   sources modules from `~/.local/etc/bashrc.d` in this order:
   `exports`, `aliases`, `functions`, `app-config`, `prompt`.
   Each `.local.bash` override is sourced before its tracked counterpart.
   The loading loop has no repeat-initialization or interactive-shell guard.
   Interactive/login detection helpers exist earlier in the file but do not
   gate this loop.
2. [`etc/bashrc.d/exports.bash`](../../../etc/bashrc.d/exports.bash),
   lines 34-43, invokes Homebrew `shellenv` whenever this module is sourced.
   Its actual effect on an inherited PATH still needs to be measured.
3. In the same file, lines 57-74, pyenv, rbenv, and n initialization use
   environment-variable guards. Those guards and the tools' behavior need
   separate evaluation; not all PATH mutation has the same lifecycle.
4. Lines 78-96 check whether node modules, Bun, and personal bin directories
   already exist in PATH before prepending them. Presence alone does not restore
   intended precedence if an earlier startup step has moved another directory
   ahead of `~/.local/bin`.
5. Lines 122-123 unconditionally prepend `$GOPATH/bin`. Re-sourcing the module
   with that entry already present can introduce another copy.
6. [`etc/inputrc`](../../../etc/inputrc), lines 2-4, explicitly configures
   Readline vi mode. This is separate from verifying Copilot's own editor mode
   and `/vim` support.
7. The repository [README](../../../README.md) already lists macOS login
   terminal behavior and local-override sourcing order as unresolved topics.

These are static observations, not results from an instrumented nested-shell
reproduction.

## Read-only live-system observations

Metadata captured before any Homebrew uninstall:

| Item | Observed value |
|------|----------------|
| `~/.bash_login` | Symlink to `~/dotfiles/etc/bash_login.bash` |
| `~/dotfiles` | Symlink to `~/Development/guyhoozdis/dotfiles` |
| `~/.local/etc` | Symlink to `~/dotfiles/etc` |
| `~/.local/bin/copilot` | Symlink to `~/.local/lib/copilot-cli/1.0.103/copilot` |
| `/opt/homebrew/bin/copilot` | Symlink to `/opt/homebrew/Caskroom/copilot-cli/1.0.56/copilot` |
| `brew list --versions` | `herdr 0.9.5`; `copilot-cli 1.0.56` |

No `.bash_profile` or `.bashrc` entry was listed by the metadata check.
Directory names and Homebrew receipts do not prove the binaries' actual versions.
Neither Copilot executable was run during this capture; the prior 1.0.108 report
remains unverified.

The machine's `/etc/profile` invokes `/usr/libexec/path_helper -s` when available,
then sources `/etc/bashrc` for Bash. System startup therefore needs to be
considered alongside this repository's login initialization.

The live startup links still point at the original checkout, not this worktree.
Its `etc/bashrc.d/app-config.bash` has an existing uncommitted change switching the
Homebrew completion source to `etc/profile.d/bash_completion.sh`. That change and
untracked `share/` content were left untouched and were not copied into the new
worktree.

## Open questions for the next phase

- What is the complete startup chain for initial login, nested login,
  interactive non-login, and non-interactive shells?
- Which PATH changes come from macOS `path_helper`, Homebrew, tracked modules,
  and local overrides, and in what order?
- What exact precedence should be preserved for personal executables, version
  manager shims, project environments, and system/Homebrew tools?
- Which initialization belongs once per inherited environment, and which belongs
  in every interactive shell?
- How should local overrides and intentional environment resets behave?
- What executable, version, PATH, alias, and `COPILOT_HOME` does Copilot actually
  see inside Herdr?
- How can startup behavior be reproduced in isolation without sourcing live
  configuration or changing installed tools?

No redesign has been selected. Controlled reproduction and research belong to the
next collaborative phase.
