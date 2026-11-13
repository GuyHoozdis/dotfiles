"""Integrity checks for the tracked dotfiles across shared Bash scenarios."""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

import scenarios
from conftest import _create_dotfiles_home
from probe import PROBE, SERIALIZE, run_scenario


DOTFILES_CONFIGURATIONS = ("tracked", "tracked+local", "tracked-home-spaces")
MODULE_LOAD_ORDER = ("exports", "shell-options", "aliases", "functions", "app-config", "prompt")

# Values describe startup policy, not the current implementation.
EXPECTED = {
    "interactive-login": {
        "interactive": True,
        "gopath": "home",
        "modules": MODULE_LOAD_ORDER,
    },
    "interactive-nonlogin": {
        "interactive": True,
        "gopath": "inherited",
        "modules": MODULE_LOAD_ORDER[1:],
    },
    "noninteractive-login": {
        "interactive": False,
        "gopath": "home",
        "modules": ("exports",),
    },
    "noninteractive-nonlogin": {
        "interactive": False,
        "gopath": "inherited",
        "modules": (),
    },
    "source-bashrc": {
        "interactive": False,
        "gopath": "inherited",
        "modules": (),
    },
}


def _shell_kind(shell) -> str:
    if shell.source_bashrc:
        assert not shell.interactive and not shell.login
        return "source-bashrc"
    mode = "interactive" if shell.reads_bashrc else "noninteractive"
    return f"{mode}-{'login' if shell.reads_profile else 'nonlogin'}"


def _normalize_startup_stderr(output: str) -> str:
    return re.sub(
        r"(?m)^(bash: cannot set terminal process group \()[0-9]+"
        r"(\): Inappropriate ioctl for device)$",
        r"\g<1><pid>\g<2>",
        output,
    )


def _expected_local_log(configuration: dict, shell) -> str:
    if configuration["configuration"] != "tracked+local":
        return ""
    loaded = EXPECTED[_shell_kind(shell)]["modules"]
    return "".join(f"{module}.local;" for module in loaded)


