# Shell Fixture Harness Implementation Plan

> **For agentic workers:** Use the executing-plans skill to implement this plan.
> Steps use checkbox (`- [ ]`) syntax for tracking. Keep this bounded work in the
> existing investigation worktree; do not modify production startup behavior.

**Goal:** Reproducibly observe current startup and expose S01-S04 policy
violations in disposable macOS and Ubuntu guests.

**Architecture:** Guest-native pytest fixtures invoke real Bash startup.
A thin Python host driver owns Tart lifecycle, source/tooling transfer, results,
and cleanup. Characterization and policy acceptance have separate invocations;
known acceptance failures remain failures.

**Tech Stack:** Python standard library, pytest, uv, Tart 2.41.1, Apple Bash 3.2,
Ubuntu Bash 5.2.

**Status:** Harness implementation and follow-ups are complete and committed.
Characterization passes on both pinned guests; acceptance reports the expected
startup-policy failures, including missing user-facing functions in
interactive non-login shells. No production startup files were changed.

---

## Chunk 1: Contracts and guest scenarios

### File responsibilities

| File | Responsibility |
|------|----------------|
| `pyproject.toml`, `uv.lock` | Locked pytest development tooling; no runtime dotfiles dependencies |
| `tests/shell/conftest.py` | Guest-only opt-in, interpreter checks, independent HOME fixtures, explicit environments and observations |
| `tests/shell/test_startup.py` | S01-S04 characterization and approved policy assertions |
| `tests/shell/run_tart.py` | Executable uv-script host entrypoint; bounded Tart lifecycle and artifact transport |
| `tests/shell/test_tart_driver.py` | Focused host-safe tests of driver-owned cleanup/status/transfer behavior |
| `tests/shell/README.md` | Short usage/navigation and baseline matrix |

Do not add a generic VM abstraction, dependency-injection layer in startup code,
or a separate reusable package. Add a shared helper only if the resulting code
actually needs one. Imported modules are not executable; the driver has a uv
shebang and executable permission.

### Task 1: Establish test tooling and invocation boundaries

- [x] Inspect existing Python/tooling metadata again before creating files;
  integrate rather than replacing any newly added repository configuration.
- [x] Add pytest as a uv-managed development dependency; generate and commit
  `uv.lock`. Use only pytest and the standard library. Select compatible Python
  requirements after checking both guest interpreters, not the host alone.
- [x] Register `characterization` and `acceptance` pytest markers and fail on
  unregistered markers.
- [x] Add explicit `--shell-bash` and `--shell-guest-root` options for scenario
  runs. Validate interpreter executability/version and a writable test-owned
  guest root. Refuse scenario execution when the explicit guest-root option is
  missing; do not mistake this opt-in for a security sandbox.
- [x] Keep guest-only setup lazy so host-safe driver tests do not invoke Bash
  startup or require the guest options.
- [x] Verify missing interpreter/root inputs produce pytest usage errors before
  sourcing repository code. Run collection to catch marker/import errors.
- [x] Commit: `test(shell): establish locked guest test tooling`.

Intended guest interface:

```bash
uv run --locked pytest tests/shell/test_startup.py \
  --shell-bash /bin/bash --shell-guest-root /tmp/dotfiles-tests \
  -m characterization --junitxml /tmp/dotfiles-results/pytest.xml
```

Invoke from the transferred source directory; the driver prepares those paths.
Do not run this guest command on the developer host.

### Task 2: Implement real-startup observations and S01-S04

- [x] Create per-test homes beneath pytest temporary storage in the supplied
  guest root. Copy the real loader to `.bash_login` and the exports and
  functions modules to `.local/etc/bashrc.d/`; do not add a `.bashrc` dispatch
  that production lacks.
- [x] Create existing personal/Node/Bun/Go directories and unique harmless
  collision-marker executables in fixture-owned directories. Include a HOME
  containing spaces. No real Copilot binary is needed.
- [x] Construct child environments from an allowlist, not `os.environ.copy()`.
  Initial PATH is `/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`; supply HOME,
  user identity, locale, TERM, and a synthetic TERM_PROGRAM. Put history and
  results under the fixture root.
- [x] Write shell observation commands that save JSON-compatible data through
  a guest Python executable referenced by its absolute path. Pass filenames
  through positional arguments rather than interpolating unquoted shell text.
  Keep observations separate from startup stdout/stderr.
- [x] Capture PATH entries, marker resolution, login/interactivity, SHLVL,
  internal helper and user-facing function availability, exit status, stdout,
  and stderr. Use bounded `subprocess` execution. No parent shell startup
  should be involved.
