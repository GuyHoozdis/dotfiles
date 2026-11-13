"""Shared shell startup scenario definitions for host and guest tests.

Examples describe documented use, not measured application launch chains:
https://www.gnu.org/software/bash/manual/html_node/Invoking-Bash.html
https://man.openbsd.org/ssh.1
See also docs/investigations/2026-11-10-shell-initialization/scenarios.md.
Examples illustrate shell modes; applications may use different launch chains.
"""

from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class Shell:
    """A shell to launch and the mutations applied to its environment."""

    name: str
    options: tuple[str, ...]
    launcher: str | None = None
    prepend_callers: bool = False
    source_bashrc: bool = False
    environment: tuple[tuple[str, str], ...] = ()
    bash_env: bool = False
    script: bool = False

    @property
    def interactive(self) -> bool:
        return "-i" in self.options

    @property
    def login(self) -> bool:
        return "-l" in self.options

    @property
    def reads_profile(self) -> bool:
        return self.login and "--noprofile" not in self.options

    @property
    def reads_rcfile(self) -> bool:
        return (
            self.interactive and not self.login
            and "--norc" not in self.options and "--rcfile" in self.options
        )

    @property
    def reads_bashrc(self) -> bool:
        """Tracked profile explicitly sources bashrc, independently of --norc."""
        return self.interactive and (
            self.reads_profile
            or (
                not self.login and "--norc" not in self.options
                and "--rcfile" not in self.options
            )
        )


@dataclass(frozen=True)
class Scenario:
    """A named sequence of shells, or a scenario awaiting launch steps."""

    id: str
    title: str
    shells: tuple[Shell, ...] = ()
    pending: str | None = None


STEPS_PENDING = "expected behavior defined in scenarios.md; launch steps not defined yet"
SSH_PENDING = "no sshd transport yet; see open question S5"

PARENT = Shell("parent", ("-i", "-l"))

S01 = Scenario("S01", "Fresh interactive login shell", (PARENT,))
"""Interactive login: Terminal.app/iTerm2, a Linux console, or ``bash -l`` (from documentation)."""

S02 = Scenario(
    "S02",
    "Nested interactive login shell",
    (PARENT, Shell("child", ("-i", "-l"), launcher="parent")),
)
"""Interactive login parent and child: ``exec bash -l`` or a new tmux window (from documentation).

``exec`` replaces its calling shell; a tmux server may launch windows independently.
"""

S03 = Scenario(
    "S03",
    "Interactive non-login shell",
    (PARENT, Shell("child", ("-i",), launcher="parent")),
)
"""Interactive login parent and non-login child: typing ``bash``, GNOME Terminal, or vim ``:shell`` (from documentation)."""

S04 = Scenario(
    "S04",
    "Caller prepends arbitrary directories",
    (
        PARENT,
        Shell("login", ("-i", "-l"), launcher="parent", prepend_callers=True),
        Shell("nonlogin", ("-i",), launcher="parent", prepend_callers=True),
    ),
)
"""Interactive login parent and login/non-login children.

``PATH=$PWD/test/bin:$PATH bash``, ``pipenv shell``, or ``poetry shell``
(from documentation).
"""

S05 = Scenario("S05", "Caller prepends a default-group directory", pending=STEPS_PENDING)
"""Login and non-login children planned: ``PATH=~/.local/bin:$PATH bash`` (from documentation)."""

S06 = Scenario("S06", "Activated environment or runner-supplied PATH", pending=STEPS_PENDING)
"""Login and non-login children planned.

``source .venv/bin/activate`` then ``bash``, ``$GITHUB_PATH``, or direnv
(from documentation).
"""

S07 = Scenario("S07", "VS Code/Herdr-like inherited environment", pending=STEPS_PENDING)
"""Shell modes not yet specified: VS Code integrated terminal inherits the S07-resolve
environment (from documentation).

Actual VS Code and Herdr launch chains have not been measured.
"""

S07_RESOLVE = Scenario(
    "S07-resolve",
    "VS Code environment resolver",
    (Shell("resolve", ("-i", "-l"), environment=(("VSCODE_RESOLVING_ENVIRONMENT", "1"),)),),
)
"""Interactive login shell representative of VS Code behavior, not an actual VS Code launch.

VS Code resolves a shell environment by invoking
``$SHELL -i -l -c <command>`` (from documentation).
https://code.visualstudio.com/docs/configure/command-line
Source: https://github.com/microsoft/vscode/blob/384ad082ee28da40bdcccad7e06f83efa57141e0/src/vs/platform/shell/node/shellEnv.ts#L111-L159
"""

S08_C = Scenario(
    "S08-c", "Inherited non-interactive shell", (PARENT, Shell("child", (), launcher="parent"))
)
"""Interactive login parent and non-interactive child.

``find … -exec bash -c``, ``xargs bash -c``, or entr/watch (from documentation).
"""

