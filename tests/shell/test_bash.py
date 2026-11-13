"""Characterize Bash's startup-file selection across registered scenarios."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import scenarios
from probe import run_scenario
from scenarios import Shell


BARE_SERIALIZER = r"""
import json, os, sys
output, interactive, login, level, pid, helper, codetree, jqless = sys.argv[1:]
with open(output, "w", encoding="utf-8") as stream:
    json.dump({
        "path": os.environ["PATH"].split(":"),
        "interactive": interactive == "true",
        "login": login == "true",
        "shlvl": int(level),
        "pid": int(pid),
        "myvar": os.environ.get("MYVAR"),
        "startup_marker": os.environ.get("SHELL_STARTUP_MARKER"),
        "profile_marker": os.environ.get("SHELL_PROFILE_MARKER"),
        "login_marker": os.environ.get("SHELL_LOGIN_MARKER"),
        "exists_in_path": helper == "true",
        "user_functions": {
            "codetree": codetree == "true",
            "jqless": jqless == "true",
        },
    }, stream)
"""

BARE_CAPTURE = r"""
if [ "$0" = "mutate" ]; then
    MYVAR=child
    PATH="$HOME/child-only:$PATH"
    export MYVAR PATH
fi
case $- in *i*) interactive=true ;; *) interactive=false ;; esac
if shopt -q login_shell; then login=true; else login=false; fi
if declare -F exists_in_path >/dev/null; then helper=true; else helper=false; fi
if declare -F codetree >/dev/null; then codetree=true; else codetree=false; fi
if declare -F jqless >/dev/null; then jqless=true; else jqless=false; fi
"$1" -c "$2" "$3" "$interactive" "$login" "$SHLVL" "$$" "$helper" "$codetree" "$jqless"
"""

BARE_PARENT = r"""
python=$1
bash=$2
serializer=$3
capture=$4
root=$5
test_bin=$6
export MYVAR=parent
"$bash" -i -c "$capture" mutate "$python" "$serializer" "$root/mutated.json" \
    >"$root/mutated.stdout" 2>"$root/mutated.stderr"
"$bash" -i -l -c "$capture" login "$python" "$serializer" "$root/login.json" \
    >"$root/login.stdout" 2>"$root/login.stderr"
MYVAR=42 PATH="$test_bin:$PATH" "$bash" -i -c "$capture" prefix "$python" \
    "$serializer" "$root/prefix.json" \
    >"$root/prefix.stdout" 2>"$root/prefix.stderr"
case $- in *i*) interactive=true ;; *) interactive=false ;; esac
if shopt -q login_shell; then login=true; else login=false; fi
if declare -F exists_in_path >/dev/null; then helper=true; else helper=false; fi
if declare -F codetree >/dev/null; then codetree=true; else codetree=false; fi
if declare -F jqless >/dev/null; then jqless=true; else jqless=false; fi
"$python" -c "$serializer" "$root/parent.json" "$interactive" "$login" \
    "$SHLVL" "$$" "$helper" "$codetree" "$jqless"
