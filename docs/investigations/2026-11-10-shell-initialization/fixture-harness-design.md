# HOME fixture harness proposal

Updated: 2026-11-11

Status: architecture and initial interpreter matrix approved by the user on
2026-11-11; see [decision 0005](../../design/decisions/0005-guest-native-shell-tests.md).
Informed by successful
[macOS](tart-experiment.md) and [Ubuntu](tart-ubuntu-experiment.md) experiments.
The [scenario scope](scenarios.md) is approved. Production startup changes
remain unapproved.

## Recommendation and alternatives

Use **guest-native pytest tests with a thin host-side Tart driver**. Tests
describe shell behavior; the driver provisions disposable execution environments.
The tests must also run directly inside a future GitHub-hosted VM without Tart.

| Approach | Benefit | Cost or limitation |
|----------|---------|--------------------|
| Direct Tart + guest-native pytest (recommended) | Proven macOS/Linux agent transport, real startup, reusable assertions, no extra orchestrator | We own a small lifecycle/transfer driver |
| Cirrus CLI + guest-native pytest | Existing task and artifact conventions | Additional dependency; Linux Tart orchestration not established here |
| Controlled host fixtures first | Fast, cheap feedback | Simulated system startup misses important behavior; temporary HOME cannot isolate absolute Homebrew calls |

Controlled unit tests can be added when a production helper warrants them.
They are not a prerequisite or a substitute for real-OS acceptance.

## Components and execution flow

1. A host entrypoint selects a pinned image and explicit guest Bash path, then
   creates a uniquely named disposable clone from an unbooted baseline.
2. The driver boots the clone without host mounts, clipboard, audio, or USB
   sharing, verifies running state, and waits for successful agent execution
   within a deadline.
3. It transfers an explicit allowlist of tracked startup sources, tests, and
   Python manifests. No live HOME, ignored local modules, credentials, or
   unrelated repository content is copied.
4. It prepares the locked uv/pytest environment inside the clone and invokes
   pytest through `tart exec`. Ordinary checks use pipes; prompt checks request
   an actual PTY.
5. It retrieves diagnostics into a unique host artifact directory, then stops
   and deletes only its owned disposable clone.

The guest test process is the boundary between lifecycle orchestration and
scenario assertions. It consumes an explicit Bash executable and artifact
directory, and returns pytest's exit status. It has no Tart dependency.
The host driver must preserve a failing test status after artifact collection
and cleanup; transport or cleanup failures also make the run unsuccessful.

Keep the initial organization small:

```text
pyproject.toml                 # pytest development dependency
uv.lock                       # reproducible Python dependencies
tests/shell/
  README.md                   # invocation and artifact navigation
  conftest.py                 # HOME and environment fixtures
  test_startup.py              # shell scenarios and assertions
  run_tart.py                  # executable host lifecycle entrypoint
```

Use standard-library subprocess/filesystem/PTY facilities and pytest; no pytest
plugins, Testcontainers, Bats, or Cirrus CLI. Extract a helper module only when
actual shared logic needs it, not to satisfy a predetermined directory layout.
The executable Python driver follows this repository's uv-script convention.

## Initial environment matrix

Start with the exact image digests captured in the experiments:

| Guest | Initial interpreter | Baseline |
|-------|---------------------|----------|
| macOS 26.6.2 arm64 | `/bin/bash`, Apple Bash 3.2.57 | Existing Tahoe base digest |
| Ubuntu 24.04.5 arm64 | `/bin/bash`, Bash 5.2.21 | Existing Ubuntu digest |

Accept an explicit interpreter path and record its actual version. A requested
interpreter that is absent is an error. Current Homebrew Bash on macOS, other
distributions, x86-64, and GUI launchers are later matrix extensions, not silently
claimed coverage.

Retain stopped pristine baselines and downloaded caches. Disable Tart automatic
pruning. Guest-wide package/system mutations require a fresh clone; HOME-only
cases may share a run clone while using independent per-test directories.
Do not install Homebrew or runtime managers merely to fill the first matrix:
the existing macOS image has real Homebrew/rbenv, while Ubuntu supplies a useful
missing-tool baseline.

## Python tooling

Manage pytest through uv with committed dependency metadata and a lockfile.
Keep the Python environment outside fixture homes. Use an existing suitable
guest Python; bootstrap a pinned uv release inside the disposable guest if
needed, without modifying login files. Record tool versions and fail explicitly
if setup/download fails. Tool provisioning may require network access; shell
test cases themselves must not download packages.

This adds only test tooling, not a dotfiles package-provisioning system.
Future GitHub-hosted jobs can prepare the same locked environment and run the
same guest command directly.

## HOME fixtures and real startup