def _check_integrity(records: dict, fixture: dict, scenario) -> None:
    for shell in scenario.shells:
        record = records[shell.name]
        assert set(record) == {
            "path",
            "interactive",
            "login",
            "shlvl",
            "pid",
            "tty",
            "magic_space",
            "startup_log",
            "local_log",
            "functions",
            "aliases",
            "shopt_on",
            "histcontrol",
            "histsize",
            "histfilesize",
            "shell_vars",
            "env",
            "invocation",
            "marker_path",
            "marker_identity",
            "marker_status",
            "status",
            "stdout",
            "stderr",
        }
        assert isinstance(record["status"], int)
        assert record["status"] == 0, record
        assert record["interactive"] is shell.interactive
        assert record["login"] is shell.login
        assert record["shlvl"] == (1 if shell.launcher is None else 2)
        assert isinstance(record["pid"], int) and record["pid"] > 0
        assert isinstance(record["marker_path"], str)
        assert isinstance(record["marker_identity"], str)
        assert isinstance(record["marker_status"], int)
        assert isinstance(record["tty"], bool)
        assert isinstance(record["magic_space"], bool)
        assert isinstance(record["path"], list)
        assert all(isinstance(entry, str) for entry in record["path"])
        assert isinstance(record["functions"], list)
        assert all(isinstance(function, str) for function in record["functions"])
        assert "probe_shell" not in record["functions"]
        assert isinstance(record["aliases"], dict)
        assert all(
            isinstance(name, str) and isinstance(value, str)
            for name, value in record["aliases"].items()
        )
        assert isinstance(record["shopt_on"], list)
        assert all(isinstance(option, str) for option in record["shopt_on"])
        assert all(
            isinstance(record[field], str)
            for field in ("startup_log", "local_log", "histcontrol", "histsize", "histfilesize")
        )
        assert record["local_log"] == _expected_local_log(fixture, shell)
        assert record["shell_vars"] == {
            "STARTUP_LOG": record["startup_log"],
            "LOCAL_LOG": record["local_log"],
            "HISTCONTROL": record["histcontrol"],
            "HISTSIZE": record["histsize"],
            "HISTFILESIZE": record["histfilesize"],
        }
        assert set(record["env"]) == {
            "MYVAR",
            "GOPATH",
            "PROMPT_COMMAND",
            "HISTTIMEFORMAT",
            "VSCODE_RESOLVING_ENVIRONMENT",
        }
        assert all(
            value is None or isinstance(value, str) for value in record["env"].values()
        )
        assert set(record["invocation"]) == {
            "env", "startup_before", "local_before", "gopath_before", "rcfile",
        }
        assert all(
            value is None or isinstance(value, str)
            for value in record["invocation"].values()
        )
        assert isinstance(record["stdout"], str) and isinstance(record["stderr"], str)

        modules_loaded = EXPECTED[_shell_kind(shell)]["modules"]
        for module in modules_loaded:
            function = fixture["local_functions"].get(module)
            if function is not None:
                assert function in record["functions"]
        matching = [
            str(Path(entry) / fixture["marker"])
            for entry in record["path"]
        ]
        expected = next((path for path in matching if path in fixture["identities"]), "")
        assert record["marker_path"] == expected
        if expected:
            assert record["marker_status"] == 0
            assert record["marker_identity"] == fixture["identities"][expected]
            assert Path(expected).is_file()
        else:
            assert record["marker_status"] == 127
            assert record["marker_identity"] == ""
            marker = Path(fixture["managed"][0]) / fixture["marker"]
            assert marker.is_file()
            assert os.access(marker, os.X_OK)
            identity = fixture["identities"][str(marker)]
            assert marker.read_bytes() == (
                f"#!/bin/sh\nprintf '%s\\n' '{identity}'\n".encode("utf-8")
            )


@pytest.mark.dotfiles
@pytest.mark.characterization
@pytest.mark.parametrize("scenario", scenarios.scenario_params())
@pytest.mark.parametrize(
    "dotfiles_home",
    DOTFILES_CONFIGURATIONS,
    indirect=True,
)
def test_dotfiles_integrity_and_system_only_control(
    scenario,
    dotfiles_home: dict,
) -> None:
    candidate = run_scenario(
        scenario,
        dotfiles_home["home"],
        dotfiles_home["environment"],
        dotfiles_home["bash"],
        dotfiles_home["root"] / "candidate",
    )
    _check_integrity(candidate, dotfiles_home, scenario)

    control_root = dotfiles_home["root"] / "system-control"
    control_home_name = (
        "home with spaces"
        if dotfiles_home["configuration"] == "tracked-home-spaces"
        else "home"
    )
    control_home = control_root / control_home_name
    control_home.mkdir(parents=True)
    assert all(
        not (control_home / filename).exists()
        for filename in (".bash_profile", ".bash_login", ".profile", ".bashrc")
    )
    control = {
        **dotfiles_home,
        "configuration": "tracked",
        "local_functions": {},
        "root": control_root,
        "home": control_home,
        "environment": {
            **dotfiles_home["environment"],
            "HOME": str(control_home),
            "HISTFILE": str(control_root / "history"),
        },
    }
    control_records = run_scenario(
        scenario,
        control_home,
        control["environment"],
        control["bash"],
        control_root / "probe",
    )
    _check_integrity(control_records, control, scenario)


