"""Host-only checks for the shared shell scenario registry."""

import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import scenarios
import test_dotfiles as dotfiles
from probe import SERIALIZE, launch_environment, launch_script, parse_shopt, run_scenario
from test_dotfiles import _check_integrity


RUNNABLE_IDS = {
    "S01",
    "S02",
    "S03",
    "S04",
    "S07-resolve",
    "S08-c",
    "S08-login-c",
    "S08-source-rc",
    "S08-fresh-c",
    "S08-fresh-login-c",
}

PENDING = {
    **dict.fromkeys(
        ("S05", "S06", "S07"),
        "expected behavior defined in scenarios.md; launch steps not defined yet",
    ),
    **dict.fromkeys(
        ("SSH-login", "SSH-cmd", "SSH-tty"),
        "no sshd transport yet; see open question S5",
    ),
}


def test_terminal_process_group_normalization():
    candidate = (
        "bash: cannot set terminal process group (123): Inappropriate ioctl for device\n"
        "another diagnostic 123\n"
    )
    control = candidate.replace("group (123)", "group (456)")
    normalize = dotfiles._normalize_startup_stderr
    assert normalize(candidate) == normalize(control)
    assert normalize("earlier output\n" + candidate) == normalize("earlier output\n" + control)
    assert normalize(candidate) != normalize(control.replace("diagnostic 123", "diagnostic 456"))
    assert normalize(candidate) != normalize(control.replace("Inappropriate", "Unexpected"))
    assert normalize("cannot set terminal process group (abc)") != normalize(
        "cannot set terminal process group (def)"
    )

    records = ({"parent": {"stderr": candidate}}, {"parent": {"stderr": control}})
    dotfiles.TestExpectedState().test_startup_output_matches_system(
        scenarios.S01, records, "stderr"
    )
    assert records[0]["parent"]["stderr"] == candidate
    assert records[1]["parent"]["stderr"] == control
    records[1]["parent"]["stderr"] += "unexpected output\n"
    with pytest.raises(AssertionError):
        dotfiles.TestExpectedState().test_startup_output_matches_system(
            scenarios.S01, records, "stderr"
        )


@pytest.mark.parametrize(
    ("stream", "line"),
    [
        ("stdout", "bash: cannot set terminal process group (123): Inappropriate ioctl for device"),
        ("stderr", "app: cannot set terminal process group (123): Inappropriate ioctl for device"),
        ("stderr", "prefix bash: cannot set terminal process group (123): Inappropriate ioctl for device"),
        ("stderr", "bash: cannot set terminal process group (123): another error"),
        ("stderr", "bash: cannot set terminal process group (123): Inappropriate ioctl for device extra"),
    ],
)
def test_terminal_process_group_normalization_preserves_other_output(stream, line):
    candidate = line + "\n"
    control = candidate.replace("(123)", "(456)")
    records = ({"parent": {stream: candidate}}, {"parent": {stream: control}})
    with pytest.raises(AssertionError):
        dotfiles.TestExpectedState().test_startup_output_matches_system(
            scenarios.S01, records, stream
        )
    assert records[0]["parent"][stream] == candidate
    assert records[1]["parent"][stream] == control


@pytest.mark.parametrize(
    ("shell", "modules"),
    [
        (scenarios.PARENT, ("exports", "shell-options", "aliases", "functions", "app-config", "prompt")),
        (scenarios.S03.shells[1], ("shell-options", "aliases", "functions", "app-config", "prompt")),
        (scenarios.S08_FRESH_LOGIN_C.shells[0], ("exports",)),
        (scenarios.S08_FRESH_C.shells[0], ()),
        (scenarios.S08_SOURCE_RC.shells[1], ()),
    ],
)
def test_local_shell_options_expectations(shell, modules):
    scenario = scenarios.Scenario("local-options", "Local shell options", (shell,))
    fixture = {"configuration": "tracked+local"}
    record = {
        "local_log": "".join(f"{module}.local;" for module in modules),
        "functions": ["dotfiles_local_" + module.replace("-", "_") for module in modules],
    }
    records = ({shell.name: record}, {})
    suite = dotfiles.TestExpectedState()
    suite.test_local_module_log_and_login_fallbacks(scenario, fixture, records)
    suite.test_local_module_functions(scenario, fixture, records)
    assert dotfiles._expected_local_log(fixture, shell) == record["local_log"]

    if "shell-options" in modules:
        record["local_log"] = record["local_log"].replace("shell-options.local;", "")
        record["functions"].remove("dotfiles_local_shell_options")
    else:
        record["local_log"] += "shell-options.local;"
        record["functions"].append("dotfiles_local_shell_options")
    with pytest.raises(AssertionError):
        suite.test_local_module_log_and_login_fallbacks(scenario, fixture, records)
    with pytest.raises(AssertionError):
        suite.test_local_module_functions(scenario, fixture, records)
    assert dotfiles._expected_local_log(fixture, shell) != record["local_log"]