- [x] Implement S01 fresh interactive login and S02 actual nested login.
  Preserve the parent/child relationship; separate Python subprocesses with
  similar environments are not a nesting test.
- [x] Implement S03 plain interactive non-login child and S04 login/non-login
  children with two arbitrary caller directories prepended. Children are
  independent siblings from the same outer shell.
- [x] Add characterization assertions only for observation integrity: expected
  shell mode, complete records, executable marker identity, and successful
  command execution. Save incorrect ordering rather than calling it correct.
- [x] Add acceptance assertions for approved applicable default ordering,
  no startup-added managed duplicates, `codetree` and `jqless` availability in
  new interactive processes, and caller directories retaining precedence and
  relative order.
  Compare observed managed entries without deciding missing-directory or
  global-deduplication policies.
- [x] Verify known policy assertions fail against unchanged sources: nested Go
  duplication, caller displacement, absent non-login user functions, and fresh
  default ordering. Unexpected infrastructure errors are not acceptable
  substitutes for those failures.
- [x] Commit: `test(shell): characterize real startup and assert PATH policy`.

Core acceptance examples, using observations rather than parsing log banners:

```python
assert child.path[:2] == caller_directories
assert child.path.count(go_bin) <= parent.path.count(go_bin)
assert nonlogin.user_functions["codetree"] is True
assert fresh.path.index(personal_bin) < fresh.path.index(go_bin)
```

Do not create a “fixed” startup fixture just to turn these assertions green.
The first increment does not claim custom prompt rendering or full-framework
coverage. System startup remains active: no `--noprofile`, fake `path_helper`,
or fake Homebrew for these cases.

## Chunk 2: Local Tart driver and end-to-end evidence

### Task 3: Implement bounded lifecycle and artifact ownership

- [x] Inspect `tart` help and existing baselines without changing them. Encode
  these immutable image references as the initial selectable matrix:

```text
macOS:
ghcr.io/cirruslabs/macos-tahoe-base@sha256:65c3133a633fda8753cf1f71f2d55727792d534a2125b0032466563dcc8e58fd
Ubuntu:
ghcr.io/cirruslabs/ubuntu@sha256:97166c84ea5f102be33d2959f70e83861a36bd749f1715ab669d93e6c9f31476
```

- [x] Define a minimal CLI: required `--image macos|ubuntu`, optional explicit
  `--bash` (default `/bin/bash`), `--suite characterization|acceptance`, and
  required `--artifacts` destination. Reject existing nonempty artifact paths.
  Do not add a broad shell-command passthrough.
- [x] Add host-safe tests with simulated subprocess results for failed guest
  commands preserving nonzero status, clone failure not deleting unowned VMs,
  and artifact failure still attempting stop/cleanup of an owned clone.
- [x] Generate a unique clone name. Set `TART_NO_AUTO_PRUNE=1` for clone
  commands, never use overwrite, and record ownership only after creation
  succeeds. Launch `tart run` as a tracked child process with the isolation
  flags used in the experiments.
- [x] Poll successful guest-agent execution with a deadline. Record transient
  readiness failures; on timeout, stop the owned guest and surface the error.
- [x] Transfer an explicit allowlist of `etc/bash_login.bash`,
  `etc/bashrc.d/exports.bash`, `etc/bashrc.d/functions.bash`, guest test files,
  and dependency manifests.
  Archive relative regular-file entries without macOS metadata; never transmit
  the entire worktree or dereference symlinks to external content.
- [x] Record git revision, dirty status, and hashes of transferred source
  bytes. Test the worktree content, not only HEAD, so future edits are exercised.
- [x] Bootstrap a pinned official uv release inside the guest only when absent.
  Verify its distribution using the release's published integrity metadata,
  install without changing profiles, and record the version. Since the guests
  have no network access, export locked dev requirements (`uv export --locked`),
  then install the host-verified wheelhouse offline using
  `uv pip install --offline --no-index --require-hashes`; do not use
  `uv sync --locked`, which still fetches registry URLs. Determine the pin
  during implementation and persist it, not `latest`.
- [x] Run the selected pytest suite and retrieve result files through the agent.
  Keep host/guest command logs and JUnit results in the artifact directory.
  Artifact transfer must check exit codes and reject unsafe archive paths.
- [x] Use `finally` cleanup for setup, execution, and collection failures.
  Stop only the owned VM, confirm it is stopped, delete the clone, and reap the
  runner child. If stop cannot be confirmed, retain the clone and report its
  name rather than deleting a possibly running guest or hiding the failure.
- [x] Return nonzero for failed tests, setup, collection, or cleanup. Preserve
  the pytest status in run metadata even if a later cleanup error also occurs.
