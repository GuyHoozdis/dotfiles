# Requirements and scope

Status: organized from the user's 2026-11-10 context; acceptance criteria below
are proposals, not an approved implementation specification.

## Existing workflow to preserve

One shared `main` branch already works across fully deployed macOS machines.
Cloning the repository and selectively symlinking configuration enables direct
editing, committing, pushing, and pulling. `cddotfiles` is a valued convention,
not a problem to replace. The tracked alias is at
`etc/bashrc.d/aliases.bash:84`.

Other targets consume only portions: VS Code devcontainers, Docker images,
temporary containers, and remote Linux/SSH environments. They should not need a
full workstation deployment merely to obtain Readline vi bindings and selected
shell configuration.

## Workstreams

| Workstream | Desired outcome | Scope boundary |
|------------|-----------------|----------------|
| Startup correctness | Predictable PATH and working interactive configuration in login and non-login Bash | Can be fixed without changing repository layout or choosing an installer |
| Portable configuration | Equivalent intended behavior on macOS and Unix-like targets | OS-specific commands and unsupported tools still require explicit adapters; initial Linux distributions and Bash versions are undecided |
| XDG migration | Separate configuration, data, state, and cache appropriately | Application support determines destinations; renaming `etc/` alone is not XDG adoption |
| Selective deployment | Explicit small selections for containers/SSH and fuller selections for workstations | Exact profile/component names and dependency policy are undecided |
| Reversible installation | Install, uninstall, reinstall, and reset with predictable ownership | Reset must distinguish managed configuration, packages, application state, and whole-machine changes |
| Lightweight provisioning | A small base; tools such as nmap and Wireshark are opt-in | Installing configuration must not implicitly upgrade unrelated packages |
| Agent and IDE setup | Reproducible installation of selected non-sensitive settings and external skill sources | Do not import entire live agent directories, credentials, conversation history, or downloaded skill bodies |
| CI | Actions exercise install/uninstall and shell behavior on macOS and Linux | No workflow or new tooling is introduced in this research phase |

This is multiple projects, not one indivisible overhaul. Startup correctness can
ship first; deployment ownership and component boundaries should precede a large
layout migration. Agent/IDE provisioning can be a later independent component.

## Candidate acceptance criteria

- A fresh login shell, nested login shell, and interactive non-login shell resolve
  manually managed Copilot ahead of the Homebrew installation.
- Startup does not introduce duplicates of directories managed by this repo.
  Whether to normalize pre-existing duplicates globally remains undecided.
- An inherited active project environment takes precedence over personal
  executables, which take precedence over Homebrew/system copies. This ordering
  is confirmed in [decision 0002](../../design/decisions/0002-preserve-active-project-precedence.md);
  criteria without a linked accepted decision remain proposals.
- Arbitrary caller-prepended overrides retain priority over the default tools
  and preserve their relative order, without environment-manager recognition.
  This is confirmed in [decision 0003](../../design/decisions/0003-preserve-caller-path-overrides.md).
- Default categories and the within-group order of persistent commands,
  version-managed runtimes, and other user-installed tools are approved in
  [decision 0004](../../design/decisions/0004-default-path-ordering.md).
- Prompts, aliases, completion, and Readline settings initialize in each supported
  interactive shell, without relying on exported prompt functions.
- Non-interactive startup is quiet and does not run prompt or completion logic.
- Configuration-only deployment works without Homebrew or optional applications;
  requesting a component with unmet requirements produces an explicit result.
- Reinstalling a selection is idempotent. Uninstall removes only resources owned
  by that installation and does not erase unrelated or subsequently edited files.
- Conflict handling and restoration of pre-existing files are explicit, not
  implicit overwrites.
- Container deployment can use copies where persistent repository-backed links
  are unsuitable, with clear source/update behavior.

## User-wide tools and command runners

User clarification, 2026-11-10:

- Keep persistent Python tool executables in `~/.local/bin` ahead of runtime
  shims.
- Do not install Node packages with `npm install -g`. Maintain `~/package.json`,
  install its dependencies into `~/node_modules`, and expose
  `~/node_modules/.bin` through PATH.
- `~/node_modules/.bin` follows `~/.local/bin` and precedes version-managed
  runtimes, as approved in decision 0004. Its role is user-wide CLI tools, not
  project-local tools.

Distinguish installation from execution:

- [`uv tool install`](https://docs.astral.sh/uv/concepts/tools/#tool-executables)
  exposes persistent commands in the executable directory. [`uvx`](https://docs.astral.sh/uv/concepts/tools/#tool-environments)
  normally uses disposable cached environments, and can reuse an installed tool.
- [`npx` / `npm exec`](https://docs.npmjs.com/cli/v11/commands/npm-exec/#description)
  uses local dependencies or installs requested packages into the npm cache,
  making their executables available on the executed process's PATH.
- [`bunx`](https://bun.sh/docs/pm/bunx#usage) uses local packages or a shared
  cache; Bun's documented [package cache](https://bun.sh/docs/pm/global-cache)
  defaults to `~/.bun/install/cache` and can be overridden.

These runners do not require permanently adding their cache directories to
shell PATH. Runner-supplied command environments should retain their explicit
priority under decision 0003.

## XDG interpretation

Proposed destination categories, using conventional XDG defaults:

| Category | Default destination | Examples |
|----------|---------------------|----------|
| Configuration | `~/.config` | Shell modules and application settings that support relocation |
| Data | `~/.local/share` | Installed external skill material or application data, where supported |
| State | `~/.local/state` | Installer ownership records, backups/history where appropriate |
| Cache | `~/.cache` | Redownloadable artifacts |
| Executables | `~/.local/bin` | Existing user executable convention; this is not displaced by moving configuration |

Respect supported `XDG_*` overrides and reject or handle relative paths according
to the specification; do not assume macOS applications all implement XDG.
Traditional files such as Bash's home-directory entrypoints may remain as shims.
Do not force a new `XDG_RUNTIME_DIR` into the repository or a persistent config
directory.

The [official XDG specification](https://specifications.freedesktop.org/basedir/latest/)
was discoverable in search, but direct retrieval failed during this session.
Detailed application-by-application migration rules still need source verification
before an XDG implementation is approved.

## Agent and IDE configuration: candidate boundary

Version source declarations and selected settings, not complete live directories.
A source declaration could identify the upstream repository, skill subdirectory,
and pinned revision. The installer could fetch to a managed location and expose
only selected skills to the appropriate harness. Pin updates would be explicit.

This is a proposal, not a selected format or dependency. Open issues include
licensing, offline installs, review of upstream changes, harness-specific paths,
installation ownership, and shared versus harness-specific skills. Some tools
mix authentication/session data with preferences; those require file-level
allowlists or supported configuration APIs rather than directory-wide links.

## Current gaps evidenced in the repository

- `share/install/vscode/install.sh:46-49,68` copies a fixed subset of config and
  expects execution from the repository root. Lines 51-57 may install IPython,
  so it is not a configuration-only entrypoint.
- `share/install/homebrew/core.sh:9-10` updates/upgrades Homebrew packages;
  line 68 includes nmap. `share/install/homebrew/cask.sh:25` includes Wireshark.
  These scripts also contain historical package syntax; do not use them
  unchanged as a fresh-machine baseline.
- `etc/bashrc.d/exports.bash` mixes environment construction with interactive
  `bind`/history behavior.
- `etc/bashrc.d/prompt.bash:101-102,197-208` depends on non-portable command
  conventions and Homebrew-oriented Git prompt discovery. Merely adding a
  `.bashrc` entrypoint will not complete the Linux portability goal.
- No tracked `.github/` workflow was found in the initial inventory.
