# Bash and dotfiles test suites Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development
> (if subagents are available) or superpowers:executing-plans to implement this
> plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single `tests/shell/test_startup.py` with two guest-native
suites, `bash` and `dotfiles`. They share one scenario registry and run every
scenario against every configuration they define.

**Architecture:**
- A shared registry describes each scenario as a tree of shell launches.
- A shared runner executes a scenario in a given HOME and records one
  observation per shell.
- The `bash` suite installs marker-only standard startup files in all 16
  presence combinations. It checks Bash's file selection against the documented
  rules.
- The `dotfiles` suite installs the real tracked files. It checks the
  user-visible end state per scenario against an approved expected-state table.
- `characterization` and `acceptance` remain pytest markers within each suite.
- Scenarios a transport can't run yet, such as SSH, are collected and skipped
  with a reason.

**Tech Stack:** Python 3 + pytest (locked via `uv`), Bash 3.2 (macOS guest) and
5.2 (Ubuntu guest), Tart guests driven by `tests/shell/run_tart.py`.

---

## Context

- User direction, 2026-11-12:
  - "For as long as we have separated init files … I want the `dotfiles` test
    suite to validate that, for all defined scenarios, the resulting state is
    what was expected."
  - "The bash test suite should only use the standard init files and run the
    defined scenarios over the various combinations of those init files."
  - "Both test suites should share the scenario definitions and run all of the
    scenarios for all of the configurations they define."
  - The user also approved skipping not-yet-runnable scenarios with a reason,
    and using `bash`/`dotfiles` as the suite names.
  - Scenarios carry real-world examples in docstrings rather than comments:
    "I would prefer that a docstring (as opposed to a code comment) be used in
    case we want to use a doc generation tool (like `sphinx`) in the future."
  - VS Code's environment resolution is a scenario of its own: "Ensure this is
    represented as one of our scenarios. Mention that it is representative of
    VSCode behavior in the scenario docstring and include a reference to the
    official documentation that confirms this behavior."
  - Decisions E1–E3 were confirmed on 2026-11-12 (see below).
- The system under test differs per suite:
  - In `bash`, Bash itself is under test. Startup files contain only markers.
  - In `dotfiles`, the tracked `etc/` files are under test. Nothing tracked may
    be replaced by a stand-in. Only `.local` overrides, which are never in the
    repo, may be synthetic.
- Expected dotfiles state is stated as user-visible state: functions, aliases,
  prompt, `shopt`, PATH, exported variables and startup output. It is not
  stated as "module X loaded". This lets modules be merged or renamed without
  rewriting tests.
- Background reading:
  - [Harness plan](../2026-11-11-shell-fixture-harness/plan.md)
  - [Scenarios](../../investigations/2026-11-10-shell-initialization/scenarios.md)
  - Decisions [0003](../../design/decisions/0003-preserve-caller-path-overrides.md),
    [0004](../../design/decisions/0004-default-path-ordering.md),
    [0005](../../design/decisions/0005-guest-native-shell-tests.md),
    [0006](../../design/decisions/0006-deduplicate-system-path-entries.md),
    [0007](../../design/decisions/0007-split-bashrc-from-bash-profile.md)
  - [Harness README](../../../tests/shell/README.md)

## Decisions (confirmed 2026-11-12)

Task 5 encodes these as acceptance expectations; Task 5b changes the dotfiles
to meet them.

| ID | Question | Decision |
|----|----------|----------|
| E1 | Should interactive non-login children get the per-shell settings in `exports.bash` (`shopt`, `bind`, HIST variables)? Today they are login-only (ADR 0007 limitation). | Yes. The user accepted the proposal. |
| E2 | Must the dotfiles add no output to stdout/stderr in any scenario? Known emitters today: `exports.bash:43` echoes the Homebrew status on every login, including `bash -l -c`; `exports.bash:132` runs `bind` in non-interactive login shells; and `app-config.bash:13` calls `brew` unconditionally (absent on Ubuntu). Bash 3.2 and the system files also print output (e.g. "no job control in this shell") that the dotfiles don't cause. | Yes, compared against a system-only control HOME for the same scenario and launch mode; keep the raw output of both as artifacts. The user's fix: "Remove (or hide behind a debugging flag) the `echo` statements. Move the `bind` and other history customization under an interactive only codepath. Check for the existence of `brew` before trying to invoke it." |
| E3 | Should guest tool availability (Homebrew, git) be a dotfiles configuration axis, or a fixed property of each image? | Fixed per image: macOS has Homebrew, Ubuntu does not. |