@pytest.mark.parametrize("scenario", (scenarios.S01, scenarios.S08_FRESH_LOGIN_C))
@pytest.mark.parametrize(
    "policy",
    (
        "precedence",
        "duplicates",
        "required-paths",
        "required-paths-missing",
        "homebrew-order",
    ),
)
def test_fresh_login_path_policies_detect_violations(scenario, policy):
    fixture = {
        "home": Path("/home/example"),
        "managed": ["/managed/first", "/managed/second"],
        "initial_path": ["/system"],
    }
    if policy == "precedence":
        path = ["/managed/second", "/managed/first", "/system"]
    elif policy == "duplicates":
        path = ["/managed/first", "/managed/first", "/system"]
    elif policy == "required-paths":
        path = [
            "/home/example/node_modules/.bin",
            "/home/example/.local/bin",
            "/home/example/.go/bin",
            "/home/example/.bun/bin",
            "/system",
        ]
    elif policy == "required-paths-missing":
        path = [
            "/home/example/.local/bin",
            "/home/example/node_modules/.bin",
            "/home/example/.go/bin",
            "/system",
        ]
    else:
        path = ["/opt/homebrew/sbin", "/opt/homebrew/bin", "/system"]
    name = scenario.shells[0].name
    records = ({name: {"path": path}}, {name: {"path": ["/system"]}})
    suite = dotfiles.TestExpectedState()
    check = {
        "precedence": suite.test_managed_precedence,
        "duplicates": suite.test_fresh_managed_paths_are_not_duplicated,
        "required-paths": suite.test_fresh_login_retains_required_managed_path_defaults,
        "required-paths-missing": suite.test_fresh_login_retains_required_managed_path_defaults,
        "homebrew-order": suite.test_managed_precedence,
    }[policy]
    with pytest.raises(AssertionError):
        check(scenario, fixture, records)


def test_dotfiles_characterization_preserves_different_startup_output(tmp_path, monkeypatch):
    observations = []

    def fake_run(command, **kwargs):
        root = Path(kwargs["cwd"])
        (root / "parent.json").write_text("{}", encoding="utf-8")
        stdout = "Homebrew initialized\n" if root.name == "candidate" else ""
        stderr = "known startup diagnostic\n" if root.name == "candidate" else ""
        return subprocess.CompletedProcess(command, 0, stdout, stderr)

    def check_integrity(records, fixture, scenario):
        observations.append((records, fixture, scenario))

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(dotfiles, "_check_integrity", check_integrity)
    home = tmp_path / "home"
    home.mkdir()
    fixture = {
        "root": tmp_path,
        "home": home,
        "configuration": "tracked",
        "local_functions": {},
        "environment": {"HOME": str(home), "PATH": "/bin"},
        "bash": "/bin/bash",
    }
    dotfiles.test_dotfiles_integrity_and_system_only_control(scenarios.S01, fixture)

    assert len(observations) == 2
    candidate, control = observations
    assert candidate[2] is control[2] is scenarios.S01
    assert control[1]["home"].is_dir()
    assert not list(control[1]["home"].iterdir())
    for suffix in ("stdout", "stderr"):
        candidate_output = candidate[0]["parent"][suffix]
        control_output = control[0]["parent"][suffix]
        assert candidate_output and control_output == ""
        assert (tmp_path / "candidate" / f"parent.{suffix}").read_text() == candidate_output
        assert (
            tmp_path / "system-control/probe" / f"parent.{suffix}"
        ).read_text() == control_output


