# Approaches and smallest useful changes

Status: recommendations for discussion, not approved decisions or an
implementation plan.

## Long-term approaches

| Approach | Benefits | Costs and risks |
|----------|----------|-----------------|
| A. Incrementally evolve the existing symlink workflow | Preserves `main`, `cddotfiles`, and direct editing; shell fix can ship independently; component/XDG migration can be staged | Any custom deployment tool must own conflict handling, backups, uninstall semantics, and tests; keep it deliberately small |
| B. Adopt a link-focused manager | Stow supplies package selection and link lifecycle; Dotbot supplies explicit mappings/conditions without requiring a target-mirrored layout | New runtime/tool dependency; neither supplies the full package/skill/reset lifecycle. Stow and Dotbot are alternatives with different conventions, not interchangeable wrappers |
| C. Adopt a rendered desired-state manager such as chezmoi | Strong templating, target variation, external-source support, and preview mechanisms | Broad migration and changed editing/apply semantics; symlink mode has restrictions. Current cross-machine Git sync is not itself a reason to migrate |
| D. Use configuration management or task orchestration | Ansible or Chef can manage configuration and optional packages; Fabric/Invoke can coordinate local/remote deployment while retaining source symlinks | More bootstrap/runtime dependencies; explicit ownership and reset policies still required. Fabric executes tasks rather than supplying a desired-state resource model |

Initial recommendation: A for startup correctness, then evaluate A versus B for
deployment after defining ownership and component boundaries, with Ansible as a
serious additional contender if optional machine provisioning is in scope.
Consider C only if rendered per-machine differences justify it. This does not
commit the project to maintaining a custom installer.

Approach D can also wrap A or B: for example, Ansible can install prerequisites
and selected links, or invoke a small shared component installer. Avoid having
two tools independently manage the same target. See the
[provisioning-tool comparison](reference-survey.md#provisioning-and-orchestration-tools).

## Evidence behind the immediate PATH issue

The initial static findings are in [context.md](context.md). Additional read-only
probes used `env -i` with explicitly supplied PATH values; they printed generated
startup code without evaluating it or modifying live startup files:

- With personal bin first and Homebrew's bin/sbin already later in PATH,
  installed `brew shellenv bash` still emitted a PATH assignment that prepends
  Homebrew bin/sbin to the inherited PATH. Evaluating that output would put
  Homebrew first and repeat the existing Homebrew entries.
- `path_helper -s`, given Homebrew-first PATH, emitted system-configured paths
  first, followed by the remaining inherited Homebrew entries.

The tracked personal-bin logic checks membership only
(`etc/bashrc.d/exports.bash:78-96`). It does not move an existing entry back ahead
of Homebrew. Go's bin directory is unconditionally prepended at lines 122-123.

This demonstrates a concrete mechanism consistent with the reported symptom,
not the complete PATH sequence inside Herdr. Local overrides and launcher
behavior remain unmeasured.

## Immediate choices

### 1. PATH-only correction

Keep the current login entrypoint and module layout. Make PATH operations
repeat-safe and enforce the agreed precedence after system/Homebrew setup.
Apply the policy to the repo-owned personal, Bun, node modules, and Go entries;
review version-manager/local initialization for dependent changes.

A helper must distinguish "ensure present" from "ensure priority." Moving a
managed entry requires removing its previous occurrences before reinserting it.
Preserve unrelated entries and their relative order; handle spaces and literal
path characters without regex or unquoted word splitting.

This is the smallest *class* of correction for nested login PATH behavior. Exact
patch size depends on the desired ordering and local overrides. It does not
repair non-login interactive startup.

If active virtual environments should remain ahead of personal tools, a blind
"always put personal bin first" policy is insufficient. Nested login system
startup may have already reordered the inherited environment before user files
run; preserving its intended priority must be deliberate.

### 2. PATH correction plus consistent interactive initialization

Add a `.bashrc` entrypoint to the existing framework and arrange for both
interactive login and interactive non-login Bash to load the same interactive
modules. Prefer one shared loader with thin entrypoint wrappers. Keep the
existing `.bash_login` entrypoint during transition if that minimizes deployment
risk; a switch to `.bash_profile` is optional, not part of the bug fix.

Make environment/PATH setup repeat-safe, and separate or guard interactive
`bind`, prompt, history, and completion behavior. Load prompt functions in each
interactive process before setting the hook. Do not export a global "already
initialized" flag that suppresses a child's aliases/functions.

This is the recommended bounded first project: fix both reported startup modes
without XDG migration, package provisioning changes, a new dotfile manager, or
agent configuration work. Supporting a minimal Linux environment may also
require a fallback when the Homebrew Git prompt helper is absent; the existing
unconditional `__git_ps1` call cannot be assumed portable.

### 3. Combine startup repair with a layout/tool overhaul

Possible, but not necessary to fix either symptom. It increases the number of
moving parts, makes regression attribution harder, and delays a useful repair.
Do not bundle it into the first change without a concrete additional reason.

## Tempting fixes that are insufficient

- `SHLVL == 1` or an inherited global initialization flag: system login setup can
  still reorder PATH, and a fresh child still needs functions/options.
- Skipping Homebrew solely because `HOMEBREW_PREFIX` is set: does not undo
  system PATH reordering or resolve unconditional appends elsewhere.
- Deduplicating without specifying precedence: preserves whichever wrong entry
  happened to occur first.
- Prepending `~/.local/bin` unconditionally: repairs one lookup but introduces
  duplicates and can override active project environments.
- Restoring an old PATH snapshot: can discard later environment activation.
- Exporting every prompt function: does not initialize completion/options and
  unnecessarily expands inherited shell state.
- Installing a new `.bash_profile` without dispatching the current framework:
  silently shadows `.bash_login`.

## Proposed verification scope for an approved startup change

Use temporary HOME fixtures and controlled tool stubs, not live local overrides.
Exercise initial and nested interactive login shells, interactive non-login
shells, and repeated startup in the same process. Check executable resolution,
managed-entry duplication, inherited project precedence, and prompt/helper
availability. Include missing optional tools and non-interactive quietness.

The available local interpreters are Apple Bash 3.2 and Homebrew Bash 5.3.
Whether both are supported is an open requirement, not an implicit promise.
Future Actions should include macOS and Linux; a shell-only fixture test is
separate from a later installer install/uninstall round-trip test.