@pytest.fixture(scope="class")
def acceptance_records(scenario, dotfiles_home):
    """Keep candidate and system-only artifacts for every acceptance assertion."""
    home = dotfiles_home["home"]
    if dotfiles_home["configuration"] == "tracked":
        for filename in (".bash_login", ".profile"):
            (home / filename).write_text(
                f'LOCAL_LOG="${{LOCAL_LOG-}}{filename};"\n', encoding="utf-8"
            )

    candidate = run_scenario(
        scenario,
        home,
        dotfiles_home["environment"],
        dotfiles_home["bash"],
        dotfiles_home["root"],
    )
    control_root = dotfiles_home["root"] / "system-control"
    control_home = control_root / home.name
    control_home.mkdir(parents=True)
    control = run_scenario(
        scenario,
        control_home,
        {
            **dotfiles_home["environment"],
            "HOME": str(control_home),
            "HISTFILE": str(control_root / "history"),
        },
        dotfiles_home["bash"],
        control_root / "probe",
    )
    for shell in scenario.shells:
        assert candidate[shell.name]["status"] == 0, candidate[shell.name]
        assert control[shell.name]["status"] == 0, control[shell.name]
    return candidate, control


def _managed_entries(fixture: dict) -> list[str]:
    return fixture["managed"] + [
        str(fixture["home"] / ".docker/bin"),
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
    ]