@pytest.mark.parametrize("damage", [None, "contents", "permissions", "missing"])
@pytest.mark.parametrize("mode", ["shared", "shared-local-overwritten-alias"])
def test_unresolved_dotfiles_marker_is_checked_without_execution(
    tmp_path, monkeypatch, damage, mode
):
    def forbidden_run(*args, **kwargs):
        pytest.fail("integrity checks must not execute the fixture marker")

    monkeypatch.setattr(subprocess, "run", forbidden_run)
    marker = tmp_path / "marker"
    marker.write_text("#!/bin/sh\nprintf '%s\\n' 'marker-0'\n", encoding="utf-8")
    marker.chmod(0o755)
    fixture = {
        "configuration": "tracked",
        "local_functions": {},
        "marker": marker.name,
        "managed": [str(tmp_path)],
        "identities": {str(marker): "marker-0"},
    }
    record = {
        "path": ["/bin"],
        "interactive": False,
        "login": False,
        "shlvl": 1,
        "pid": 42,
        "tty": False,
        "magic_space": False,
        "startup_log": "",
        "local_log": "",
        "functions": [],
        "aliases": {},
        "shopt_on": [],
        "histcontrol": "",
        "histsize": "",
        "histfilesize": "",
        "shell_vars": dict.fromkeys(
            ("STARTUP_LOG", "LOCAL_LOG", "HISTCONTROL", "HISTSIZE", "HISTFILESIZE"), ""
        ),
        "env": dict.fromkeys(
            ("MYVAR", "GOPATH", "PROMPT_COMMAND", "HISTTIMEFORMAT", "VSCODE_RESOLVING_ENVIRONMENT")
        ),
        "marker_path": "",
        "marker_identity": "",
        "marker_status": 127,
        "status": 0,
        "stdout": "",
        "stderr": "",
    }
    if damage == "contents":
        marker.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    elif damage == "permissions":
        marker.chmod(0o644)
    elif damage == "missing":
        marker.unlink()
    checker = _check_integrity
    if mode == "shared-local-overwritten-alias":
        fixture["configuration"] = "tracked+local"
        fixture["local_functions"] = {
            module: "dotfiles_local_" + module.replace("-", "_")
            for module in dotfiles.MODULE_LOAD_ORDER
        }
        record["interactive"] = True
        record["login"] = True
        record["functions"] = list(fixture["local_functions"].values())
        record["aliases"] = {"ll": "ls -l"}
        record["local_log"] = "".join(
            f"{module}.local;" for module in dotfiles.MODULE_LOAD_ORDER
        )
        record["shell_vars"]["LOCAL_LOG"] = record["local_log"]
        records = {"parent": record}
        scenario = scenarios.S01
    else:
        records = {"fresh": record}
        scenario = scenarios.S08_FRESH_C
    if damage is None:
        checker(records, fixture, scenario)
    else:
        with pytest.raises(AssertionError):
            checker(records, fixture, scenario)


def test_scenario_ids_are_unique_and_indexed():
    ids = [scenario.id for scenario in scenarios.SCENARIOS]
    assert len(ids) == len(set(ids))
    assert scenarios.SCENARIO == {scenario.id: scenario for scenario in scenarios.SCENARIOS}
    assert set(ids) == RUNNABLE_IDS | PENDING.keys()


def test_launchers_exist_and_precede_children():
    for scenario in scenarios.SCENARIOS:
        seen = set()
        for shell in scenario.shells:
            assert shell.name not in seen, scenario.id
            assert shell.launcher is None or shell.launcher in seen, scenario.id
            seen.add(shell.name)


