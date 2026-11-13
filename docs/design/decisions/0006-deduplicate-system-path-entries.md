# 0006: Deduplicate system-provided PATH entries

Date: 2026-11-11

Status: accepted behavioral requirement; implementation not yet approved.

## Context

The pinned macOS baseline can contribute a system PATH entry that is also
inserted by user startup initialization. Keeping both copies causes the same
executable directory to appear more than once in a fresh shell. Decision 0004
establishes PATH precedence but left duplicate handling open.

## Decision

Deduplicate identical system-provided PATH entries rather than preserving
repeated copies. Retain the first occurrence so the relative order of distinct
entries remains stable. Caller-prepended overrides continue to retain precedence
as required by [decision 0003](0003-preserve-caller-path-overrides.md).

## Consequences

- The same PATH directory is represented once even if system startup and user
  initialization both provide it.
- Deduplication must not displace caller-prepended overrides or reorder distinct
  system entries.
- This decision does not define canonicalization of equivalent filesystem paths,
  treatment of empty or relative PATH components, or behavior for missing
  directories.
- This approves behavior, not an implementation or changes to system startup
  files.

## Source

User statement in the originating conversation, 2026-11-11:
"Yes, deduplicate the system provided paths."