@pytest.mark.dotfiles
@pytest.mark.acceptance
@pytest.mark.parametrize("scenario", scenarios.scenario_params(), scope="class")
@pytest.mark.parametrize(
    "dotfiles_home", DOTFILES_CONFIGURATIONS, indirect=True, scope="class"
)
class TestExpectedState:
    @pytest.fixture(scope="class")
    def dotfiles_home(self, request, scenario, shell_tmp_factory, shell_bash):
        return _create_dotfiles_home(request.param, shell_tmp_factory, shell_bash)

    def test_user_functions(self, scenario, acceptance_records):
        candidate, _ = acceptance_records
        for shell in scenario.shells:
            expected = EXPECTED[_shell_kind(shell)]["interactive"]
            functions = candidate[shell.name]["functions"]
            for name in ("codetree", "jqless", "set_prompt"):
                assert (name in functions) is expected, (shell.name, name)

    def test_invocation_inputs(self, scenario, dotfiles_home, acceptance_records):
        candidate, control = acceptance_records
        for shell in scenario.shells:
            env_loaded = shell.bash_env and not shell.interactive
            for records in (candidate, control):
                record = records[shell.name]
                invocation = record["invocation"]
                assert invocation["env"] == ("loaded" if env_loaded else None)
                assert invocation["rcfile"] == ("loaded" if shell.reads_rcfile else None)
                assert record["startup_log"] == (
                    "BASH_ENV;" if env_loaded else "rcfile;" if shell.reads_rcfile else ""
                )
                if env_loaded:
                    assert invocation["startup_before"] == ""
                    assert invocation["local_before"] == record["local_log"]
                    assert invocation["gopath_before"] == (record["env"]["GOPATH"] or "")
            if not shell.reads_profile:
                expected_path = (
                    candidate[shell.launcher]["path"]
                    if shell.launcher else dotfiles_home["initial_path"]
                )
                if shell.prepend_callers:
                    expected_path = dotfiles_home["callers"] + expected_path
                assert candidate[shell.name]["path"] == expected_path, shell.name

    def test_ll_alias(self, scenario, acceptance_records):
        candidate, _ = acceptance_records
        for shell in scenario.shells:
            expected = EXPECTED[_shell_kind(shell)]["interactive"]
            assert ("ll" in candidate[shell.name]["aliases"]) is expected, shell.name

    def test_prompt_command(self, scenario, acceptance_records):
        candidate, _ = acceptance_records
        for shell in scenario.shells:
            if EXPECTED[_shell_kind(shell)]["interactive"]:
                assert candidate[shell.name]["env"]["PROMPT_COMMAND"] == (
                    "set_prompt; _iterm2_set_repo_label"
                ), shell.name

    def test_gopath(self, scenario, dotfiles_home, acceptance_records):
        candidate, _ = acceptance_records
        for shell in scenario.shells:
            if EXPECTED[_shell_kind(shell)]["gopath"] == "home":
                expected = str(dotfiles_home["home"] / ".go")
            elif shell.launcher is not None:
                expected = candidate[shell.launcher]["env"]["GOPATH"]
            else:
                expected = dotfiles_home["environment"].get("GOPATH")
            assert candidate[shell.name]["env"]["GOPATH"] == expected, shell.name

    def test_fresh_noninteractive_launch_environment(
        self, scenario, dotfiles_home, acceptance_records
    ):
        if scenario != scenarios.S08_FRESH_C:
            pytest.skip("only the fresh noninteractive launch has no parent")
        candidate, _ = acceptance_records
        record = candidate[scenario.shells[0].name]
        assert record["env"]["GOPATH"] is None
        assert record["path"] == dotfiles_home["initial_path"]

    @pytest.mark.parametrize("option", ("nocaseglob", "cdspell"))
    def test_shopt(self, scenario, acceptance_records, option):
        candidate, control = acceptance_records
        for shell in scenario.shells:
            actual = option in candidate[shell.name]["shopt_on"]
            expected = (
                True
                if EXPECTED[_shell_kind(shell)]["interactive"]
                else option in control[shell.name]["shopt_on"]
            )
            assert actual is expected, (shell.name, option)

    @pytest.mark.parametrize(
        ("field", "interactive_value"),
        (
            ("histcontrol", "erasedups:ignoreboth"),
            ("histsize", "100000"),
            ("histfilesize", "100000"),
        ),
    )
    def test_history(self, scenario, acceptance_records, field, interactive_value):
        candidate, control = acceptance_records
        for shell in scenario.shells:
            expected = (
                interactive_value
                if EXPECTED[_shell_kind(shell)]["interactive"]
                else control[shell.name][field]
            )
            assert candidate[shell.name][field] == expected, (shell.name, field)

    def test_magic_space(self, scenario, acceptance_records):
        candidate, _ = acceptance_records
        for shell in scenario.shells:
            if EXPECTED[_shell_kind(shell)]["interactive"]:
                assert candidate[shell.name]["magic_space"] is True, shell.name

    @pytest.mark.parametrize("stream", ("stdout", "stderr"))
    def test_startup_output_matches_system(self, scenario, acceptance_records, stream):
        candidate, control = acceptance_records
        for shell in scenario.shells:
            actual = candidate[shell.name][stream]
            expected = control[shell.name][stream]
            if stream == "stderr":
                actual = _normalize_startup_stderr(actual)
                expected = _normalize_startup_stderr(expected)
            assert actual == expected, shell.name

    def test_local_module_functions(self, scenario, dotfiles_home, acceptance_records):
        if dotfiles_home["configuration"] != "tracked+local":
            pytest.skip("local modules exist only in tracked+local")
        candidate, _ = acceptance_records
        for shell in scenario.shells:
            loaded = EXPECTED[_shell_kind(shell)]["modules"]
            for module in MODULE_LOAD_ORDER:
                function = "dotfiles_local_" + module.replace("-", "_")
                assert (function in candidate[shell.name]["functions"]) is (
                    module in loaded
                ), (shell.name, module)

    def test_local_module_log_and_login_fallbacks(
        self, scenario, dotfiles_home, acceptance_records
    ):
        candidate, _ = acceptance_records
        for shell in scenario.shells:
            modules = (
                EXPECTED[_shell_kind(shell)]["modules"]
                if dotfiles_home["configuration"] == "tracked+local"
                else ()
            )
            expected = "".join(f"{module}.local;" for module in modules)
            assert candidate[shell.name]["local_log"] == expected, shell.name

    def test_tracked_alias_overrides_local(self, scenario, dotfiles_home, acceptance_records):
        if dotfiles_home["configuration"] != "tracked+local":
            pytest.skip("local alias exists only in tracked+local")
        candidate, _ = acceptance_records
        for shell in scenario.shells:
            if "aliases" in EXPECTED[_shell_kind(shell)]["modules"]:
                assert candidate[shell.name]["aliases"]["ll"] != "local-override", shell.name

    def test_managed_precedence(self, scenario, dotfiles_home, acceptance_records):
        candidate, control = acceptance_records
        managed = _managed_entries(dotfiles_home)
        rank = {entry: index for index, entry in enumerate(managed)}
        rank["/opt/homebrew/sbin"] = rank["/opt/homebrew/bin"]
        for shell in scenario.shells:
            path = candidate[shell.name]["path"]
            homebrew = ("/opt/homebrew/bin", "/opt/homebrew/sbin")
            present_homebrew = set(path) & set(homebrew)
            actual_homebrew = [entry for entry in path if entry in homebrew]
            expected_homebrew = [
                entry for entry in homebrew if entry in present_homebrew
            ]
            assert actual_homebrew == expected_homebrew, (shell.name, path)
            if not (shell.reads_bashrc or shell.reads_profile):
                continue
            actual = [entry for entry in path if entry in managed]
            assert actual == sorted(actual, key=rank.__getitem__), (shell.name, actual)
            managed_positions = [index for index, entry in enumerate(path) if entry in managed]
            system_paths = (
                set(dotfiles_home["initial_path"]) | set(control[shell.name]["path"])
            ) - set(managed)
            system_positions = [
                index for index, entry in enumerate(path) if entry in system_paths
            ]
            assert (
                not managed_positions
                or not system_positions
                or max(managed_positions) < min(system_positions)
            ), (shell.name, path)

    def test_fresh_login_retains_required_managed_path_defaults(
        self, scenario, dotfiles_home, acceptance_records
    ):
        candidate, _ = acceptance_records
        required = [
            str(dotfiles_home["home"] / suffix)
            for suffix in (
                ".local/bin",
                "node_modules/.bin",
                ".go/bin",
                ".bun/bin",
            )
        ]
        for shell in scenario.shells:
            if shell.launcher is None and shell.reads_profile:
                path = candidate[shell.name]["path"]
                assert all(entry in path for entry in required), (shell.name, path)
                assert [entry for entry in path if entry in required] == required, (
                    shell.name,
                    path,
                )

    def test_fresh_managed_paths_are_not_duplicated(
        self, scenario, dotfiles_home, acceptance_records
    ):
        candidate, _ = acceptance_records
        for shell in scenario.shells:
            if shell.launcher is None and shell.reads_profile:
                for entry in _managed_entries(dotfiles_home):
                    assert candidate[shell.name]["path"].count(entry) <= 1, (shell.name, entry)

    def test_child_adds_no_managed_duplicates(self, scenario, dotfiles_home, acceptance_records):
        candidate, _ = acceptance_records
        for shell in scenario.shells:
            if shell.launcher is None:
                continue
            for entry in _managed_entries(dotfiles_home):
                parent_count = candidate[shell.launcher]["path"].count(entry)
                child_count = candidate[shell.name]["path"].count(entry)
                assert child_count <= max(1, parent_count), (
                    shell.name, entry, parent_count, child_count
                )

    def test_callers_precede_managed_paths(self, scenario, dotfiles_home, acceptance_records):
        candidate, _ = acceptance_records
        for shell in scenario.shells:
            if not shell.prepend_callers:
                continue
            record = candidate[shell.name]
            assert record["path"][:2] == dotfiles_home["callers"], shell.name
            marker = str(Path(dotfiles_home["callers"][0]) / dotfiles_home["marker"])
            assert record["marker_path"] == marker, shell.name
            assert record["marker_status"] == 0, shell.name
            assert record["marker_identity"] == dotfiles_home["identities"][marker], shell.name

    def test_nonlogin_child_keeps_inherited_path(
        self, scenario, dotfiles_home, acceptance_records
    ):
        candidate, _ = acceptance_records
        for shell in scenario.shells:
            if shell.launcher is None or shell.reads_profile:
                continue
            inherited = candidate[shell.launcher]["path"]
            if shell.prepend_callers:
                inherited = dotfiles_home["callers"] + inherited
            assert candidate[shell.name]["path"] == inherited, shell.name