def test_params_skip_only_pending_scenarios():
    params = list(scenarios.scenario_params())
    assert [param.id for param in params] == [scenario.id for scenario in scenarios.SCENARIOS]
    for param, scenario in zip(params, scenarios.SCENARIOS, strict=True):
        assert param.values == (scenario,)
        assert scenario.pending == PENDING.get(scenario.id)
        if scenario.id in PENDING:
            assert scenario.shells == ()
            assert len(param.marks) == 1
            assert param.marks[0].name == "skip"
            assert param.marks[0].kwargs["reason"] == PENDING[scenario.id]
        else:
            assert not param.marks


def test_runnable_scenario_shell_structures():
    parent = scenarios.PARENT
    assert parent == scenarios.Shell("parent", ("-i", "-l"))
    expected = {
        "S01": (parent,),
        "S02": (parent, scenarios.Shell("child", ("-i", "-l"), launcher=parent.name)),
        "S03": (parent, scenarios.Shell("child", ("-i",), launcher=parent.name)),
        "S04": (
            parent,
            scenarios.Shell("login", ("-i", "-l"), launcher=parent.name, prepend_callers=True),
            scenarios.Shell("nonlogin", ("-i",), launcher=parent.name, prepend_callers=True),
        ),
        "S07-resolve": (
            scenarios.Shell(
                "resolve",
                ("-i", "-l"),
                environment=(("VSCODE_RESOLVING_ENVIRONMENT", "1"),),
            ),
        ),
        "S08-c": (parent, scenarios.Shell("child", (), launcher=parent.name)),
        "S08-login-c": (parent, scenarios.Shell("child", ("-l",), launcher=parent.name)),
        "S08-source-rc": (
            parent,
            scenarios.Shell("child", (), launcher=parent.name, source_bashrc=True),
        ),
        "S08-fresh-c": (scenarios.Shell("fresh", ()),),
        "S08-fresh-login-c": (scenarios.Shell("fresh", ("-l",)),),
    }
    assert {s.id: s.shells for s in scenarios.SCENARIOS if not s.pending} == expected


def test_shell_mode_properties_and_immutable_records():
    for options, interactive, login in [
        ((), False, False),
        (("-i",), True, False),
        (("-l",), False, True),
        (("-i", "-l"), True, True),
    ]:
        shell = scenarios.Shell("example", options)
        assert shell.interactive is interactive
        assert shell.login is login
        with pytest.raises(FrozenInstanceError):
            shell.name = "changed"
    with pytest.raises(FrozenInstanceError):
        scenarios.S01.title = "changed"


def test_vscode_resolver_is_top_level():
    (shell,) = scenarios.SCENARIO["S07-resolve"].shells
    assert shell.launcher is None
    assert shell.options == ("-i", "-l")
    assert dict(shell.environment) == {"VSCODE_RESOLVING_ENVIRONMENT": "1"}


def test_s04_launches_both_children_with_caller_paths():
    script = launch_script(scenarios.SCENARIO["S04"])
    assert script.count('PATH="$caller1:$caller2:$PATH"') == 2


def test_s08_source_rc_prefixes_child_command():
    script = launch_script(scenarios.SCENARIO["S08-source-rc"])
    assert '[ -r ~/.bashrc ] && . ~/.bashrc;' in script


def test_shopt_parser_reads_enabled_options_from_bash_output():
    assert parse_shopt(
        "checkwinsize       on\n"
        "cdspell             off\n"
        "nocaseglob          on\n"
    ) == ["checkwinsize", "nocaseglob"]


def test_launch_environment_applies_only_top_level_scenario_pairs():
    base = {"PATH": "/bin", "KEEP": "yes"}
    assert launch_environment(scenarios.SCENARIO["S07-resolve"], base) == {
        **base,
        "VSCODE_RESOLVING_ENVIRONMENT": "1",
    }
    assert launch_environment(scenarios.SCENARIO["S04"], base) == base


def test_parent_probe_failure_stops_child_launches():
    script = launch_script(scenarios.SCENARIO["S04"])
    assert script.index('|| exit "$?"') < script.index('"$bash"')


