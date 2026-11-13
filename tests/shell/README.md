# Shell startup harness

Guest-native pytest scenarios for Bash startup, run in disposable Tart clones
of pinned macOS and Ubuntu images. Design and scope:
[fixture harness proposal](../../docs/investigations/2026-11-10-shell-initialization/fixture-harness-design.md),
[implementation plan](../../docs/plans/2026-11-11-shell-fixture-harness/plan.md),
[suite decision](../../docs/design/decisions/0008-separate-bash-and-dotfiles-suites-over-shared-scenarios.md).

- `run_tart.py`: host driver (clone, boot, transfer, run, collect, clean up).
- `test_bash.py`, `test_dotfiles.py`, `conftest.py`: guest suites and HOME fixtures.
- `scenarios.py`: shared executable scenario registry.
- `test_tart_driver.py`: host-safe driver tests; no VM or network.

The Bash suite characterizes all 16 presence/absence combinations of standard
`.bash_profile`, `.bash_login`, `.profile`, and `.bashrc` files, using marker
fixtures rather than dotfiles. The dotfiles suite checks expected state using
three configurations: tracked files, tracked plus synthetic local overrides,
and tracked files with a HOME path containing spaces. Both run every registered
scenario over their configuration axes; pending scenarios are reported as
skips. System startup remains enabled on both pinned images: Homebrew is
present on macOS and absent on Ubuntu.

## Invocation inputs

The shared registry also covers actual Bash invocation controls, not IDE, SSH,
or PTY sessions. S09–S12 extend decision 0008's fixtures with explicitly named
invocation inputs: a silent `BASH_ENV` sentinel, an alternative `--rcfile`, and a
probe script, all in fixture-owned paths containing spaces. These do not replace
tracked modules, standard startup fixtures, or system files. Matched system-only
controls receive the same scenario inputs; neither harness nor profile sources
the sentinel on Bash's behalf.

| IDs | Actual invocation (probe arguments omitted) | Expected selection |
| --- | --- | --- |
| S09-env-c | `BASH_ENV=file bash -c …` | Sentinel only |
| S09-env-script | `BASH_ENV=file bash "probe script.bash" …` | Sentinel, then real script; no extra Bash runner |
| S09-env-login-c | `BASH_ENV=file bash -l -c …` | Login files, then sentinel |
| S09-env-interactive | `BASH_ENV=file bash -i -c …` | Normal rc; sentinel ignored |
| S09-env-inherited-c | Login parent → `BASH_ENV=file bash -c …` | Inherited exports; sentinel in child, no user interactive modules |
| S10-noprofile-i | `bash --noprofile -i -l -c …` | No automatic profile or user rc |
| S10-noprofile-env | `BASH_ENV=file bash --noprofile -l -c …` | Sentinel despite suppressed profiles |
| S11-norc-i | `bash --norc -i -c …` | No automatic rc or user interactive modules |
| S11-norc-login | `bash --norc -i -l -c …` | Profile can still explicitly source `.bashrc` |
| S12-rcfile-i | `bash --rcfile file -i -c …` | Alternative rc, not ordinary user rc |
| S12-rcfile-login | `bash --rcfile file -i -l -c …` | Alternative ignored; profile can source ordinary rc |
| S12-norc-rcfile | `bash --norc --rcfile file -i -c …` | Neither automatic rc runs |

Every new scenario runs over all 16 Bash startup-file combinations and all
three dotfiles configurations. Additional Bash cases explicitly source `.bashrc`
from each selected synthetic login profile to distinguish automatic selection
from profile dispatch. Sentinel records prove execution, login-before-sentinel
ordering, and exported/local state at the time of sourcing. Dotfiles assertions
distinguish actual interactive mode from whether tracked interactive modules
were selected; suppressed profiles preserve the input PATH instead of asserting
login initialization. Local overrides retain their existing module order.

## Running

Host-safe driver tests:

```bash
uv run --locked pytest tests/shell/test_tart_driver.py
```

One guest suite (`--image macos|ubuntu`, `--suite bash|dotfiles`):

```bash
uv run tests/shell/run_tart.py --image ubuntu \
  --suite dotfiles --marker characterization --artifacts "$HOME/shell-artifacts/dotfiles-ubuntu-characterization"
```

The optional `--marker` filters by `characterization` or `acceptance`; omit it
to run the entire suite. The artifacts directory must be new or empty. The exit
code is pytest's; other driver errors indicate infrastructure failure. Keep
artifacts outside the worktree, or the run records `git_dirty: true`. The
driver passes `-rs` to pytest to report skip reasons in guest output.

## Safety boundary

The guest suites run only inside a guest, never against the host shell or host
HOME. The driver:

- clones a pinned image digest under a unique run-owned name;
- runs the clone without graphics, audio, USB, or clipboard sharing;
- runs commands through the Tart guest agent;
- copies in only the startup sources and test files under test;
- deletes only its own clone, and only after confirming it is stopped.

