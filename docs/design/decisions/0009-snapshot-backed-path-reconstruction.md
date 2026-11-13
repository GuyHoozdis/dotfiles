# 0009: Snapshot-backed login PATH reconstruction

Date: 2026-11-12

Status: accepted and implemented; guest-verified and integrated after operator
review and approval on 2026-11-12.

## Context

[Decision 0003](0003-preserve-caller-path-overrides.md) requires caller
precedence, [0004](0004-default-path-ordering.md) orders defaults, and
[0006](0006-deduplicate-system-path-entries.md) requires identical system
duplicates to be removed. The previous initialization prepended Go after other
providers, duplicated Go on nested logins, displaced caller prefixes, and
duplicated Homebrew on the pinned macOS guest.

System login startup precedes the user's profile. macOS can move system and
Homebrew paths ahead of caller directories while leaving callers ahead of the
inherited home-tool block. PATH alone cannot universally recover provenance.

## Decision

Keep environment initialization login-only, as required by
[decision 0007](0007-split-bashrc-from-bash-profile.md). Capture the incoming
PATH before tool providers, then reconstruct it once after initialization:
supported callers, eligible home defaults in decision 0004 order, the active
Homebrew prefix's `bin` and `sbin`, then the remaining observed entries.

Export the exact final PATH as `_DOTFILES_PATH_BASELINE` and its producing HOME
as `_DOTFILES_PATH_HOME`. These private values are inherited state, not
activation signals callers must supply. Non-login children neither reconstruct
PATH nor refresh this snapshot.

Caller recovery requires a nonempty, same-HOME baseline with a unique, ordered
home-managed subsequence. Home-managed entries shared with the incoming PATH
must remain unique and ordered; removed defaults alone do not invalidate it.
The first baseline home-managed entry still present is the anchor. Retain
incoming entries before that anchor unless they are managed defaults or occur
in the baseline tail beginning at the anchor. This excludes known system paths
moved forward, retains surviving callers, and never promotes appended paths or
resurrects removed callers.

Missing, stale, inconsistent, reordered, or anchorless metadata uses the
no-baseline path: initialize defaults and preserve the remaining observed PATH
in order. This does not claim recovery of an unseen pre-login prefix.

Keep existing provisioning rules: personal, Node, and Bun directories are added
when present; Go remains unconditional; other home-managed defaults participate
only when already supplied by incoming PATH or real provider initialization.
Supplied directories remain even if they no longer exist. Discover Homebrew
through the existing executable branches, preferring `/usr/local` before
`/opt/homebrew`; only the active prefix is classified as managed.

Remove all identical managed defaults from the remainder, including active
Homebrew duplicates supplied by system startup. Remove only the recovered
caller occurrence counts already represented in the prefix. Preserve unknown
entries' order and multiplicity, missing directories, literal tildes, and empty
or relative components. Do not canonicalize paths or globally deduplicate.

## Alternatives

- Blind default prepending repairs some ordering but displaces callers and
  repeats entries on reinitialization.
- Membership-only snapshot subtraction treats novel appended paths as callers,
  incorrectly promoting them. The anchor bounds recovery to the prefix.
- Pre-login capture, launcher wrapping, environment-manager recognition, and
  system-file changes require broader design and are deferred.

## Consequences

- All four known failure categories are eliminated on both pinned guests.
  [Results and evidence](../../../tests/shell/README.md#baselines-and-current-results)
  include unchanged Bash semantics, non-login inheritance, quiet startup, and
  guest-only lifecycle and literal-component tests.
- This is a partial implementation of decision 0003, not universal provenance
  recovery. A caller reusing a managed or system directory may be
  indistinguishable from default ordering. Replaced/reordered PATHs, changed
  system providers, or launchers discarding private state need further design;
  unsupported metadata does not justify guessing provenance.
- Unclassified application/launcher entries remain in the inherited tail.
  Decision 0004's broader application-tool category is not implemented here.
- S05, S06, S07, actual IDE/SSH launches, PTY interaction, and live-HOME migration
  remain pending. No `SHLVL` inference, `bash` interception, or pre-login hook
  is introduced.
- Operational/provider errors remain visible; metadata fallback is not an
  error-suppression mechanism.

## Source and approval

The user selected this bounded mechanism on 2026-11-12:

> Use the private PATH snapshot for the four known failures; defer ambiguous overrides.

The [implementation plan](../../plans/2026-11-12-shell-path-policy/plan.md)
records its scope. The user separately required implementation in a parallel
worktree and operator review/approval before completion and integration into
`investigate-shell-initialization`. After reviewing the implementation worktree,
the user approved integration and cleanup on 2026-11-12:

> I reviewed the `implement-shell-path-policy` worktree and I think it is ready to use. Merge it back into the investigate-shell-initialization worktree and clean up the `implement-shell-path-policy` worktree/branch.