_PATH_CASE_PREFIX = r"""
shell=$1
py=$2
serial=$3
root=$4
marker_name=$5
next_script=$6
shift 6
probe_shell() {
""" + PROBE + r"""
}
record() {
    probe_shell "$py" "$serial" "$root/$1.json" "$root/$1.functions" \
        "$root/$1.aliases" "$root/$1.shopt" "$marker_name"
}
"""

_PATH_CASE_CHILD = r"""
exec "$shell" -l -c "$next_script" path-case "$shell" "$py" "$serial" \
    "$root" "$marker_name" "" "$@"
"""


def _run_path_case(fixture: dict, body: str, args=(), child_body="") -> dict:
    """Run fixed test code with fixture-owned paths passed only as arguments."""
    root = fixture["root"] / "path-case"
    root.mkdir()
    child = _PATH_CASE_PREFIX + child_body
    result = subprocess.run(
        [
            fixture["bash"], "-l", "-c", _PATH_CASE_PREFIX + body, "path-case",
            fixture["bash"], fixture["python"], SERIALIZE, str(root),
            fixture["marker"], child, *map(str, args),
        ],
        env=fixture["environment"],
        cwd=root,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    for suffix, value in (
        ("stdout", result.stdout), ("stderr", result.stderr),
        ("status", f"{result.returncode}\n"),
    ):
        (root / f"launch.{suffix}").write_text(value, encoding="utf-8")
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in root.glob("*.json")
    }