"""

STANDARD_FILES = (".bash_profile", ".bash_login", ".profile", ".bashrc")
LOGIN_CHAIN = (".bash_profile", ".bash_login", ".profile")
PRESENT_CONFIGURATIONS = tuple(
    frozenset(
        filename for bit, filename in enumerate(STANDARD_FILES) if mask & (1 << bit)
    )
    for mask in range(1 << len(STANDARD_FILES))
)


def expected_log(present: frozenset[str], shell: Shell) -> str:
    """Return the startup file log expected for one shell mode."""
    loaded = []
    if shell.login:
        login_file = next(
            (filename for filename in LOGIN_CHAIN if filename in present), None
        )
        if login_file is not None:
            loaded.append(login_file)
    elif shell.interactive and ".bashrc" in present:
        loaded.append(".bashrc")
    if shell.source_bashrc and ".bashrc" in present:
        loaded.append(".bashrc")
    return "".join(f"{filename};" for filename in loaded)


def _write_startup_files(home: Path, present: frozenset[str]) -> None:
    for filename in present:
        (home / filename).write_text(
            f'STARTUP_LOG="${{STARTUP_LOG-}}{filename};"',
            encoding="utf-8",
        )


@pytest.mark.bash
@pytest.mark.characterization
@pytest.mark.parametrize("scenario", scenarios.scenario_params())
@pytest.mark.parametrize(
    "present",
    PRESENT_CONFIGURATIONS,
    ids=lambda present: "+".join(sorted(present)) or "empty",
)
def test_startup_files_read(scenario, present, bash_home):
    _write_startup_files(bash_home["home"], present)
    records = run_scenario(
        scenario,
        bash_home["home"],
        bash_home["environment"],
        bash_home["bash"],
        bash_home["root"] / "probe",
    )

    for shell in scenario.shells:
        record = records[shell.name]
        assert record["startup_log"] == expected_log(present, shell)
        assert record["interactive"] is shell.interactive
        assert record["login"] is shell.login


@pytest.mark.bash
@pytest.mark.characterization
@pytest.mark.parametrize("scenario", scenarios.scenario_params())
@pytest.mark.parametrize(
    "present",
    PRESENT_CONFIGURATIONS,
    ids=lambda present: "+".join(sorted(present)) or "empty",
)
def test_nonlogin_shell_keeps_launched_path(scenario, present, bash_home):
    _write_startup_files(bash_home["home"], present)
    root = bash_home["root"] / "probe"
    records = run_scenario(
        scenario,
        bash_home["home"],
        bash_home["environment"],
        bash_home["bash"],
        root,
    )

    for shell in scenario.shells:
        if shell.login:
            continue
        launched_path = (
            records[shell.launcher]["path"]
            if shell.launcher is not None
            else bash_home["environment"]["PATH"].split(":")
        )
        if shell.prepend_callers:
            launched_path = [
                str(root / "caller one/bin"),
                str(root / "caller two/bin"),
                *launched_path,
            ]
        assert records[shell.name]["path"] == launched_path


@pytest.mark.bash
@pytest.mark.characterization
def test_empty_home_child_bash_modes_and_environment(bash_home) -> None:
    tmp_path = bash_home["root"]
    home = bash_home["home"]
    shell_bash = bash_home["bash"]
    for name in (".bashrc", ".bash_profile", ".bash_login", ".profile"):
        assert not (home / name).exists()
    test_bin = tmp_path / "test/bin"
    test_bin.mkdir(parents=True)

    environment = bash_home["environment"]
    result = subprocess.run(
        [
            os.path.abspath(shell_bash),
            "-i",
            "-c",
            BARE_PARENT,
            "parent",
            os.path.abspath(sys.executable),
            os.path.abspath(shell_bash),
            BARE_SERIALIZER,
            BARE_CAPTURE,
            str(tmp_path),
            str(test_bin),
        ],
        env=environment,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    (tmp_path / "outer.stdout").write_text(result.stdout, encoding="utf-8")
    (tmp_path / "outer.stderr").write_text(result.stderr, encoding="utf-8")

    records = {
        name: json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("parent", "mutated", "login", "prefix")
    }
    assert (records["parent"]["interactive"], records["parent"]["login"]) == (
        True,
        False,
    )
    assert (records["mutated"]["interactive"], records["mutated"]["login"]) == (
        True,
        False,
    )
    assert (records["login"]["interactive"], records["login"]["login"]) == (True, True)
    assert (records["prefix"]["interactive"], records["prefix"]["login"]) == (
        True,
        False,
    )
    assert records["parent"]["myvar"] == "parent"
    assert records["mutated"]["myvar"] == "child"
    assert records["login"]["myvar"] == "parent"
    assert records["prefix"]["myvar"] == "42"
    assert records["mutated"]["path"][0] == str(home / "child-only")
    assert records["prefix"]["path"][0] == str(test_bin)
    assert records["parent"]["path"] == environment["PATH"].split(":")
    assert records["parent"]["startup_marker"] is None
    assert all(record["startup_marker"] is None for record in records.values())
    assert all(record["exists_in_path"] is False for record in records.values())
    assert all(
        record["user_functions"] == {"codetree": False, "jqless": False}
        for record in records.values()
    )
    assert records["parent"]["profile_marker"] is None
    assert records["parent"]["login_marker"] is None