## File structure

| File | Responsibility |
|------|----------------|
| Create `tests/shell/scenarios.py` | Shared scenario registry: `Shell`, `Scenario`, `SCENARIOS`, and `scenario_params()` (pending scenarios become skip-marked params). |
| Create `tests/shell/probe.py` | Shared probe script, serializer, and `run_scenario(scenario, home, environment, bash, root)` returning `{shell_name: record}`. |
| Create `tests/shell/test_scenarios.py` | Host-side tests of the registry's structure. |
| Create `tests/shell/test_bash.py` | `bash` suite: 16 standard-file configurations, the file-selection model, characterization tests. |
| Create `tests/shell/test_dotfiles.py` | `dotfiles` suite: real-file configurations, expected-state table, integrity and acceptance tests (PATH tests ported from `test_startup.py`). |
| Modify `tests/shell/conftest.py` | Rename `shell_fixture` to `dotfiles_home` and install all tracked modules; add `bash_home`; register suite markers. |
| Modify `tests/shell/run_tart.py` | `--suite bash\|dotfiles`, optional `--marker`, `-rs` skip reporting, source allowlist. |
| Modify `tests/shell/test_tart_driver.py` | Driver tests for the new options and allowlist. |
| Delete `tests/shell/test_startup.py` | Contents move into the two suites. |
| Modify `pyproject.toml` | Register `bash` and `dotfiles` markers. |
| Create `etc/bashrc.d/shell-options.bash` | Task 5b: per-shell settings (`shopt`, `bind`, history) moved out of `exports.bash`; loaded by `.bashrc`, so interactive only. |
| Modify `etc/bashrc.d/exports.bash`, `etc/bashrc.bash`, `etc/bashrc.d/app-config.bash`, `etc/bashrc.d/aliases.bash` | Task 5b: remove the Homebrew echo, load `shell-options`, guard `brew` calls. |
| Docs | `tests/shell/README.md`, `scenarios.md`, ADR 0008, decision index, `docs/plans/README.md`. |

## Scenario registry

The executable scenarios mirror the existing behaviour, plus S08:

| ID | Shells (launcher → shell: options) |
|----|------------------------------------|
| S01 | pytest → `parent`: `-i -l` |
| S02 | `parent` (`-i -l`) → `child`: `-i -l` |
| S03 | `parent` (`-i -l`) → `child`: `-i` |
| S04 | `parent` (`-i -l`) → `login`: `-i -l` with callers prepended; `parent` → `nonlogin`: `-i` with callers prepended |
| S08-c | `parent` (`-i -l`) → `child`: `-c` |
| S08-login-c | `parent` (`-i -l`) → `child`: `-l -c` |
| S08-source-rc | `parent` (`-i -l`) → `child`: `-c` that runs `. ~/.bashrc` (if readable) before probing |
| S08-fresh-c | pytest → `shell`: `-c` (no initialized parent) |
| S08-fresh-login-c | pytest → `shell`: `-l -c` (no initialized parent) |
| S07-resolve | pytest → `shell`: `-i -l -c` with `VSCODE_RESOLVING_ENVIRONMENT=1` (no initialized parent): VS Code's shell-environment resolution |