def test_serializer_groups_shell_variables_and_parses_multiline_aliases(tmp_path):
    output = tmp_path / "record.json"
    functions = tmp_path / "functions"
    aliases = tmp_path / "aliases"
    shopt = tmp_path / "shopt"
    functions.write_text("probe_shell\ncodetree\n", encoding="utf-8")
    aliases.write_text(
        "alias simple='one two'\nalias multiline='first\nsecond'\n"
        "alias #foo='hash value'\n",
        encoding="utf-8",
    )
    shopt.write_text("shopt -s extglob\n", encoding="utf-8")
    env = {
        **os.environ,
        "MYVAR": "my-value",
        "GOPATH": "/go",
        "PROMPT_COMMAND": "prompt",
        "HISTTIMEFORMAT": "%F",
        "VSCODE_RESOLVING_ENVIRONMENT": "1",
    }
    args = [
        sys.executable,
        "-c",
        SERIALIZE,
        str(output),
        str(functions),
        str(aliases),
        str(shopt),
        "true",
        "false",
        "2",
        "42",
        "false",
        "true",
        "startup",
        "local",
        "ignoredups",
        "123",
        "456",
        "false",
        "",
        "",
        "0",
    ]
    subprocess.run(args, env=env, check=True, capture_output=True, text=True)
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["functions"] == ["codetree"]
    assert record["aliases"] == {
        "simple": "one two",
        "multiline": "first\nsecond",
        "#foo": "hash value",
    }
    assert record["shell_vars"] == {
        "STARTUP_LOG": "startup",
        "LOCAL_LOG": "local",
        "HISTCONTROL": "ignoredups",
        "HISTSIZE": "123",
        "HISTFILESIZE": "456",
    }
    assert record["env"] == {
        "MYVAR": "my-value",
        "GOPATH": "/go",
        "PROMPT_COMMAND": "prompt",
        "HISTTIMEFORMAT": "%F",
        "VSCODE_RESOLVING_ENVIRONMENT": "1",
    }


def test_runner_resolves_relative_home_and_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    observed = {}

    def fake_run(command, **kwargs):
        observed.update(kwargs)
        (Path(kwargs["cwd"]) / "resolve.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_scenario(
        scenarios.SCENARIO["S07-resolve"],
        "relative-home",
        {"PATH": "/bin"},
        "/bin/bash",
        "relative-root",
    )
    assert Path(observed["cwd"]).is_absolute()
    assert observed["env"]["HOME"] == str((tmp_path / "relative-home").resolve())


def test_missing_observation_reports_captured_process_output(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 7, "captured stdout", "captured stderr")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AssertionError) as error:
        run_scenario(
            scenarios.SCENARIO["S07-resolve"],
            "home",
            {"PATH": "/bin"},
            "/bin/bash",
            "root",
        )
    message = str(error.value)
    assert "status=7" in message
    assert "captured stdout" in message
    assert "captured stderr" in message


def test_runner_clears_stale_shell_artifacts_before_failed_launch(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    root = Path("root")
    root.mkdir()
    shell_name = "resolve"
    for suffix in (
        ".json",
        ".functions",
        ".aliases",
        ".shopt",
        ".stdout",
        ".stderr",
        ".status",
    ):
        (root / f"{shell_name}{suffix}").write_text("stale record", encoding="utf-8")
    unrelated = root / "keep.txt"
    unrelated.write_text("preserve", encoding="utf-8")

    def failed_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 9, "fresh stdout", "fresh stderr")

    monkeypatch.setattr(subprocess, "run", failed_run)
    with pytest.raises(AssertionError) as error:
        run_scenario(
            scenarios.SCENARIO["S07-resolve"],
            "home",
            {"PATH": "/bin"},
            "/bin/bash",
            root,
        )
    message = str(error.value)
    assert "status=9" in message
    assert "fresh stdout" in message and "fresh stderr" in message
    assert "stale record" not in message
    assert not (root / f"{shell_name}.json").exists()
    assert not (root / f"{shell_name}.functions").exists()
    assert not (root / f"{shell_name}.aliases").exists()
    assert not (root / f"{shell_name}.shopt").exists()
    assert unrelated.read_text(encoding="utf-8") == "preserve"