Baseline VMs and the image cache are never modified.

Guests have no network access. The host downloads uv 0.13.7 and its official
`sha256.sum`, plus the wheels locked in `uv.lock` for the dev group, and checks
each against its pinned digest. The guest checks them again before installing.
The guest installs dependencies with
`uv export --locked` followed by
`uv pip install --offline --no-index --require-hashes` into a harness venv,
instead of `uv sync --locked`: `uv sync` still fetches the registry URLs
recorded in the lockfile, even with `--find-links`.

## Diagnostics

Each run writes these files to its artifacts directory:

- `run.json`: image digest, git revision and dirty state, SHA-256 of each
  transferred source, uv version and digest, wheel digests, pytest status,
  readiness failures, number of result symlinks skipped, and cleanup outcome.
- `host-commands.json`: every host command the driver ran.
- `tart-run.{stdout,stderr}.log`, `guest-{stdout,stderr}.log`.
- `results/pytest.xml`: JUnit XML.
- `results/shell-pytest-*/`: per-scenario observations including PATH, functions,
  aliases, shell state and raw stdout/stderr. Dotfiles runs retain candidate
  and matched system-only control artifacts.

Symlinks created by pytest under `results/` are skipped, not followed. Any other
special or unsafe archive member fails the run.

## Verified invocation-variation results

Unfiltered runs on 2026-11-13 tested committed implementation
`05e0e74d77f9a5b3b287cd9a82eab138878e8ec1`, with `git_dirty: false` and
`marker: null` in all four `run.json` files. Every run exited 0; JUnit failure
and error lists are empty, harness/cleanup errors are null, and all four
run-owned clones were confirmed absent afterward. Transient guest-agent
readiness retries recovered normally.

| Suite | Image | Characterization: passed / failed / skipped | Acceptance: passed / failed / skipped | Total: passed / failed / skipped |
| --- | --- | --- | --- | --- |
| Bash | Ubuntu (`/bin/bash` 5.2.21) | 737 / 0 / 192 | — | 737 / 0 / 192 |
| Bash | macOS (Apple `/bin/bash` 3.2.57) | 737 / 0 / 192 | — | 737 / 0 / 192 |
| Dotfiles | Ubuntu | 66 / 0 / 18 | 1386 / 0 / 565 | 1452 / 0 / 583 |
| Dotfiles | macOS | 66 / 0 / 18 | 1386 / 0 / 565 | 1452 / 0 / 583 |

Evidence directories under `~/shell-artifacts/`:

- `bash-variations-ubuntu-bash-20261113T145300`
- `bash-variations-macos-bash-20261113T145300`
- `bash-variations-ubuntu-dotfiles-20261113T145400`
- `bash-variations-macos-dotfiles-20261113T145400`

Each contains `run.json`, `results/pytest.xml`, logs, and per-shell records.
Actual-script artifacts confirm non-interactive mode, `SHLVL=1`, and the
sentinel marker. Login sentinel snapshots include `exports.local;` and the
initialized GOPATH when local modules are selected. All 36 new dotfiles
scenario/configuration pairs pass invocation assertions on each image.

The supplied main-baseline XML files in
`~/shell-artifacts/bash-noexec-base-{ubuntu,macos}-20261113` each contain 24
failures, all `test_prompt_command`. The separate correction now requires
exactly `set_prompt; _iterm2_set_repo_label`; host negative tests reject missing
or extra hooks. No baseline failures remain.

Host TDD first observed 12 failures for missing invocation scenarios, then nine
failures for invocation-unaware suite expectations. Final committed host checks:
129 passed with `uv run --locked pytest tests/shell/test_scenarios.py
tests/shell/test_tart_driver.py -q`; Ruff, generated Bash-input syntax checks,
and `git diff --check` passed. No tracked startup production code changed.

Pending reasons are unchanged. Bash skips remain 96 undefined-launch cases and
96 SSH cases per image. Dotfiles characterization skips remain nine of each;
acceptance skips are 207 undefined-launch, 207 SSH, 63 fresh-only, and 88
local-only cases. Adding assertions increases pending-case counts, not scope.

## Earlier PATH-policy evidence

Final PATH-policy guest runs tested revision
`53031888ef4a759b3b5b709f50dbf6621988a9da` without a marker, using fresh artifact
directories and `git_dirty: false`. All four runs exited 0 with no harness or
cleanup error and no run-owned Tart clone remaining. Bash has characterization
only. Dotfiles totals include characterization and acceptance:

| Suite | Image (Bash) | Characterization: passed / failed / skipped | Acceptance: passed / failed / skipped | Unfiltered total: passed / failed / skipped |
| --- | --- | --- | --- | --- |
| Bash | Ubuntu (`/bin/bash` 5.2.21) | 321 / 0 / 192 | — | 321 / 0 / 192 |
| Bash | macOS 26.6.2 (Apple `/bin/bash` 3.2.57) | 321 / 0 / 192 | — | 321 / 0 / 192 |
| Dotfiles | Ubuntu | 30 / 0 / 18 | 612 / 0 / 463 | 642 / 0 / 481 |
| Dotfiles | macOS | 30 / 0 / 18 | 612 / 0 / 463 | 642 / 0 / 481 |

The former failures are repaired: Go no longer outranks personal defaults,
nested logins do not duplicate Go, supported S04 callers retain precedence,
and active Homebrew paths are not duplicated by system and user startup.
Fresh-login tests require supplied personal, Node, Go, and Bun defaults.
Boundary tests cover repeated sourcing, surviving/removed callers, appended
paths, literal components, unknown tail multiplicity, missing directories, and
snapshot lifecycle. E1 (per-shell settings), E2 (output relative to system-only
control), and inherited non-login PATH remain green.

Raw evidence is under
`~/shell-artifacts/path-final-{ubuntu,macos}-{bash,dotfiles}-20261112T182500`,
including each `run.json`, `results/pytest.xml`, logs, and observations.
Readiness probes required transient retries, but guest execution and cleanup
succeeded. Earlier red/boundary runs used uncommitted test changes and are not
the clean final evidence above. The reviewed implementation was integrated into
`investigate-shell-initialization` after operator approval on 2026-11-12.

Characterization skips split evenly between S05/S06/S07 (expected behavior
exists but launch steps are undefined) and SSH-login/cmd/tty (no sshd
transport): 96 each for Bash, nine each for dotfiles. Acceptance also skips
assertions applicable only to fresh launches or `tracked+local`. Per image,
acceptance skips comprise 198 undefined-launch cases, 198 SSH cases, 27
fresh-noninteractive-only cases, and 40 local-only cases.

## Login PATH snapshot

[Decision 0009](../../docs/design/decisions/0009-snapshot-backed-path-reconstruction.md)
documents the bounded preservation mechanism. Login initialization captures PATH
before tool providers and composes once afterward: supported caller prefixes,
eligible home defaults, active Homebrew `bin`/`sbin`, then the observed tail.
The exact final PATH and its HOME are exported privately as
`_DOTFILES_PATH_BASELINE` and `_DOTFILES_PATH_HOME`; callers need not set them.
Non-login children inherit PATH and metadata without recomposition or refresh.

A valid same-HOME snapshot with a surviving, ordered home-managed anchor allows
recovery only before that anchor. Known baseline tail entries moved forward by
system startup are excluded; removed callers are never restored, and appended
unknown paths remain in the tail. Missing, stale, inconsistent, or anchorless
metadata initializes defaults and preserves the remaining observed PATH without
claiming to recover an unseen pre-login prefix.

Identical managed defaults, including active Homebrew entries, are represented
once. Unknown and caller multiplicity is preserved except for occurrences
already recovered into the prefix. No global deduplication, canonicalization,
literal-tilde expansion, or missing-directory removal occurs. Direct guest
composer tests preserve empty and relative components; full system startup may
normalize them before the dotfiles run.

This does not universally solve decision 0003: caller reuse of managed/system
directories, replaced/reordered PATHs, changed system providers, or launchers
discarding private state remain ambiguous. Broader application-tool ordering,
S05/S06/S07, real IDE/SSH launches, PTY behavior, and live-HOME migration are
not implemented by this repair.

## Coverage limits

The dotfiles suite covers aliases and prompt/app-config state as well as
functions, shell settings, environment and PATH; it compares startup output
with a matched system-only control and retains raw artifacts.

A PTY (pseudo-terminal) gives a process a terminal interface like the one used
by Terminal or iTerm. Our guest tests launch Bash with commands and captured
output, not an interactive terminal session. They inspect configuration but
do not exercise:

- Keyboard interaction: whether pressing Space invokes `magic-space`, or Tab
  completion works.
- Prompt behavior: whether `PROMPT_COMMAND` runs before each prompt and the
  prompt renders correctly, including Git information from `__git_ps1`.
- Job control: Ctrl-C, Ctrl-Z, and foreground/background jobs.

For example, the probe verifies that `magic-space` is bound, not that pressing
Space behaves correctly. These end-to-end checks need a PTY-backed session.

SSH scenarios are skipped. VS Code and SSH examples describe modeled shell
modes, not actual application launches or connections. Real user HOME
directories are not used.
Passing characterization does not establish full startup correctness.

## Migration

Follow [decision 0007](../../docs/design/decisions/0007-split-bashrc-from-bash-profile.md)
for entrypoint migration. Existing `~/.local/etc` symlinks to the checkout's
`etc/` already expose the new `shell-options.bash`; no extra install step is
needed for that module.