- [x] Run the host-safe tests; commit:
  `test(shell): add isolated Tart lifecycle driver`.

Intended host interface:

```bash
uv run tests/shell/run_tart.py --image ubuntu \
  --suite characterization --artifacts /tmp/dotfiles-ubuntu-characterization
```

Ordinary observations need no guest PTY; retain and explain any interactive
Bash job-control diagnostic. The design reserves Python PTY support for later
prompt-rendering cases; do not implement unused PTY orchestration now.

### Task 4: Exercise both baselines and document the result

- [x] Run host-safe driver tests in one invocation:

```bash
uv run --locked pytest tests/shell/test_tart_driver.py
```

- [x] Run characterization once for each image through the driver. Require
  successful observations and complete artifacts on both guests.
- [x] Run acceptance once for each image in fresh clones. Require nonzero
  results tied to the intended S01-S04 assertions, not transport failures.
  Save exact failures and baseline identities. Do not retry merely to seek a
  green summary.
- [x] Confirm failed acceptance also retrieves artifacts and removes its owned
  clone. Check the final Tart listing contains no run-owned running guests.
  Do not delete the reusable baseline/cache.
- [x] Inspect manifests, transferred-file hashes, stdout/stderr, and JUnit
  output to confirm both real system startup and actual tested source.
- [x] Write `tests/shell/README.md` with the two invocations, guest-only safety
  boundary, diagnostic locations, expected current acceptance failures, and
  explicit coverage limitations.
- [x] Update investigation navigation/status with a link to the harness and
  remaining startup-policy questions. Record observed results, not raw logs
  containing machine-specific or potentially sensitive state.
- [x] Run `git diff --check` and any existing applicable repository formatter
  or linter discovered during implementation. Do not add lint dependencies
  solely for this increment.
- [x] Commit: `docs(shell): document VM harness and known policy failures`.

## Completion criteria and handoff

The harness increment is complete when host-safe driver tests and both
characterization runs succeed, both acceptance runs report the expected
policy failures with retrievable evidence, and all owned run clones are stopped
and deleted. This means the harness works, **not** that startup behavior passes.

Do not implement the PATH fix as part of this plan. Use the resulting failures
to design the smallest startup change, resolving caller-provenance and remaining
policy questions with the user first. S05-S08, complete prompt/alias coverage,
CI, XDG, and deployment tooling remain later work.

## Follow-up: Bare Bash startup-file probes

- [x] With an empty user HOME and real system startup enabled, characterize the
  child `bash`, `bash -l`, and caller-prefixed environment invocations.
- [x] Verify child environment mutations do not alter the parent; capture
  exported-variable inheritance and PATH results.
- [x] Add marker-only `.bashrc`, `.bash_profile`, and `.bash_login` fixtures
  separately; verify login-file fallback and explicit `.bashrc` sourcing.
- [x] Run characterization on both pinned guests and document the results in
  `tests/shell/README.md`.

The direct Bash probes do not launch VS Code or SSH. Their actual launch
scenarios remain unmeasured by the Tart harness.

## Follow-up: User-facing function availability

- [x] Include the real `functions.bash` module in the guest source allowlist and
  fixture, so login-shell probes observe the repository's `codetree` and
  `jqless` definitions.
- [x] Replace the internal `exists_in_path` acceptance proxy with assertions
  for those user-facing functions.
- [x] Re-run characterization and acceptance on both pinned guests. Both
  characterization suites pass; acceptance fails specifically for the plain
  interactive non-login children that lack `codetree` and `jqless`.
- [x] Update the S03 requirement and S2 investigation note. Production startup
  integration remains outside this harness change.

## Follow-up: `.bashrc` / `.bash_profile` split

- [x] Add acceptance tests for inherited PATH in non-login children, one-time
  `.local`-first module loading under `.bash_profile` (ignoring a stale
  `.bash_login` and `.profile`), and non-interactive login skipping per-shell
  modules.
- [x] Rename `etc/bash_login.bash` to `etc/bash_profile.bash`, add
  `etc/bashrc.bash`, and update the fixture and source allowlist.
- [x] Run both suites on both guests. Characterization: 13/13 on each.
  Acceptance: Ubuntu 13 passed / 8 failed, macOS 12 passed / 9 failed; every
  remaining failure is a known PATH-policy gap.
- [x] Record [decision 0007](../../design/decisions/0007-split-bashrc-from-bash-profile.md).
- [x] Characterize non-interactive `bash -c` and `bash -l -c`: a marker-only
  probe for Bash's file selection, and a real-dotfiles test confirming neither
  defines user functions. Both guests: characterization 15/15; acceptance adds
  no new failures.