def _assert_marker(record: dict, fixture: dict, directory: str) -> None:
    marker = str(Path(directory) / fixture["marker"])
    assert record["marker_path"] == marker
    assert record["marker_identity"] == fixture["identities"][marker]
    assert record["marker_status"] == 0


@pytest.mark.dotfiles
@pytest.mark.acceptance
def test_path_repeated_login_and_source(dotfiles_home):
    records = _run_path_case(
        dotfiles_home,
        'record initial\n' + _PATH_CASE_CHILD,
        child_body=r"""
record child
. "$HOME/.local/etc/bashrc.d/exports.bash"
. "$HOME/.local/etc/bashrc.d/exports.bash"
record final
""",
    )
    assert records["child"]["path"] == records["initial"]["path"]
    assert records["final"]["path"] == records["initial"]["path"]
    for entry in _managed_entries(dotfiles_home):
        assert records["final"]["path"].count(entry) <= 1
    _assert_marker(records["final"], dotfiles_home, dotfiles_home["managed"][0])


@pytest.mark.dotfiles
@pytest.mark.acceptance
@pytest.mark.parametrize("survives", (False, True))
def test_path_replaced_and_surviving_callers(dotfiles_home, survives):
    old, new = dotfiles_home["callers"]
    records = _run_path_case(
        dotfiles_home,
        r"""
record initial
PATH="$1:$PATH"
""" + _PATH_CASE_CHILD,
        args=(
            old, new, "keep" if survives else "remove",
            _PATH_CASE_PREFIX + "record final\n",
        ),
        child_body=r"""
record with_old
if [ "$3" = remove ]; then PATH=${PATH#"$1:"}; fi
PATH="$2:$PATH"
exec "$shell" -l -c "$4" path-case "$shell" "$py" "$serial" \
    "$root" "$marker_name" "" "$@"
""",
    )
    initial = records["initial"]["path"]
    assert records["with_old"]["path"] == [old, *initial]
    assert records["final"]["path"] == [new, *([old] if survives else []), *initial]
    _assert_marker(records["final"], dotfiles_home, new)


