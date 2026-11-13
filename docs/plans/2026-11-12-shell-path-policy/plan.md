# Shell PATH policy repair Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development
> (if subagents are available) or superpowers:executing-plans to implement this
> plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the four documented PATH failure categories on both pinned
guests without weakening acceptance expectations or changing non-login PATH
inheritance.

**Architecture:** Keep environment initialization in the login-only
`exports.bash`. Capture PATH before tool providers run, then perform one final
ordered reconstruction after those providers. Use a private exported snapshot
of the previous dotfiles-produced PATH to distinguish supported caller prefixes
from system paths moved forward by login startup.

**Tech Stack:** Bash 3.2 and 5.2, existing guest-native pytest suites, uv, Tart,
Python standard library for result collation. No new runtime dependencies.

**Status:** Completed. Implemented and verified in `implement-shell-path-policy`,
forked from `investigate-shell-initialization` at `ca795c0`. After operator
review and approval on 2026-11-12, integrated into the stable lineage by
fast-forwarding to `6f7debf`.

---

## Context and scope

Read these before implementation:

- [Current failures and coverage limits](../../../tests/shell/README.md#baselines-and-current-results).
- Decisions [0003: caller overrides](../../design/decisions/0003-preserve-caller-path-overrides.md),
  [0004: default ordering](../../design/decisions/0004-default-path-ordering.md),
  [0006: system duplicates](../../design/decisions/0006-deduplicate-system-path-entries.md),
  and [0007: login/per-shell split](../../design/decisions/0007-split-bashrc-from-bash-profile.md).
- [Unresolved mechanism, S6](../../investigations/2026-11-10-shell-initialization/open-questions.md).
- [Completed suite plan](../2026-11-12-bash-and-dotfiles-suites/plan.md).

The last unfiltered dotfiles runs reported:

| Failure category | Ubuntu | macOS | Cause to remove |
| --- | ---: | ---: | --- |
| Managed ordering | 27 | 27 | Go is unconditionally prepended after the other providers |
| Nested-login duplicates | 9 | 9 | Login reinitialization adds another Go entry |
| Caller precedence | 3 | 3 | Providers prepend defaults ahead of the S04 caller prefix |
| Homebrew duplicates | 0 | 27 | User and system startup both contribute `/opt/homebrew/bin` |

These are repeated observations across scenarios and HOME configurations, not
66 independent macOS defects. Characterization is green. Interactive settings,
quiet startup, and HOME-with-spaces fixes are already implemented.

### Approved bounded preservation mechanism

The user selected:

> Use the private PATH snapshot for the four known failures; defer ambiguous overrides.

Export `_DOTFILES_PATH_BASELINE` containing the exact final PATH, and
`_DOTFILES_PATH_HOME` containing the HOME that produced it. These are internal
state, not activation signals callers must set. Do not use `SHLVL`, recognize
particular environment managers, intercept `bash`, or modify system startup.

System login startup executes before `.bash_profile`. In the recorded macOS
S04 launch it moves system/Homebrew entries ahead of the caller directories,
but callers remain ahead of the inherited home-tool block. Capture that
post-system, pre-provider PATH: capturing after Homebrew/Go mutation loses the
useful boundary.

Supported recovery requires a same-HOME, structurally valid baseline and an
inherited home-managed anchor still present in the incoming PATH. Recover the
prefix before that anchor while excluding entries from the baseline's default
and inherited tail. This skips system entries that moved forward; it does not
promote arbitrary appended directories. Only retain previous callers still
present in the incoming prefix; never resurrect removed paths.

This is not a universal implementation of decision 0003:

- With no usable baseline, initialize defaults and preserve the remaining
  observed PATH in order. Do not claim to recover an unseen pre-login prefix.
- A caller deliberately reusing a managed or system directory can become
  indistinguishable from default ordering after system deduplication.
- Reordered/replaced PATHs, changed system PATH providers, and launchers that
  discard private state need further design. Do not guess provenance.
- S05, S06, S07, and SSH remain explicitly pending. No pre-login capture,
  actual IDE/SSH launch, PTY transport, or live-HOME migration is in this plan.

Record these limitations in the new ADR and README. Invalid or unusable
metadata follows the explicitly documented no-baseline path, not a false claim
that caller recovery succeeded. Unexpected operational errors must still
surface; do not catch them broadly or hide provider failures.

### Defaults and duplicate boundaries

Reconstruct the home-managed entries in this order:

```text
$HOME/.local/bin
$HOME/node_modules/.bin
$HOME/.n/bin
$HOME/.rbenv/shims
$HOME/.pyenv/shims
$HOME/.go/bin
$HOME/.bun/bin
$HOME/.dotnet/tools
```

Then place the active Homebrew prefix's `bin`, followed by `sbin`, before the
remaining observed entries. Discover the prefix through the existing
`initialize_homebrew` executable branches; do not hard-code Apple Silicon as
the only supported installation.

This plan repairs ordering of supplied defaults, not provisioning:

- Preserve existing insertion rules for personal, Node, and Bun directories:
  add them when their directories exist.
- Keep the existing unconditional `GOPATH=$HOME/.go` and Go bin availability.
- Other home-managed directories participate when already supplied by incoming
  PATH or real tool initialization. Do not add `.n`, shim, or .NET directories
  solely because a fixture created them.
- Do not invent an application-tool list or ordering for ADR 0004 group 5.
  Unclassified application/launcher entries remain in the inherited tail.
  Implementing that broader category is outside these four known failures.
- Remove identical occurrences of managed defaults from the inherited tail,
  including Homebrew entries also supplied by system startup.
- Do not globally deduplicate unknown or caller entries, canonicalize paths,
  expand literal tildes, or remove empty/relative components. Preserve the
  relative order and multiplicity of unclassified inherited entries.
- An inherited directory that no longer exists must not disappear.

## File responsibilities

| File | Responsibility |
| --- | --- |
| `etc/bashrc.d/exports.bash` | Existing provider initialization, small private Bash list helpers, caller recovery, final PATH composition and snapshot export |
| `tests/shell/test_dotfiles.py` | Existing end-state acceptance plus focused guest PATH edge cases |
| `tests/shell/test_scenarios.py` | Host-only checks that strengthened acceptance assertions detect broken records, if existing assertions change |
| `tests/shell/README.md` | New results, snapshot lifecycle and bounded coverage |
| `docs/design/decisions/0009-snapshot-backed-path-reconstruction.md` | Approved mechanism, alternatives, consequences and unresolved cases |
| `docs/design/decisions/README.md` | Decision index |
| `docs/investigations/2026-11-10-shell-initialization/open-questions.md` | S6 partial resolution and remaining ambiguity |
| `docs/plans/README.md` | Navigation to this plan |

Do not add a new startup module just to hold list helpers: automatic module
discovery and synthetic `.local` coverage would otherwise change unnecessarily.
Keep `.bash_profile`/`.bashrc` loader order, local-before-tracked overrides, and
the shared runnable scenario registry unchanged.

---

## Chunk 1: Capture the contract and repair login initialization

### Task 1: Strengthen the existing PATH regression checks

**Files:**
- Modify: `tests/shell/test_dotfiles.py` (`TestExpectedState` PATH assertions).
- Modify if needed: `tests/shell/test_scenarios.py` (assertion regression tests).

- [x] **Step 1: Inspect the existing fixtures and PATH assertions.**
  Reuse `_managed_entries`, the collision markers, and candidate/system-only
  observations. Keep tests about resulting PATH and executable selection, not
  helper names, snapshot variable names, or module implementation.
- [x] **Step 2: Add only missing regression assertions.**
  Require S01 and S08-fresh-login-c to retain the currently supplied personal,
  Node, Go, and Bun defaults; otherwise removing a default can falsely satisfy
  a relative-order check. Assert Homebrew `bin` before `sbin` when present.
  Existing S04 checks already require both callers first and resolve their
  first collision marker; retain them unchanged.

  Representative assertion using existing fixture paths:

  ```python
  required = [
      str(dotfiles_home["home"] / suffix)
      for suffix in (".local/bin", "node_modules/.bin", ".go/bin", ".bun/bin")
  ]
  for shell in scenario.shells:
      if shell.launcher is None and shell.login:
          path = candidate[shell.name]["path"]
          assert all(entry in path for entry in required), (shell.name, path)
          assert [entry for entry in path if entry in required] == required
  ```

  Do not require absent runtime-manager defaults or fake installed providers.
- [x] **Step 3: Run host-safe tests once.**

  ```bash
  uv run --locked pytest tests/shell/test_scenarios.py tests/shell/test_tart_driver.py -q
  ```

  Expected: pass, including the negative assertion tests. Do not run production
  startup against the developer HOME.
- [x] **Step 4: Establish the red guest baseline on both images.**

  ```bash
  stamp=$(date +%Y%m%d-%H%M%S)
  stage=path-red
  expected_status=1
  unexpected=0
  for image in ubuntu macos; do
    status=0
    uv run tests/shell/run_tart.py --image "$image" --suite dotfiles \
      --marker acceptance \
      --artifacts "$HOME/shell-artifacts/$stage-$image-$stamp" || status=$?
    printf '%s acceptance status: %s\n' "$image" "$status"
    if [ "$status" -ne "$expected_status" ]; then unexpected=1; fi
  done
  test "$unexpected" -eq 0
  ```

  Expected: both exit 1 for the four documented categories (three on Ubuntu),
  plus overlapping strengthened ordering assertions; no transport or E1/E2
  failures. Read `run.json` and `results/pytest.xml`, not just exit status.
  Stop for any unexpected failure before changing production.
- [x] **Step 5: Commit** — `test(shell): tighten login PATH policy regressions`.

### Task 2: Implement ordered, snapshot-backed PATH reconstruction

**Files:**
- Modify: `etc/bashrc.d/exports.bash`.

- [x] **Step 1: Add small Bash 3.2-compatible list operations.**
  Use indexed arrays, quoted literal equality, and builtins. No associative
  arrays, `mapfile`, namerefs, regex membership, subprocess text splitting, or
  exported functions. Replace PATH use of `exists_in_path`; do not remove a
  user-facing function without checking its callers.

  Colon splitting must preserve leading, repeated and trailing empty entries:

  ```bash
  _dotfiles_path_split() {
    local rest=$1
    _dotfiles_path_parts=()
    while [[ $rest == *:* ]]; do
      _dotfiles_path_parts[${#_dotfiles_path_parts[@]}]="${rest%%:*}"
      rest=${rest#*:}
    done
    _dotfiles_path_parts[${#_dotfiles_path_parts[@]}]="$rest"
  }
  ```

  Declare `_dotfiles_path_parts` locally in the calling reconstruction function
  (Bash dynamic scope), then copy its result before another split. Joining must
  preserve the same components. Compare entries as `[[ $entry == "$target" ]]`.
- [x] **Step 2: Capture incoming PATH before `initialize_homebrew`.**
  Save incoming PATH and the previous snapshot in private local variables.
  Put the module's initialization statements in
  `_dotfiles_initialize_environment()` and invoke it once at the bottom;
  declare only the new scratch variables local so existing exports and
  non-PATH behavior remain unchanged.
  Keep the existing Homebrew, pyenv, rbenv, and n initialization order and
  guards; preserve their non-PATH exports. Obtain the active Homebrew prefix
  from the same successful executable branch used for `shellenv`.
  Do not rerun system profiles or instrument them.
- [x] **Step 3: Select and validate the same-HOME baseline.**
  Accept only a nonempty snapshot whose HOME matches and whose home-managed
  subsequence is unique and follows the declared ordering. Require the shared
  home-managed entries in incoming PATH to retain that order without repeated
  occurrences; otherwise caller recovery is unsupported. Compare only entries
  present in both lists so removed defaults do not alone invalidate the check.
  Use the first baseline home-managed entry (in baseline order) still present
  in incoming PATH as the anchor.
  With no matching anchor, or inconsistent baseline structure, use the
  documented no-baseline initialization. Do not infer callers from provider
  output or assume that every entry absent from the snapshot was prepended.
- [x] **Step 4: Recover the supported caller prefix.**
  Split baseline at its anchor. Scan incoming entries before the same anchor,
  in order. Exclude managed entries and entries in the baseline's tail; retain
  all other entries, including surviving previous callers. Do not scan beyond
  the anchor for novel appended paths. Never copy missing entries back from
  the snapshot.

  Concrete vectors (`H` denotes the fixture HOME; `SYS` is the inherited
  system sequence):

  ```text
  baseline: H/.local/bin:H/node_modules/.bin:H/.go/bin:H/.bun/bin:SYS
  incoming: SYS:caller-one:caller-two:H/.local/bin:...:H/.bun/bin
  recovered callers: caller-one:caller-two

  incoming: SYS:H/.local/bin:...:H/.bun/bin:appended
  recovered callers: none; appended remains in inherited tail

  baseline: old-caller:H/.local/bin:...:SYS
  incoming: SYS:new-caller:H/.local/bin:...       (old-caller removed)
  recovered callers: new-caller                (no resurrection)
  ```
- [x] **Step 5: Compose once, after all providers.**
  Give `_dotfiles_rebuild_path` this concrete interface:

  ```bash
  _dotfiles_rebuild_path \
    "$incoming_path" "$PATH" "$homebrew_prefix" "$prior_baseline" "$prior_home"
  ```

  Arguments are the post-system/pre-provider PATH, post-provider PATH,
  discovered Homebrew prefix (empty when absent), previous baseline, and its
  HOME (empty when absent). The function assigns `PATH`, returns success, and
  writes no stdout/stderr. It does not export metadata itself; its caller does
  that after composition.

  Build `callers + eligible home defaults + Homebrew bin/sbin + remainder`
  according to the scope rules above. Remove all identical managed entries
  from the post-provider remainder. Remove only the number of recovered
  caller occurrences already represented in the prefix; preserve any other
  unclassified duplicates in the remainder. Use literal comparisons throughout.
  Remove the old independent Node/Bun/personal prepend block and unconditional
  final Go prepend; retain `GOPATH` and other environment exports.
  Tool providers may still mutate temporary PATH while initializing, but no
  tracked startup code may add paths after final composition.
- [x] **Step 6: Export the final PATH and its snapshot.**

  ```bash
  export PATH
  export _DOTFILES_PATH_BASELINE="$PATH"
  export _DOTFILES_PATH_HOME="$HOME"
  ```

  Keep working arrays and scratch variables local. `.bashrc` must not compose
  PATH or refresh the snapshot in non-login children.
- [x] **Step 7: Validate syntax and host tests.**

  ```bash
  /bin/bash -n etc/bashrc.d/exports.bash
  uv run --locked pytest tests/shell/test_scenarios.py tests/shell/test_tart_driver.py -q
  git diff --check
  ```

  Expected: pass. Use the existing Ruff invocation if available; do not add
  lint dependencies or change the Python manifests for this shell-only fix.
- [x] **Step 8: Run dotfiles acceptance on both guests.**
  Repeat Task 1's loop with `stage=path-green`, `expected_status=0`, and a new
  timestamp. Its aggregate check must succeed only if both runs exit 0.
  Expected: exit 0 on both, all runnable acceptance cases pass, pending cases
  still skip. A remaining known failure requires a fix, not xfail or deletion.
- [x] **Step 9: Commit** — `fix(bash): reconstruct login PATH with caller precedence`.

---

## Chunk 2: Boundary coverage, evidence and handoff

### Task 3: Add focused guest coverage for reconstruction boundaries

**Files:**
- Modify: `tests/shell/test_dotfiles.py`.

- [x] **Step 1: Add focused guest tests, reusing real fixtures and `run_scenario`.**
  Keep additional one-off shell launch trees local to these tests; do not
  activate pending S05/S06/S07 scenarios or mutate the shared registry.
  Use fixture-owned directories and observation files only.

  | Case | Mutation / assertion |
  | --- | --- |
  | Repeated login and sourcing | Initialize, launch login child, then source `exports.bash` twice in that child; final PATH order/managed counts and resolution are unchanged |
  | Surviving and removed callers | After S04-like initialization, remove the old caller prefix, prepend new callers, launch another login; only new callers are first |
  | Appended unknown path | Append a fixture directory after initialization, then launch login; it stays behind defaults, not promoted as a caller |
  | Literal components | Use caller/inherited directories containing spaces, `*`, `?`, and `[`; preserve literal values and marker resolution |
  | Tail multiplicity | Supply repeated unknown directories, relative components, and leading/interior/trailing empty components directly to the composer; preserve their sequence and multiplicity |
  | Missing inherited directory | Include a now-missing inherited directory; final composition retains it |
  | No/stale snapshot | Unset both metadata values, supply inconsistent metadata, or change HOME; initialize for the current HOME without copying paths out of stale metadata |

  Full startup may legitimately transform empties through system/provider code.
  Test composer preservation directly inside the guest for that case, and
  retain the real-system startup tests for end-to-end behavior. Do not replace
  tracked modules, Homebrew, `path_helper`, or providers with stand-ins.

  `run_scenario` does not expose arbitrary between-launch mutations. Keep a
  small test-local `_run_path_case` wrapper for the cases requiring those
  mutations: invoke the validated `shell_bash` with a fixed `-l -c` body,
  explicit fixture environment, `stdin=subprocess.DEVNULL`,
  `start_new_session=True`, and a 120-second timeout. Pass paths and test values
  as positional arguments, not interpolated command text. Capture return code
  and raw streams in fixture-owned artifacts. Reuse `PROBE`/`SERIALIZE` for
  final observations rather than introducing a second JSON format.

  For direct composer cases, load the real login environment first, then call
  `_dotfiles_rebuild_path` with explicit fixture PATH vectors and empty snapshot
  arguments. Probe immediately afterward; no subsequent startup or provider
  may transform the result. This also covers components that real system
  startup would otherwise normalize. The wrapper is test-local, not a new
  configurable transport or production hook.
- [x] **Step 2: Ensure the tests exercise behavior rather than constants.**
  Snapshot metadata may be cleared/injected to reach lifecycle branches, but
  assert resulting PATH and collision-marker selection, not the private
  variable values. Use explicit expected lists, not the production composer
  as the expected-value oracle. Cover both fresh and initialized baselines.
- [x] **Step 3: Run new tests through the dotfiles driver on both guests.**
  Repeat Task 1's loop with `stage=path-boundaries`, `expected_status=0`, and
  a new timestamp. Expected: both exit 0, E1/E2 and inherited
  non-login behavior remain green. If a new boundary case fails, fix it in
  `exports.bash` before proceeding.
- [x] **Step 4: Run host tests, syntax and diff checks once after any fixes.**
  Use Task 2 Step 7's commands. Expected: pass.
- [x] **Step 5: Commit** — `test(shell): cover PATH snapshot lifecycle and literal entries`.
  If production fixes were needed after Task 2's commit, commit those separately
  as `fix(bash): <specific correction>`; never amend earlier work.

### Task 4: Full guest verification and documentation

**Files:**
- Modify: `tests/shell/README.md`.
- Create: `docs/design/decisions/0009-snapshot-backed-path-reconstruction.md`.
- Modify: `docs/design/decisions/README.md`.
- Modify: `docs/investigations/2026-11-10-shell-initialization/open-questions.md`.
- Modify: this `plan.md` (completion checkboxes).

- [x] **Step 1: Run all four guest combinations without a marker.**

  ```bash
  stamp=$(date +%Y%m%d-%H%M%S)
  failed=0
  for image in ubuntu macos; do
    for suite in bash dotfiles; do
      status=0
      uv run tests/shell/run_tart.py --image "$image" --suite "$suite" \
        --artifacts "$HOME/shell-artifacts/path-final-$image-$suite-$stamp" || status=$?
      printf '%s/%s status: %s\n' "$image" "$suite" "$status"
      if [ "$status" -ne 0 ]; then failed=1; fi
    done
  done
  test "$failed" -eq 0
  ```

  Expected: all four exit 0. Both Bash suites retain startup-file semantics;
  both dotfiles suites pass every runnable case. Record counts from actual
  XML; added tests change totals, so do not copy old counts.
- [x] **Step 2: Check artifacts and clone cleanup.**
  Verify `run.json` has no infrastructure/cleanup error. Record revision and
  dirty state accurately; if tests run against uncommitted fixes, label that
  evidence and repeat affected validation after committing.
  `tart list` must contain no run-owned clones; reusable local bases and OCI
  cache entries are allowed. Do not delete unrelated images.
- [x] **Step 3: Collate results into passed/failed/skipped counts per marker.**
  Use `results/pytest.xml`: Bash cases are characterization;
  `test_dotfiles_integrity_and_system_only_control` is characterization;
  `TestExpectedState` and the new PATH boundary cases are acceptance.
  Record pending skip reasons, and investigate every failure. Keep raw logs
  and PATH observations in artifact directories, not repository documentation.
- [x] **Step 4: Record the mechanism as the next ADR.**
  Follow the repository format: context, decision, alternatives, consequences,
  user approval, and links to ADRs 0003/0004/0006/0007. Alternatives include
  blind default prepending, membership-only snapshot subtraction (incorrectly
  promotes appended paths), and pre-login capture/launcher wrapping (deferred).
  State the partial caller-provenance boundary explicitly. Verify 0009 is still
  the next number above the current target branch's highest ADR before creating
  it; do not renumber published records or fill historical gaps.
- [x] **Step 5: Update README results and S6.**
  Replace historical failure claims with new verified results while retaining
  a brief explanation of the repaired categories. Document the private
  snapshot lifecycle, missing/unusable snapshot behavior, duplicate boundaries,
  unchanged non-login inheritance, and pending ambiguous overrides.
  Mark S6 partially resolved, not universally solved. Retain PTY/SSH limits.
- [x] **Step 6: Finish checkboxes, check links and commit.**
  Check off only completed steps in this plan. Run `git diff --check`; verify
  ADR links and index. Commit `docs(shell): record PATH repair results and limitations`.

### Execution evidence and operator gate

Clean final validation tested `53031888ef4a759b3b5b709f50dbf6621988a9da`.
All four unfiltered runs exited 0, with no infrastructure/cleanup errors or
retained run-owned clones. Per image, Bash recorded 321 passed / 0 failed /
192 skipped; dotfiles recorded 642 passed / 0 failed / 481 skipped, including
612 acceptance passes. Host-safe tests recorded 100 passes; syntax, Ruff and
diff checks passed. [Results](../../../tests/shell/README.md#baselines-and-current-results)
link the raw artifacts and explain pending skips.

Atomic implementation commits: `ceaed379` (regressions), `36376d4` (composer),
`e4762fe` (boundaries), and `5303188` (active Homebrew test expectations).
Per-task specification and quality reviews, followed by final code review,
found no remaining significant issues. Earlier dirty red/boundary evidence is
not substituted for the clean final matrix.

- [x] **Operator approval:** The user reviewed the isolated worktree and approved
  completion, integration into `investigate-shell-initialization`, and cleanup
  of the implementation worktree/branch on 2026-11-12. The fast-forward retained
  the reviewed source tree unchanged; merged host-safe tests (100 passes),
  syntax, Ruff, and diff checks passed.

## Completion criteria

The four known failure categories are eliminated on both pinned guests;
all runnable Bash and dotfiles tests pass; pending scenarios remain visible
as skips; raw evidence is retrievable; no run-owned Tart clones remain.

The result implements the approved bounded snapshot mechanism, not universal
caller-provenance recovery or all unimplemented categories of ADR 0004.
Do not weaken behavior to meet a green summary. Stop and obtain approval if
passing the known cases requires a pre-login hook, system-file change, broader
deduplication policy, or expanded launcher scope.

Use @verification-before-completion and @finishing-a-development-branch at
execution handoff. Make atomic Conventional Commits with the required Copilot
coauthor trailer; commit only task-owned changes and do not amend history.
