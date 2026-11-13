# 0002: Preserve active project environment precedence

Date: 2026-11-10

Status: accepted PATH requirement; implementation not yet approved.

## Context

Restoring personal-bin priority after system/Homebrew startup must not displace
an intentionally activated project environment.

## Decision

Active project environment executables take precedence over personal executables.
Personal executables, including manually managed Copilot, take precedence over
Homebrew/system copies.

[Decision 0003](0003-preserve-caller-path-overrides.md) extends this precedence
requirement to arbitrary caller-prepended overrides, not just recognized project
environments.

[Decision 0004](0004-default-path-ordering.md) subsequently defines the default
category order and placement of version-managed runtimes and user tools. This
decision does not require globally sorting PATH or removing unrelated inherited
entries.

## Consequences

A fix that simply prepends `~/.local/bin` in every shell is insufficient.
Startup verification must include an inherited active project environment as
well as the personal-versus-Homebrew Copilot lookup.

## Source

User selection in the originating conversation:
"Active project environment before personal executables (recommended)".