@pytest.mark.dotfiles
@pytest.mark.acceptance
def test_path_appended_unknown_stays_in_tail(dotfiles_home):
    appended = dotfiles_home["root"] / "appended"
    appended.mkdir()
    records = _run_path_case(
        dotfiles_home,
        'record initial\nPATH="$PATH:$1"\n' + _PATH_CASE_CHILD,
        args=(appended,),
        child_body="record final\n",
    )
    assert records["final"]["path"] == [*records["initial"]["path"], str(appended)]
    _assert_marker(records["final"], dotfiles_home, dotfiles_home["managed"][0])


@pytest.mark.dotfiles
@pytest.mark.acceptance
@pytest.mark.parametrize("name", ("with spaces", "star*", "question?", "bracket["))
def test_path_literal_caller_and_inherited_entries(dotfiles_home, name):
    root = dotfiles_home["root"]
    caller = root / ("caller " + name)
    inherited = root / ("inherited " + name)
    for directory in (caller, inherited):
        directory.mkdir()
        marker = directory / dotfiles_home["marker"]
        identity = directory.name
        marker.write_text(f"#!/bin/sh\nprintf '%s\\n' '{identity}'\n", encoding="utf-8")
        marker.chmod(0o755)
        dotfiles_home["identities"][str(marker)] = identity
    for managed in dotfiles_home["managed"]:
        (Path(managed) / dotfiles_home["marker"]).unlink()
    dotfiles_home["environment"]["PATH"] += f":{inherited}"
    records = _run_path_case(
        dotfiles_home,
        'record initial\nPATH="$1:$PATH"\n' + _PATH_CASE_CHILD,
        args=(caller,),
        child_body="record final\n",
    )
    assert records["initial"]["path"].count(str(inherited)) == 1
    _assert_marker(records["initial"], dotfiles_home, str(inherited))
    assert records["final"]["path"] == [str(caller), *records["initial"]["path"]]
    _assert_marker(records["final"], dotfiles_home, str(caller))


def _homebrew_prefix():
    return next(
        (value for value in ("/usr/local", "/opt/homebrew")
         if os.access(f"{value}/bin/brew", os.X_OK)),
        "",
    )


def _homebrew_entries():
    prefix = _homebrew_prefix()
    return [f"{prefix}/bin", f"{prefix}/sbin"] if prefix else []


def _direct_path_case(fixture, incoming, provider, baseline="", baseline_home=None):
    prefix = _homebrew_prefix()
    records = _run_path_case(
        fixture,
        r"""
_dotfiles_rebuild_path "$1" "$2" "$3" "$4" "$5"
export PATH
record final
""",
        args=(
            ":".join(incoming), ":".join(provider), prefix, ":".join(baseline),
            str(fixture["home"]) if baseline_home is None and baseline else str(baseline_home or ""),
        ),
    )
    return records["final"], _homebrew_entries()


@pytest.mark.dotfiles
@pytest.mark.acceptance
def test_path_direct_tail_multiplicity_and_missing_entry(dotfiles_home):
    fixture = dotfiles_home
    missing = str(fixture["root"] / "does not exist")
    assert not Path(missing).exists()
    caller = fixture["callers"][0]
    tail = ["", caller, "relative dir", missing, caller, "", ".", ""]
    incoming = ["", *fixture["managed"], *tail[1:]]
    record, brew = _direct_path_case(fixture, incoming, incoming)
    assert record["path"] == [*fixture["managed"], *brew, *tail]
    _assert_marker(record, fixture, fixture["managed"][0])