S07-resolve reproduces VS Code's documented launch rather than running VS Code.
VS Code source at commit `384ad08`
([`shellEnv.ts` L111-L159](https://github.com/microsoft/vscode/blob/384ad082ee28da40bdcccad7e06f83efa57141e0/src/vs/platform/shell/node/shellEnv.ts#L111-L159)):
- argv: `$SHELL -i -l -c <command>` for Bash
- stdin ignored; stdout and stderr piped; `detached: true` (no controlling
  terminal)
- environment: VS Code's own environment plus `VSCODE_RESOLVING_ENVIRONMENT=1`

The harness matches these: stdin is `/dev/null`, the variable is set on the
launch, and every top-level launch uses `start_new_session=True`, so there's no
controlling terminal. The probe records `tty`'s result, so "no TTY" is measured
rather than assumed.

These are pending and appear as skipped:

| ID | Reason |
|----|--------|
| S05, S06 | Expected behaviour is in `scenarios.md`, but the launch steps aren't defined yet. |
| S07 | The VS Code integrated terminal, which inherits the resolved environment. Its launch steps aren't defined yet; S07-resolve covers the resolution step. |
| SSH-login (`ssh host`), SSH-cmd (`ssh host 'cmd'`), SSH-tty (`ssh -t host 'cmd'`) | No `sshd` transport yet (open question S5). |

All launches use `stdin=/dev/null`. A socket on stdin makes non-interactive
Bash read `.bashrc`; that belongs to the SSH scenarios, not these.

---

## Chunk 1: Shared foundation

### Task 1: Scenario registry

**Files:**
- Create: `tests/shell/scenarios.py`
- Test: `tests/shell/test_scenarios.py`

- [x] **Step 1: Write the failing host tests**

```python
"""Structural checks for the shared shell scenario registry (host-only)."""

import pytest

from scenarios import SCENARIO, SCENARIOS, scenario_params


def test_scenario_ids_are_unique():
    ids = [scenario.id for scenario in SCENARIOS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_shell_launchers_exist_and_precede(scenario):
    seen = set()
    for shell in scenario.shells:
        assert shell.launcher is None or shell.launcher in seen
        seen.add(shell.name)


def test_pending_scenarios_are_skipped_with_reason():
    params = {p.id: p for p in scenario_params()}
    for scenario in SCENARIOS:
        marks = [m for m in params[scenario.id].marks if m.name == "skip"]
        if scenario.pending:
            assert marks and marks[0].kwargs["reason"] == scenario.pending
        else:
            assert not marks


def test_executable_scenarios_cover_existing_and_noninteractive_cases():
    runnable = {s.id for s in SCENARIOS if not s.pending}
    assert runnable == {
        "S01", "S02", "S03", "S04", "S07-resolve", "S08-c", "S08-login-c",
        "S08-source-rc", "S08-fresh-c", "S08-fresh-login-c",
    }


def test_vscode_resolver_matches_documented_launch():
    (shell,) = SCENARIO["S07-resolve"].shells
    assert shell.launcher is None
    assert shell.options == ("-i", "-l")
    assert dict(shell.environment) == {"VSCODE_RESOLVING_ENVIRONMENT": "1"}
```

- [x] **Step 2: Run them and confirm they fail**

Run: `uv run --locked pytest tests/shell/test_scenarios.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'scenarios'`.
If the import path fails rather than the module, add `pythonpath = ["tests/shell"]`
under `[tool.pytest.ini_options]` in `pyproject.toml`.

- [x] **Step 3: Implement `tests/shell/scenarios.py`**

Each scenario is a module-level constant followed by an attribute docstring
(a string literal on the next line). Sphinx autodoc reads these. The docstring
gives the shell mode, then real-world examples of how the scenario happens.
`SCENARIOS` lists the constants. Each example is marked either *measured* or
*from documentation*, so later work knows which ones the harness has
confirmed. Starting examples:

| ID | Real-world examples |
|----|---------------------|
| S01 | Opening a Terminal.app or iTerm2 window or tab (macOS starts login shells); a Linux console or `bash -l`. |
| S02 | `exec bash -l` or `bash -l` to reload configuration; a new tmux window, since tmux starts login shells by default. |
| S03 | Typing `bash` in an existing terminal; a Linux desktop terminal such as GNOME Terminal; vim's `:shell`. |
| S04 | `PATH=$PWD/test/bin:$PATH bash`; tools that spawn a subshell with their own bin first, such as `pipenv shell` or `poetry shell`. |
| S05 | `PATH=~/.local/bin:$PATH bash` to force one user tool ahead of its default group. |
| S06 | `source .venv/bin/activate` followed by `bash`; CI runners that add to PATH through `$GITHUB_PATH`; direnv. |
| S07 | The VS Code integrated terminal: VS Code launched from the Dock starts terminals that inherit the environment S07-resolve produced. |
| S07-resolve | VS Code launched from the Dock or Finder resolving the user's environment before starting extensions and terminals. Representative of VS Code behaviour; the docstring cites the documentation and source listed under "Scenario registry". |
| S08-c / S08-fresh-c | `find … -exec bash -c '…' _ {} +`; `xargs bash -c`; `entr`/`watch` running `bash -c`. |
| S08-login-c / S08-fresh-login-c | crontab entries `bash -lc 'cmd'`; Docker `SHELL ["/bin/bash", "-l", "-c"]`; CI steps using `shell: bash -l {0}` (as setup-miniconda recommends). |
| S08-source-rc | Scripts that explicitly `. ~/.bashrc` to borrow interactive configuration. |
| SSH-login | `ssh host` |
| SSH-cmd | `ssh host 'cmd'`; rsync and scp remote sides; Ansible and Fabric. |
| SSH-tty | `ssh -t host 'cmd'`, e.g. `ssh -t host htop` |

Example shape:

```python
S08_LOGIN_C = Scenario(
    "S08-login-c", "Non-interactive login (bash -l -c)",
    (PARENT, Shell("child", ("-l",), "parent")),
)
"""Non-interactive login shell launched from an initialized session.

Real-world examples (from documentation; not measured):

- crontab entries such as ``bash -lc 'cmd'``
- Docker ``SHELL ["/bin/bash", "-l", "-c"]``
- CI steps using ``shell: bash -l {0}``

Callers want the user's environment and PATH, with no extra output.
"""

S07_RESOLVE = Scenario(
    "S07-resolve", "VS Code shell-environment resolution (bash -i -l -c)",
    (Shell("shell", ("-i", "-l"),
           environment=(("VSCODE_RESOLVING_ENVIRONMENT", "1"),)),),
)
"""Interactive login shell with no TTY, run to capture the user's environment.

Representative of VS Code behaviour. When VS Code is launched from the Dock or
Finder, it runs ``$SHELL -i -l -c <command>`` with stdin ignored, stdout and
stderr piped, no controlling terminal, and ``VSCODE_RESOLVING_ENVIRONMENT=1``
set. It then uses the printed environment for extensions and terminals.

References:

- VS Code documentation, Command Line Interface, "How do I detect when a shell
  was launched by VS Code?":
  https://code.visualstudio.com/docs/configure/command-line
  ("This will launch an **interactive login** shell and fetch its environment.")
- VS Code source, ``getUnixShellEnvironment``:
  https://github.com/microsoft/vscode/blob/384ad082ee28da40bdcccad7e06f83efa57141e0/src/vs/platform/shell/node/shellEnv.ts#L111-L159
"""
```

`SCENARIO` maps each ID to its constant, for tests that need one scenario.

The constructor calls in the block below are unchanged. Bind each one to a
constant as shown above, add its docstring, and build `SCENARIOS` from the
constants.

```python
"""Scenario definitions shared by the bash and dotfiles suites."""

from dataclasses import dataclass

import pytest

SSH_PENDING = "no sshd transport yet; see open question S5"
STEPS_PENDING = "expected behavior defined in scenarios.md; launch steps not defined yet"


@dataclass(frozen=True)
class Shell:
    name: str
    options: tuple[str, ...]
    launcher: str | None = None
    prepend_callers: bool = False
    source_bashrc: bool = False
    environment: tuple[tuple[str, str], ...] = ()

    @property
    def interactive(self) -> bool:
        return "-i" in self.options

    @property
    def login(self) -> bool:
        return "-l" in self.options


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    shells: tuple[Shell, ...] = ()
    pending: str | None = None


PARENT = Shell("parent", ("-i", "-l"))

SCENARIOS = (
    Scenario("S01", "Fresh interactive login shell", (PARENT,)),
    Scenario("S02", "Nested interactive login shell",
             (PARENT, Shell("child", ("-i", "-l"), "parent"))),
    Scenario("S03", "Interactive non-login child (bash)",
             (PARENT, Shell("child", ("-i",), "parent"))),
    Scenario("S04", "Caller prepends arbitrary directories", (
        PARENT,
        Shell("login", ("-i", "-l"), "parent", prepend_callers=True),
        Shell("nonlogin", ("-i",), "parent", prepend_callers=True),
    )),
    Scenario("S05", "Caller prepends a default-group directory", pending=STEPS_PENDING),
    Scenario("S06", "Activated environment or runner-supplied PATH", pending=STEPS_PENDING),
    Scenario("S07", "VS Code integrated terminal (inherits resolved environment)",
             pending=STEPS_PENDING),
    S07_RESOLVE,
    Scenario("S08-c", "Non-interactive non-login (bash -c)",
             (PARENT, Shell("child", (), "parent"))),
    Scenario("S08-login-c", "Non-interactive login (bash -l -c)",
             (PARENT, Shell("child", ("-l",), "parent"))),
    Scenario("S08-source-rc", "Non-interactive shell explicitly sourcing ~/.bashrc",
             (PARENT, Shell("child", (), "parent", source_bashrc=True))),
    Scenario("S08-fresh-c", "Fresh non-interactive non-login (bash -c)",
             (Shell("shell", ()),)),
    Scenario("S08-fresh-login-c", "Fresh non-interactive login (bash -l -c)",
             (Shell("shell", ("-l",)),)),
    Scenario("SSH-login", "ssh host", pending=SSH_PENDING),
    Scenario("SSH-cmd", "ssh host 'cmd'", pending=SSH_PENDING),
    Scenario("SSH-tty", "ssh -t host 'cmd'", pending=SSH_PENDING),
)

SCENARIO = {scenario.id: scenario for scenario in SCENARIOS}


def scenario_params():
    return [
        pytest.param(
            s, id=s.id,
            marks=[pytest.mark.skip(reason=s.pending)] if s.pending else [],
        )
        for s in SCENARIOS
    ]
```

- [x] **Step 4: Run the host tests and confirm they pass**

Run: `uv run --locked pytest tests/shell/test_scenarios.py -q && uv run --locked ruff check tests/shell`
Expected: all pass; Ruff clean.

- [x] **Step 5: Commit** — `test(shell): add shared scenario registry`

### Task 2: Shared probe and runner

**Files:**
- Create: `tests/shell/probe.py`
- Modify: `tests/shell/test_scenarios.py` (add a host test for script generation)

The probe runs inside each shell and records:
- `interactive`, `login`, `shlvl`, `pid` and the PATH list
- `tty`: whether stdin is a terminal (`tty -s`), so the no-TTY launches are
  measured
- `magic_space`: whether `bind -q magic-space` reports a binding (interactive
  shells only; this runs without a PTY)
- `startup_log` and `local_log`: the unexported `STARTUP_LOG` (bash-suite
  markers) and `LOCAL_LOG` (dotfiles `.local` stand-ins). The probe passes them
  to the serializer as arguments. The serializer's own environment can't see
  unexported variables, and exporting them would leak into children.
- `functions`: names from `compgen -A function`
- `aliases`: name → definition, parsed from `alias -p`
- `shopt_on`: the option-name column of `shopt -s`
- `shell_vars`: the unexported `HISTCONTROL`, `HISTSIZE` and `HISTFILESIZE`,
  passed as arguments
- `env`: a selected set of exported variables: `MYVAR`, `GOPATH`,
  `PROMPT_COMMAND`, `HISTTIMEFORMAT`, `VSCODE_RESOLVING_ENVIRONMENT`
- `marker_path`, `marker_identity` and `marker_status`, when a resolution marker
  name is supplied (dotfiles integrity)

The probe writes the `compgen` and `shopt` output to sibling files. A Python
serializer then builds `<name>.json`. Both `compgen` forms exist in Bash 3.2.

`run_scenario` generates one outer Bash script per scenario. The launcher shell
probes itself, then starts each child in registry order. Each child gets
`[PATH="$callers:$PATH"] "$bash" <options> -c "<prefix>$probe" …`, where the
prefix is `[ -r ~/.bashrc ] && . ~/.bashrc;` for `source_bashrc`. A child's
`environment` pairs are added to its launch the same way as the caller PATH.
For a top-level shell (no launcher), `run_scenario` adds them to the
subprocess environment. Each child's
stdout, stderr and exit status go to `<name>.stdout`, `<name>.stderr` and
`<name>.status`.

The top-level launch uses `stdin=subprocess.DEVNULL` and
`start_new_session=True`. Port the existing
`OBSERVE`/`OUTER`/`observe()` logic from `test_startup.py:13-221` rather than
rewriting it. The changes are:
- Generalize the `case "$scenario"` block into a generated launch sequence.
- Add the new record fields.

- [x] **Step 1: Write a failing host test**
  - Assert that `probe.launch_script(SCENARIO["S04"])` contains two child
    launches, each prefixed with the caller PATH.
  - Assert that the `S08-source-rc` script contains the `. ~/.bashrc` prefix.
  - Assert that `probe.launch_environment(SCENARIO["S07-resolve"], base)`
    returns `base` plus `VSCODE_RESOLVING_ENVIRONMENT=1`, and that scenarios
    without `environment` return `base` unchanged.
- [x] **Step 2: Run it and confirm it fails on the missing `probe` module**
- [x] **Step 3: Implement `probe.py`** (`PROBE`, `SERIALIZE`, `launch_script()`, `launch_environment()`, `run_scenario()`).
- [x] **Step 4: Run host tests and Ruff; confirm they pass**
- [x] **Step 5: Commit** — `test(shell): add shared scenario probe and runner`

---

## Chunk 2: Suites

### Task 3: `bash` suite

**Files:**
- Create: `tests/shell/test_bash.py`
- Modify: `tests/shell/conftest.py` (add a `bash_home` fixture: empty HOME under the guest root, with the environment from `_bare_shell_environment`)
- Modify: `pyproject.toml` (markers `bash`, `dotfiles`)

Each configuration is a subset of `STANDARD_FILES = (".bash_profile",
".bash_login", ".profile", ".bashrc")`, giving 16 in all. Every present file
contains only `STARTUP_LOG="${STARTUP_LOG-}<file>;"`. The variable is
deliberately unexported, so each shell's log reflects only its own startup.

The expected file-selection model follows the Bash manual:

```python
LOGIN_CHAIN = (".bash_profile", ".bash_login", ".profile")


def expected_log(present: frozenset[str], shell: Shell) -> str:
    read = []
    if shell.login:
        read += [next((f for f in LOGIN_CHAIN if f in present), None)]
    elif shell.interactive:
        read += [".bashrc" if ".bashrc" in present else None]
    if shell.source_bashrc and ".bashrc" in present:
        read += [".bashrc"]
    return "".join(f"{name};" for name in read if name)
```

Tests (`@pytest.mark.bash`, `@pytest.mark.characterization`, parametrized over
`scenario_params()` × the 16 configurations):
- `test_startup_files_read`: each shell's `startup_log` equals
  `expected_log(...)`, and each shell's `interactive`/`login` flags match the
  registry.
- `test_nonlogin_shell_keeps_launched_path`: each non-login shell's PATH equals
  its launcher's PATH, with callers prepended when `prepend_callers` is set.
  Login PATH is recorded but not asserted, because it is system-specific.
- Move `test_empty_home_child_bash_modes_and_environment` (the `MYVAR`
  inheritance and mutation checks) from `test_startup.py` unchanged.
- Delete the three marker-file tests and `test_noninteractive_bash_reads_only_login_files`;
  the model subsumes them.

- [x] **Step 1: Write `test_bash.py`.** Run Ruff and the host tests.
- [x] **Step 2: Commit** — `test(shell): add bash startup-file suite`
- [x] **Step 3: Run on the guests in Task 6 Step 6.** The runner's source
  allowlist needs both suite files to exist first.
  - Expected: all runnable cases pass, and the 6 pending scenarios × 16
    configurations are reported as skipped with their reasons.
  - Any mismatch is a finding about Bash or the guest's system files. Record it
    rather than changing the model to match.

### Task 4: `dotfiles` fixture and integrity

**Files:**
- Modify: `tests/shell/conftest.py`
  - Rename `shell_fixture` to `dotfiles_home`.
  - Install every tracked `etc/bashrc.d/*.bash` module except `*.local.bash`
    (today: `aliases`, `app-config`, `exports`, `functions`, `prompt`), so the
    module Task 5b adds is picked up without editing the fixture. Personal
    `.local` overrides in a working tree must never be installed.
  - Accept a `configuration` param: `tracked`, `tracked+local`, or
    `tracked-home-spaces`. The last keeps the existing coverage for a HOME
    path containing spaces.
  - Provide a matching system-only control HOME for E2 output comparison.
- Create: `tests/shell/test_dotfiles.py`

Configurations:
- `tracked`: the real `bash_profile.bash`, `bashrc.bash` and all modules.
- `tracked+local`: the same, plus a synthetic `<module>.local.bash` for each
  module. Each one defines `dotfiles_local_<module>` and appends
  `<module>.local;` to an unexported `LOCAL_LOG`. `aliases.local.bash` also
  defines `alias ll=local-override`.

Move `check_integrity` and the system-only control from `test_startup.py`,
adapting the field set to the new probe. Mark them
`@pytest.mark.dotfiles @pytest.mark.characterization`, parametrized over
scenarios × configurations.

- [x] **Step 1: Port the integrity tests to the new runner.** Run Ruff and the
  host tests.
- [x] **Step 2: Commit** — `test(shell): run dotfiles integrity over shared scenarios`
- [x] **Step 3: Run on the guests in Task 6 Step 6**, using
  `--marker characterization`.
  - Expected: pass. A failure here is a harness defect and must be fixed
    before the Task 5 acceptance run.

### Task 5: `dotfiles` expected-state acceptance

**Precondition:** decisions E1–E3 are confirmed (done 2026-11-12).

**Files:** Modify `tests/shell/test_dotfiles.py`

Expected state per shell kind. S07-resolve is an interactive login shell.

| Observation | interactive login | interactive non-login | non-interactive login (`-l -c`) | non-interactive non-login (`-c`) | `-c` sourcing `.bashrc` |
|---|---|---|---|---|---|
| Functions `codetree`, `jqless`, `set_prompt` | yes | yes | no | no | no (the `.bashrc` interactive guard returns) |
| Alias `ll` | yes | yes | no | no | no |
| `PROMPT_COMMAND == set_prompt` | yes | yes | not asserted (exported, inherited) | not asserted | not asserted |
| `GOPATH == $HOME/.go` | yes | inherited from parent | yes | inherited | inherited |
| `shopt` `nocaseglob`, `cdspell`; `HISTCONTROL`, `HISTSIZE`, `HISTFILESIZE` | yes | yes (E1) | same as the system-only control (E2: interactive only) | same as the control | same as the control |
| `magic_space` (`bind Space:magic-space`) | yes | yes (E1) | not probed (non-interactive) | not probed | not probed |
| Startup output beyond the system-only control | none (E2) | none (E2) | none (E2) | none (E2) | none (E2) |
| Fresh `-c` only: `GOPATH` unset, PATH unchanged from the launch PATH | — | — | — | yes | — |
| `tracked+local` only: `dotfiles_local_<module>` for every module the shell loads; `LOCAL_LOG` lists each once, in loader order; `ll` is not `local-override` (tracked loads after `.local`) | yes | yes (no `exports` entry) | `exports` only | none | none |

Coverage limits to state in the README, since these need a PTY transport:
- keyboard interaction with readline bindings (the probe checks that
  `magic-space` is bound, not that it behaves)
- prompt rendering, including `__git_ps1`
- `PROMPT_COMMAND` execution

Encode the table as `EXPECTED` keyed by shell kind. Write one test per
observation row, parametrized over scenarios × configurations, so that each
failure names a single behaviour.

Port these PATH-policy tests from `test_startup.py`, keyed by scenario rather
than hard-coded names:
- `test_managed_precedence`
- `test_fresh_managed_paths_are_not_duplicated`
- `test_child_adds_no_managed_duplicates`
- `test_callers_precede_managed_paths`
- `test_nonlogin_child_keeps_inherited_path`

Delete `test_bash_profile_loads_each_module_once_and_ignores_fallbacks` and
`test_noninteractive_shell_has_no_user_functions`; the table rows cover them.
Keep the stale `.bash_login` and `.profile` precedence check as a `tracked`
configuration detail: write both files with a `LOCAL_LOG` entry and assert
they never appear.

- [x] **Step 1: Write the acceptance tests**
- [x] **Step 2: Run the `dotfiles` suite with `-m acceptance` on both guests**
  - Expected: the PATH-policy failures from the harness README remain.
  - New expected failures, before Task 5b:
    - E1: interactive non-login children lack the `shopt` and HIST settings.
    - E2: the Homebrew echo on every login shell (both guests); `bind`
      warnings in non-interactive login shells; on Ubuntu, `brew: command
      not found` from `app-config.bash`.
    - E2: non-interactive login shells have the `shopt` and HIST settings.
  - Record every failure with its reason. Don't weaken an expectation to make
    it pass.
  - If the E2 test reports an emitter not listed above, stop and report it to
    the user before Task 5b changes anything for it.
- [x] **Step 3: Commit** — `test(shell): assert dotfiles expected state for all scenarios`

### Task 5b: Interactive-only settings and silent startup (E1, E2)

**Files:**
- Create: `etc/bashrc.d/shell-options.bash`
- Modify: `etc/bashrc.d/exports.bash`, `etc/bashrc.bash`,
  `etc/bashrc.d/app-config.bash:13`, `etc/bashrc.d/aliases.bash:14,32`
- Modify: the loader comment at the top of each `etc/bashrc.d/*.bash` module

The Task 5 failures are the failing tests for this task.

- [x] **Step 1: Move the per-shell settings.** Move these from `exports.bash`
  into the new `shell-options.bash`, unchanged:
  - `shopt -s nocaseglob`, `cdspell`, `dirspell`, `globstar` (lines 22–25)
  - the whole "Customize History" section (lines 125–end): `bind
    Space:magic-space`, `HISTTIMEFORMAT`, `HISTCONTROL`, `HISTSIZE`,
    `HISTFILESIZE`, `histappend`, `HISTIGNORE`, `cmdhist`

  Exported variables keep their `export`. `exports.bash` keeps `LANG`,
  `LC_ALL`, Homebrew, the version managers, PATH, `EDITOR` and `GOPATH`.
- [x] **Step 2: Load it from `.bashrc` first.** Change the loop in
  `etc/bashrc.bash` to `{shell-options,aliases,functions,app-config,prompt}`.
  It sits after the interactive guard, so it is interactive only. A
  `shell-options.local.bash` override works like the others.
- [x] **Step 3: Remove the Homebrew echo.** Replace `exports.bash:43` with a
  bare `initialize_homebrew`. Removing the echo is enough, with no new flag:
  the existing `~/.local/etc/bash_profile.debug` flag turns on `set -x`, which
  already traces `initialize_homebrew`.
- [x] **Step 4: Guard `brew`.** Run each `brew` call only when
  `command -v brew >/dev/null` succeeds:
  - `app-config.bash:13` (completion)
  - `aliases.bash:14` and `:32` (`gls`, `gtar`)
- [x] **Step 5: Update the loader comments** in each module so the listed
  order matches the code: `exports` at login; `shell-options`, `aliases`,
  `functions`, `app-config`, `prompt` per interactive shell.
- [x] **Step 6: Run the `dotfiles` acceptance suite on both guests.**
  Expected: the E1 and E2 failures are gone; only the PATH-policy failures
  from the harness README remain.
- [x] **Step 7: Commit** — `fix(bash): keep per-shell settings and output out of non-interactive shells`

---

## Chunk 3: Runner, cleanup, docs

### Task 6: Runner suite selection

**Files:**
- Modify: `tests/shell/run_tart.py:146-155` (`parse_args`), `:800-808` (pytest command), `SOURCE_FILES` (~line 37)
- Test: `tests/shell/test_tart_driver.py`

- [x] **Step 1: Write failing driver tests**
  - `--suite` accepts only `bash` and `dotfiles`.
  - `--marker` is optional, and limited to `characterization` and `acceptance`.
  - The guest pytest command selects `tests/shell/test_<suite>.py`, passes
    `-m <marker>` only when given, and includes `-rs`.
  - `SOURCE_FILES` includes `scenarios.py`, `probe.py`, both suite files and
    every tracked `etc/bashrc.d/*.bash` module (from `git ls-files`, excluding
    `*.local.bash`, so Task 5b's module is included and personal overrides
    never are), and excludes `test_startup.py`.
- [x] **Step 2: Run and confirm they fail.** Command: `uv run --locked pytest tests/shell/test_tart_driver.py -q`
- [x] **Step 3: Implement**
- [x] **Step 4: Run and confirm they pass**, along with Ruff and `git diff --check`
- [x] **Step 5: Commit** — `feat(shell): select bash or dotfiles suite in tart runner`
- [x] **Step 6: Run the deferred guest checks from Tasks 3 and 4** on both
  images. Use fresh artifact directories and confirm cleanup.

Order of work: Tasks 1–4 (host-verified), then Task 6 (including the guest
runs), then Task 5, Task 5b, Task 7, Task 8 and Task 9.

### Task 7: Remove `test_startup.py`

- [x] Confirm that every test in it has been moved or explicitly retired
  (Tasks 3–5), then delete it.
- [x] Commit — `test(shell): retire combined startup test module`

### Task 8: Full verification

- [x] Run each of the following four times with fresh artifact directories:
  `{ubuntu, macos} × {bash, dotfiles}`, with no `--marker`.
- [x] Confirm `tart list` shows only the two local base images and reusable
  OCI cache entries; no run-owned clones remain.
- [x] Record the counts: passed, failed and skipped per marker. Also record
  each failure with its reason.

### Task 9: Docs and ADR

- [x] **ADR 0008:** "Separate Bash and dotfiles suites over shared scenarios".
  - Cover the context, decision, alternatives and consequences.
  - Alternatives: one combined suite; per-suite scenario lists.
  - Source: the user quotes from the Context section.
  - Add it to `docs/design/decisions/README.md`.
- [x] **`tests/shell/README.md`:** the two suites, the run commands, the results
  table per suite, skip reasons, and updated coverage limits. Aliases, prompt
  and app-config are now covered; SSH is skipped.
- [x] **`scenarios.md`:**
  - Add the S07-resolve and S08 sub-IDs and the SSH rows.
  - Point to `tests/shell/scenarios.py` as the executable definition.
- [x] **ADR 0007:** the branch is unpublished, so update its "Known limitations"
  directly. The per-shell settings now live in `shell-options.bash`;
  `exports.local.bash` remains login-only.
- [x] **Install notes:** none needed. `~/.local/etc` is a symlink to the
  checkout's `etc/` (verified on the host), so `shell-options.bash` is present
  once the branch is merged. Mention this in the README's migration note.
- [x] **`docs/plans/README.md`:** add this plan.
- [x] **Commit** — `docs(shell): document bash and dotfiles suites`