S08_LOGIN_C = Scenario(
    "S08-login-c",
    "Inherited non-interactive login shell",
    (PARENT, Shell("child", ("-l",), launcher="parent")),
)
"""Interactive login parent and non-interactive login child.

Crontab ``bash -lc``, Docker ``SHELL ["/bin/bash", "-l", "-c"]``, or CI
``shell: bash -l {0}`` (from documentation).
"""

S08_SOURCE_RC = Scenario(
    "S08-source-rc",
    "Inherited non-interactive shell sourcing bashrc",
    (PARENT, Shell("child", (), launcher="parent", source_bashrc=True)),
)
"""Interactive login parent and non-interactive child: explicitly ``. ~/.bashrc`` (from documentation)."""

S08_FRESH_C = Scenario("S08-fresh-c", "Fresh non-interactive shell", (Shell("fresh", ()),))
"""Non-interactive non-login shell.

``find … -exec bash -c``, ``xargs bash -c``, or entr/watch (from documentation).
"""

S08_FRESH_LOGIN_C = Scenario(
    "S08-fresh-login-c", "Fresh non-interactive login shell", (Shell("fresh", ("-l",)),)
)
"""Non-interactive login shell.

Crontab ``bash -lc``, Docker ``SHELL ["/bin/bash", "-l", "-c"]``, or CI
``shell: bash -l {0}`` (from documentation).
"""

SSH_LOGIN = Scenario("SSH-login", "SSH login", pending=SSH_PENDING)
"""Interactive login shell planned: ``ssh host`` (from documentation). Not yet measured."""

SSH_CMD = Scenario("SSH-cmd", "SSH command", pending=SSH_PENDING)
"""Remote command mode unspecified: ``ssh host 'cmd'`` or rsync/scp/Ansible/Fabric
(from documentation). Not yet measured.
"""

SSH_TTY = Scenario("SSH-tty", "SSH pseudo-terminal", pending=SSH_PENDING)
"""Remote tty mode unspecified: ``ssh -t host 'cmd'`` such as htop
(from documentation). Not yet measured.
"""

INVOCATION_SCENARIOS = (
    Scenario("S09-env-c", "Fresh command with BASH_ENV",
             (Shell("fresh", (), bash_env=True),)),
    Scenario("S09-env-script", "Actual script with BASH_ENV",
             (Shell("script", (), bash_env=True, script=True),)),
    Scenario("S09-env-login-c", "Non-interactive login with BASH_ENV",
             (Shell("fresh", ("-l",), bash_env=True),)),
    Scenario("S09-env-interactive", "Interactive shell ignores BASH_ENV",
             (Shell("fresh", ("-i",), bash_env=True),)),
    Scenario("S09-env-inherited-c", "Inherited command with BASH_ENV",
             (PARENT, Shell("child", (), launcher="parent", bash_env=True))),
    Scenario("S10-noprofile-i", "Interactive login without profiles",
             (Shell("fresh", ("--noprofile", "-i", "-l")),)),
    Scenario("S10-noprofile-env", "Non-interactive login without profiles with BASH_ENV",
             (Shell("fresh", ("--noprofile", "-l"), bash_env=True),)),
    Scenario("S11-norc-i", "Interactive non-login without automatic rc",
             (Shell("fresh", ("--norc", "-i")),)),
    Scenario("S11-norc-login", "Login profile explicitly sources rc despite --norc",
             (Shell("fresh", ("--norc", "-i", "-l")),)),
    Scenario("S12-rcfile-i", "Interactive non-login alternative rc",
             (Shell("fresh", ("--rcfile", "{rcfile}", "-i")),)),
    Scenario("S12-rcfile-login", "Login ignores alternative rc",
             (Shell("fresh", ("--rcfile", "{rcfile}", "-i", "-l")),)),
    Scenario("S12-norc-rcfile", "--norc overrides alternative rc",
             (Shell("fresh", ("--norc", "--rcfile", "{rcfile}", "-i")),)),
)

SCENARIOS = (
    S01,
    S02,
    S03,
    S04,
    S05,
    S06,
    S07,
    S07_RESOLVE,
    S08_C,
    S08_LOGIN_C,
    S08_SOURCE_RC,
    S08_FRESH_C,
    S08_FRESH_LOGIN_C,
    *INVOCATION_SCENARIOS,
    SSH_LOGIN,
    SSH_CMD,
    SSH_TTY,
)
SCENARIO = {scenario.id: scenario for scenario in SCENARIOS}


def scenario_params() -> tuple:
    """Create parametrized scenarios, skipping only those without launch steps."""
    return tuple(
        pytest.param(
            scenario,
            id=scenario.id,
            marks=pytest.mark.skip(reason=scenario.pending) if scenario.pending is not None else (),
        )
        for scenario in SCENARIOS
    )
