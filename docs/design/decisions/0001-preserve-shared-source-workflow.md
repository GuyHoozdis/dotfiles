# 0001: Preserve the shared-source editing workflow

Date: 2026-11-10

Status: accepted requirement from the user's stated workflow; not approval of a
new implementation or management tool.

## Context

The current shared `main` branch and repository-backed symlinks already support
editing and synchronizing configuration effectively. `cddotfiles` makes returning
to the source checkout convenient. Selective deployment and startup correctness
are problems to address; replacing Git synchronization is not.

## Decision

Preserve the single shared-source workflow and the `cddotfiles` convention.
Treat direct editing through symlinks on fully deployed machines as a requirement
when evaluating alternatives. Keep partial/container deployment as a distinct
use case that need not clone and enable the complete workstation configuration.

## Consequences

XDG adoption does not require replacing Git or immediately adopting Stow.
Link-focused tools remain viable. Approaches based on rendered target copies
must explicitly justify their editing/apply tradeoff rather than assuming it is
an improvement. No installer, reset policy, PATH order, or migration layout is
selected by this decision.

## Source

User context in this investigation's originating conversation, 2026-11-10:
"I like my `cddotfiles` alias/convention. Between that and the symlinks I find it
easy to edit and push changes as needed and/or sync other machines."
