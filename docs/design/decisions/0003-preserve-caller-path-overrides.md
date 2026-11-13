# 0003: Preserve caller-prepended PATH overrides

Date: 2026-11-10

Status: accepted behavioral requirement; implementation not yet approved.

## Context

[Decision 0002](0002-preserve-active-project-precedence.md) gives active project
environments priority over default personal tools. Recognizing only particular
environment managers would make explicit caller PATH changes behave differently
depending on whether the framework understood their origin.

## Decision

Preserve caller-prepended PATH overrides, in their supplied relative order, ahead
of the default dotfiles-managed PATH. Do not require recognized activation
variables, an environment-manager allowlist, or a declaration of project paths.
The caller controls which executables those overrides select.

For example:

```bash
PATH="$PWD/project/bin:$PATH" bash -l
```

The child must retain `project/bin` ahead of the default tools. The same principle
applies to an activated virtual environment and interactive non-login Bash.
This refines decision 0002 rather than limiting the behavior to project tools.

## Consequences and unresolved mechanism

- Tests must cover arbitrary caller-prepended directories without `VIRTUAL_ENV`
  or another recognized activation signal, including multiple directories whose
  relative order must remain unchanged.
- Reinitialization must not blindly prepend default directories over caller
  overrides, including overrides that reuse a default tool directory.
- This is a precedence contract, not a guarantee of byte-for-byte identical PATH
  strings or approval of a global deduplication policy.
- PATH alone does not distinguish an intentional override from stale launcher
  ordering. Additionally, `/etc/profile` can reorder PATH before the user's
  login file executes. How to preserve caller intent while repairing repeated
  initialization remains a design question; this decision does not claim that
  the original order can always be recovered from the resulting PATH alone.
- This does not approve an implementation or change system startup files.

## Source

User statement in the originating conversation, 2026-11-10:
"Preserve caller-prepended overrides."

The user identifies caller responsibility, flexibility/control, and the principle
of least surprise as the reasons for this choice.