Build fresh fixture homes from tracked files and explicit synthetic inputs,
never a copy of the user's HOME. Reproduce the repository's current entrypoint
layout; do not introduce a successful test-only profile-to-rc dispatch. (Since
decision 0007 the production `.bash_profile` itself sources `.bashrc`, and the
fixture installs both tracked files.)
Include only the modules needed by each case, and distinguish the current
loader/exports/functions subset from full interactive-framework coverage.

Construct a small explicit child environment. Supply HOME, initial PATH,
locale, terminal settings, and fixture history locations. Do not accidentally
inherit `BASH_ENV`, exported functions, prompt hooks, activation markers, or
telemetry variables. Scenarios that need such variables declare them explicitly.
Include directories containing spaces and colliding harmless marker executables.

Invoke actual login and non-login Bash processes, including real nested shells,
without `--noprofile` or a simulated system profile for acceptance cases.
System `/etc/profile`, platform bashrc, and `path_helper` remain active.
Do not rewrite production source or repair PATH before observing it.

Record machine-readable observations in fixture-owned files, separately from
stdout/stderr: PATH entries, command resolution, SHLVL, login/interactivity
flags, aliases/functions, and relevant prompt hooks. Preserve startup output.
Ubuntu's sudo guidance is system output; the current repository's misleading
`Homebrew initialized` message is not proof of an installed dependency.

## First implementation increment

Implement the fixture/lifecycle foundation and these bounded cases first:

- S01: observe fresh-login ordering and marker-command resolution.
- S02: compare nested-login precedence and managed-path occurrence counts.
- S03: compare non-login PATH and availability of user-facing functions such as
  `codetree` and `jqless`.
- S04: preserve arbitrary caller-prepended directories through login and
  non-login startup.

Use the real loader/exports/functions subset first. Add full prompt rendering
and aliases only with their actual tracked modules and explicit dependency
inventory. Do not infer prompt correctness or alias coverage from this limited
module set.

Keep characterization and policy acceptance visibly separate. Characterization
captures observations without asserting that current incorrect ordering is
desired. Acceptance asserts approved requirements and returns failure for
violations; initial failures are expected evidence, not grounds to skip tests,
weaken assertions, or mark the suite passing. Attribute each failure to a
scenario and baseline so the later startup fix has a concrete regression target.

S05-S08, repeated sourcing, terminal callback composition, and broader optional
tool combinations remain approved scenario scope but are later increments.
Do not claim the initial suite covers them.

## PTY, diagnostics, and failures

Pipes suffice for PATH/function observations. For prompt rendering, the driver
must supply a host PTY before requesting `tart exec -t`: the experiment showed
that a non-terminal host invocation crashes Tart's PTY path. Use Python's
standard-library PTY support rather than requiring an interactive operator.
Exercise an actual prompt before claiming rendering coverage.

Every subprocess and readiness loop has a deadline. Record command arguments,
exit status, stdout/stderr, image digest, guest OS/architecture, Bash version,
source revision/dirty state, relevant system profiles, optional-tool inventory,
and per-scenario observations. Capture tested source content hashes so a dirty
worktree run remains identifiable. Transfer files without irrelevant macOS
extended attributes.

Artifact collection and cleanup run on test/setup failure as well as success.
If the guest is unreachable, retain available host logs and report that guest
artifacts could not be retrieved. Do not replace missing results with a
success-shaped fallback. Terminate owned child processes, stop the owned VM,
and confirm shutdown before deletion. Never prune unrelated VMs or caches.
The caller receives the artifact location on both successful and failing runs.

## Outstanding startup-policy questions

The harness does not decide global deduplication, missing-directory policy,
empty/relative PATH handling, application ordering within a group, or how caller
intent survives login system mutations. Preserve diagnostic inputs for these
questions without inventing expected answers.

S07's stale-launcher-versus-explicit-override ambiguity needs a startup design:
PATH alone cannot establish provenance. Real VS Code/Herdr behavior also
requires separate application-level evidence.

## Approval boundary

The architecture and initial two-interpreter matrix are approved; the
[implementation plan](../../plans/2026-11-11-shell-fixture-harness/plan.md)
is the next review artifact. Production startup changes require a separate design, informed by
the failing acceptance cases. XDG migration, install/uninstall tooling, GitHub
Actions, and package/agent/IDE provisioning remain outside this increment.

## References

- [pytest temporary directories](https://docs.pytest.org/en/stable/how-to/tmp_path.html#the-tmp-path-fixture)
- [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html#pytest-mark-parametrize)
- [uv locked dependency synchronization](https://docs.astral.sh/uv/concepts/projects/sync/#locking-and-syncing)
- [GNU Bash startup rules](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html#Bash-Startup-Files-1)
- [Python PTY facilities](https://docs.python.org/3/library/pty.html#module-pty)
- [Local macOS experiment and PTY recovery](tart-experiment.md#pty-transport-caveat-and-recovery)
- [Local Ubuntu experiment](tart-ubuntu-experiment.md#results)