@pytest.mark.dotfiles
@pytest.mark.acceptance
@pytest.mark.parametrize(
    "snapshot",
    ("absent", "missing-home", "stale-home", "duplicate", "reordered", "no-anchor"),
)
def test_path_invalid_snapshot_does_not_promote_or_copy(dotfiles_home, snapshot):
    fixture = dotfiles_home
    managed = fixture["managed"]
    caller = fixture["callers"][0]
    stale = str(fixture["root"] / "stale-only")
    incoming = [caller, *managed, "tail"]
    baseline = {
        "absent": [],
        "missing-home": [*managed, stale],
        "stale-home": [*managed, stale],
        "duplicate": [managed[0], managed[0], *managed[1:], stale],
        "reordered": [managed[1], managed[0], *managed[2:], stale],
        "no-anchor": [stale],
    }[snapshot]
    home = {
        "missing-home": "",
        "stale-home": fixture["root"] / "old-home",
    }.get(snapshot, fixture["home"])
    record, brew = _direct_path_case(fixture, incoming, incoming, baseline, home)
    assert record["path"] == [*managed, *brew, caller, "tail"]
    assert stale not in record["path"]
    _assert_marker(record, fixture, managed[0])


@pytest.mark.dotfiles
@pytest.mark.acceptance
def test_path_snapshot_compares_only_surviving_defaults(dotfiles_home):
    fixture = dotfiles_home
    managed = fixture["managed"]
    caller = fixture["callers"][0]
    # The first baseline default was removed; the next shared default is the anchor.
    incoming = [caller, managed[1], managed[5], "tail"]
    record, brew = _direct_path_case(fixture, incoming, incoming, [*managed, "tail"])
    expected = [managed[0], managed[1], managed[5], managed[6]]
    assert record["path"] == [caller, *expected, *brew, "tail"]
    _assert_marker(record, fixture, caller)


@pytest.mark.dotfiles
@pytest.mark.acceptance
@pytest.mark.parametrize("metadata", ("unset", "inconsistent"))
def test_path_source_with_missing_snapshot(dotfiles_home, metadata):
    fixture = dotfiles_home
    caller = fixture["callers"][0]
    records = _run_path_case(
        fixture,
        r"""
record initial
PATH="$1:$PATH"
if [ "$2" = unset ]; then
    unset _DOTFILES_PATH_BASELINE _DOTFILES_PATH_HOME
else
    unset _DOTFILES_PATH_HOME
fi
. "$HOME/.local/etc/bashrc.d/exports.bash"
record final
""",
        args=(caller, metadata),
    )
    initial = records["initial"]["path"]
    managed = fixture["managed"] + _homebrew_entries()
    expected_head = [entry for entry in initial if entry in managed]
    expected_tail = [entry for entry in initial if entry not in managed]
    assert records["final"]["path"] == [*expected_head, caller, *expected_tail]
    _assert_marker(records["final"], fixture, fixture["managed"][0])


@pytest.mark.dotfiles
@pytest.mark.acceptance
def test_path_changed_home_ignores_old_snapshot(dotfiles_home):
    fixture = dotfiles_home
    old_home = fixture["home"]
    new_home = fixture["root"] / "new home"
    for name in (".local/bin", "node_modules/.bin", ".bun/bin"):
        (new_home / name).mkdir(parents=True)
    new_marker = new_home / ".local/bin" / fixture["marker"]
    new_marker.write_text("#!/bin/sh\nprintf '%s\\n' new-home\n", encoding="utf-8")
    new_marker.chmod(0o755)
    fixture["identities"][str(new_marker)] = "new-home"
    caller = fixture["callers"][0]
    records = _run_path_case(
        fixture,
        r"""
record initial
HOME=$1
PATH="$2"
export HOME PATH
. "$3"
record final
""",
        args=(
            new_home, f"{caller}:{fixture['environment']['PATH']}",
            old_home / ".local/etc/bashrc.d/exports.bash",
        ),
    )
    brew = _homebrew_entries()
    expected = [
        str(new_home / ".local/bin"), str(new_home / "node_modules/.bin"),
        str(new_home / ".go/bin"), str(new_home / ".bun/bin"),
    ]
    assert records["final"]["path"] == [
        *expected, *brew, caller, *(entry for entry in fixture["initial_path"] if entry not in brew),
    ]
    _assert_marker(records["final"], fixture, expected[0])
