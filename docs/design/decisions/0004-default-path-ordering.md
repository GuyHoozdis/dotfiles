# 0004: Default PATH ordering

Date: 2026-11-10

Status: accepted precedence requirement; implementation not yet approved.

## Decision

Use the following precedence, highest first. The listed within-group order for
groups 2-4 is also approved.

| Priority | Category | Entries, in order |
|----------|----------|-------------------|
| 1 | Caller-prepended overrides | Preserve the caller's relative order, including active environments and runner-provided paths |
| 2 | Persistent user-selected commands | `~/.local/bin`, `~/node_modules/.bin` |
| 3 | Version-managed runtimes | `~/.n/bin`, `~/.rbenv/shims`, `~/.pyenv/shims` |
| 4 | Other user-installed tools | `~/.go/bin`, `~/.bun/bin`, `~/.dotnet/tools` |
| 5 | Explicit application tools | For example, `~/.docker/bin`, Wireshark, and the .NET installation directory; not an exhaustive list or an approved within-group ordering |
| 6 | Homebrew | `<Homebrew prefix>/bin`, `<Homebrew prefix>/sbin` |
| 7 | Remaining inherited system and launcher paths | Preserve their relative order, including Apple/system interleaving |

Caller overrides take priority even when they reference a directory from a lower
group, as required by [decision 0003](0003-preserve-caller-path-overrides.md).
The table describes defaults, not a rule that moves an explicit caller override
back into its default category.

Home-directory notation above must become absolute paths, not literal `~`
entries. Do not permanently add command-runner caches to PATH.

## Rationale

User-selected persistent commands should outrank runtime-manager shims and
packaged defaults. The user's home Node manifest provides user-wide commands
through `~/node_modules/.bin`, serving the same policy role as Python tool
executables exposed in `~/.local/bin`.

Group `n`, rbenv, and pyenv by their role as version managers, regardless of
whether they use executable shims. Preserve the relative order of remaining
system paths rather than moving all Apple paths behind traditional Unix paths.

## Boundaries

This approves precedence only. It does not select the preservation mechanism,
duplicate policy, missing-directory policy, or implementation. It does not
instruct provisioning to install missing tools or globally sort every inherited
directory.

## Source

The user reviewed the complete proposed ordering and selected:
"Approve this ordering".
