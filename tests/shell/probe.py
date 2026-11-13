"""Shared Bash probe and scenario runner."""

import inspect
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from scenarios import STATE, SYNTAX


def parse_aliases(text: str) -> dict[str, str]:
    """Parse Bash ``alias -p`` output, including definitions spanning lines."""
    lexer = shlex.shlex(text, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    aliases = {}
    index = 0
    while index + 1 < len(tokens):
        if tokens[index] == "alias" and "=" in tokens[index + 1]:
            name, value = tokens[index + 1].split("=", 1)
            aliases[name] = value
            index += 2
        else:
            index += 1
    return aliases


def parse_shopt(text: str) -> list[str]:
    """Return enabled options from the two-column output of ``shopt -s``."""
    enabled = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == "on":
            enabled.append(parts[0])
    return enabled


SERIALIZE = inspect.getsource(parse_aliases) + inspect.getsource(parse_shopt) + r"""
import json, os, shlex, sys
(
    output, functions_file, aliases_file, shopt_file, interactive, login,
    level, pid, tty, magic_space, startup_log, local_log, histcontrol,
    histsize, histfilesize, marker_supplied, marker_path, marker_identity,
    marker_status,
) = sys.argv[1:]
with open(functions_file, encoding="utf-8") as stream:
    functions = [
        line.rstrip("\n") for line in stream if line.rstrip("\n") != "probe_shell"
    ]
with open(aliases_file, encoding="utf-8") as stream:
    aliases = parse_aliases(stream.read())
with open(shopt_file, encoding="utf-8") as stream:
    shopt_on = parse_shopt(stream.read())
record = {
    "path": os.environ.get("PATH", "").split(":"),
    "interactive": interactive == "true",
    "login": login == "true",
    "shlvl": int(level),
    "pid": int(pid),
    "tty": tty == "true",
    "magic_space": magic_space == "true",
    "startup_log": startup_log,
    "local_log": local_log,
    "functions": functions,
    "aliases": aliases,
    "shopt_on": shopt_on,
    "histcontrol": histcontrol,
    "histsize": histsize,
    "histfilesize": histfilesize,
    "shell_vars": {
        "STARTUP_LOG": startup_log,
        "LOCAL_LOG": local_log,
        "HISTCONTROL": histcontrol,
        "HISTSIZE": histsize,
        "HISTFILESIZE": histfilesize,
    },
    "env": {
        name: os.environ.get(name) for name in (
            "MYVAR", "GOPATH", "PROMPT_COMMAND", "HISTTIMEFORMAT",
            "VSCODE_RESOLVING_ENVIRONMENT",
        )
    },
}
if marker_supplied == "true":
    record.update({
        "marker_path": marker_path,
        "marker_identity": marker_identity,
        "marker_status": int(marker_status),
    })
with open(output, "w", encoding="utf-8") as stream:
    json.dump(record, stream)
"""


PROBE = r"""
python=$1
serializer=$2
output=$3
functions_file=$4
aliases_file=$5
shopt_file=$6
marker=$7
case $- in *i*) interactive=true ;; *) interactive=false ;; esac
if shopt -q login_shell; then login=true; else login=false; fi
if tty -s 2>/dev/null; then tty_value=true; else tty_value=false; fi
if [ "$interactive" = true ] && bind -q magic-space >/dev/null 2>&1; then
    magic_space=true
else
    magic_space=false
fi
compgen -A function >"$functions_file"
alias -p >"$aliases_file"
shopt -s >"$shopt_file"
if [ -n "$marker" ]; then
    marker_supplied=true
    marker_path=$(command -v "$marker" 2>/dev/null)
    if [ -n "$marker_path" ]; then
        marker_identity=$("$marker_path" 2>/dev/null)
        marker_status=$?
    else
        marker_identity=
        marker_status=127
    fi
else
    marker_supplied=false
    marker_path=
    marker_identity=
    marker_status=0
fi
"$python" -c "$serializer" "$output" "$functions_file" "$aliases_file" \
    "$shopt_file" "$interactive" "$login" "$SHLVL" "$$" "$tty_value" \
    "$magic_space" "${STARTUP_LOG-}" "${LOCAL_LOG-}" "${HISTCONTROL-}" \
    "${HISTSIZE-}" "${HISTFILESIZE-}" "$marker_supplied" "$marker_path" \
    "$marker_identity" "$marker_status"
"""


def launch_script(scenario) -> str:
    """Build the Bash launcher that probes each shell in registry order."""
    first, *children = scenario.shells
    lines = [
        "bash=$1",
        "python=$2",
        "serializer=$3",
        "probe=$4",
        "root=$5",
        "marker=$6",
        "caller1=$7",
        "caller2=$8",
        "probe_shell() { eval \"$probe\"; }",
        'probe_shell "$python" "$serializer" '
        f'"$root/{first.name}.json" "$root/{first.name}.functions" '
        f'"$root/{first.name}.aliases" "$root/{first.name}.shopt" "$marker" '
        '|| exit "$?"',
    ]
    for shell in children:
        prefix = "[ -r ~/.bashrc ] && . ~/.bashrc; " if shell.source_bashrc else ""
        # The probe is Bash code and is passed as the child's -c command.
        launch = []
        if shell.prepend_callers:
            launch.append('PATH="$caller1:$caller2:$PATH"')
        launch.extend(
            f"{name}={shlex.quote(value)}" for name, value in shell.environment
        )
        launch.append('"$bash"')
        launch.extend(shell.options)
        launch.extend(
            [
                "-c",
                f'"{prefix}$probe"',
                shell.name,
                '"$python"',
                '"$serializer"',
                f'"$root/{shell.name}.json"',
                f'"$root/{shell.name}.functions"',
                f'"$root/{shell.name}.aliases"',
                f'"$root/{shell.name}.shopt"',
                '"$marker"',
            ]
        )
        lines.append(
            " ".join(launch)
            + f' >"$root/{shell.name}.stdout" 2>"$root/{shell.name}.stderr"'
        )
        lines.append(f'printf "%s\\n" "$?" >"$root/{shell.name}.status"')
    return "\n".join(lines) + "\n"


def launch_environment(scenario, base: dict[str, str]) -> dict[str, str]:
    """Return the top-level process environment for a scenario."""
    environment = base.copy()
    if scenario.shells:
        environment.update(dict(scenario.shells[0].environment))
    return environment


def run_scenario(scenario, home, environment, bash, root) -> dict:
    """Run a scenario and return each shell's probe record."""
    if scenario.observation_kind != STATE:
        raise ValueError(
            f"{scenario.id} is a {scenario.observation_kind} scenario; "
            "the -c probe cannot observe it"
        )
    root = Path(root).resolve()
    home = Path(home).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for shell in scenario.shells:
        for suffix in (
            ".json",
            ".functions",
            ".aliases",
            ".shopt",
            ".stdout",
            ".stderr",
            ".status",
        ):
            artifact = root / f"{shell.name}{suffix}"
            if artifact.is_file() or artifact.is_symlink():
                artifact.unlink()
    first = scenario.shells[0]
    caller1 = root / "caller one/bin"
    caller2 = root / "caller two/bin"
    marker = environment.get("SHELL_MARKER", "")
    command = [
        os.path.abspath(bash),
        *first.options,
        "-c",
        launch_script(scenario),
        "shell",
        os.path.abspath(bash),
        sys.executable,
        SERIALIZE,
        PROBE,
        str(root),
        marker,
        str(caller1),
        str(caller2),
    ]
    result = subprocess.run(
        command,
        env=launch_environment(scenario, {**environment, "HOME": str(home)}),
        cwd=root,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    (root / f"{first.name}.stdout").write_text(result.stdout, encoding="utf-8")
    (root / f"{first.name}.stderr").write_text(result.stderr, encoding="utf-8")
    (root / f"{first.name}.status").write_text(f"{result.returncode}\n", encoding="utf-8")
    records = {}
    for shell in scenario.shells:
        record_path = root / f"{shell.name}.json"
        if not record_path.is_file():
            status_path = root / f"{shell.name}.status"
            stdout_path = root / f"{shell.name}.stdout"
            stderr_path = root / f"{shell.name}.stderr"
            status = (
                status_path.read_text(encoding="utf-8").strip()
                if status_path.is_file()
                else str(result.returncode)
            )
            stdout = (
                stdout_path.read_text(encoding="utf-8")
                if stdout_path.is_file()
                else result.stdout
            )
            stderr = (
                stderr_path.read_text(encoding="utf-8")
                if stderr_path.is_file()
                else result.stderr
            )
            raise AssertionError(
                f"{scenario.id} {shell.name} observation missing; status={status}; "
                f"stdout={stdout!r}; stderr={stderr!r}"
            )
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["status"] = int(
            (root / f"{shell.name}.status").read_text(encoding="utf-8")
        )
        record["stdout"] = (root / f"{shell.name}.stdout").read_text(encoding="utf-8")
        record["stderr"] = (root / f"{shell.name}.stderr").read_text(encoding="utf-8")
        records[shell.name] = record
    return records


SYNTAX_MARKERS = ("valid", "invalid", "bash_env")
SCRIPT_ARTIFACTS = (".stdout", ".stderr", ".status", ".argv.json")


def write_syntax_fixtures(directory) -> dict:
    """Write fixture scripts whose only side effects are fixture-owned sentinels.

    The invalid script appends its sentinel before an unterminated ``if`` so an
    executing shell would leave evidence before reporting the syntax error.
    """
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    markers = {
        "valid": directory / "valid script ran",
        "invalid": directory / "invalid script ran",
        "bash_env": directory / "bash env ran",
    }
    scripts = {
        "valid": (
            directory / "valid script.sh",
            f"printf '%s\\n' valid-script >>{shlex.quote(str(markers['valid']))}\n",
        ),
        "invalid": (
            directory / "invalid script.sh",
            f"printf '%s\\n' invalid-script >>{shlex.quote(str(markers['invalid']))}\n"
            "if true; then\n"
            "    printf '%s\\n' unreachable\n",
        ),
        "bash_env": (
            directory / "bash env.sh",
            f"printf '%s\\n' bash-env >>{shlex.quote(str(markers['bash_env']))}\n",
        ),
    }
    fixtures = {"directory": directory, "markers": markers}
    for name, (path, text) in scripts.items():
        path.write_text(text, encoding="utf-8")
        fixtures[name] = path
    return fixtures


def run_script(options, script, home, environment, bash, root, name) -> dict:
    """Run ``bash [options] <script>`` and record its raw status and output."""
    script = Path(script)
    if not script.is_file():
        raise FileNotFoundError(f"script fixture is missing: {script}")
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for suffix in SCRIPT_ARTIFACTS:
        artifact = root / f"{name}{suffix}"
        if artifact.is_file() or artifact.is_symlink():
            artifact.unlink()
    argv = [os.path.abspath(bash), *options, str(script)]
    result = subprocess.run(
        argv,
        env={**environment, "HOME": str(Path(home).resolve())},
        cwd=root,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    (root / f"{name}.stdout").write_text(result.stdout, encoding="utf-8")
    (root / f"{name}.stderr").write_text(result.stderr, encoding="utf-8")
    (root / f"{name}.status").write_text(f"{result.returncode}\n", encoding="utf-8")
    (root / f"{name}.argv.json").write_text(json.dumps(argv), encoding="utf-8")
    return {
        "argv": argv,
        "status": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_syntax_check(scenario, script, home, environment, bash, root, name) -> dict:
    """Run a syntax scenario's shell as ``bash -n <script>``; no probe or state exists."""
    if scenario.observation_kind != SYNTAX:
        raise ValueError(
            f"{scenario.id} is a {scenario.observation_kind} scenario; "
            "only syntax scenarios run bash -n <script>"
        )
    (shell,) = scenario.shells
    return run_script(shell.options, script, home, environment, bash, root, name)


def observe_syntax_scenario(scenario, fixtures, home, environment, bash, root) -> dict:
    """Run a positive control, then ``-n`` on valid and invalid scripts.

    ``BASH_ENV`` names a fixture script for every run. The ordinary control must
    create both script and ``BASH_ENV`` sentinels; only those sentinels are then
    removed before the syntax-only runs.
    """
    if scenario.observation_kind != SYNTAX:
        raise ValueError(f"{scenario.id} is not a syntax scenario")
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    markers = fixtures["markers"]
    environment = {**environment, "BASH_ENV": str(fixtures["bash_env"])}

    def snapshot() -> dict:
        state = {}
        for marker, path in markers.items():
            if path.is_file():
                state[marker] = path.read_text(encoding="utf-8")
            else:
                state[marker] = "<not a regular file>" if os.path.lexists(path) else None
        return state

    observations = {
        "scenario": scenario.id,
        "observation_kind": scenario.observation_kind,
        "fixtures": {
            name: str(fixtures[name]) for name in ("directory", "valid", "invalid", "bash_env")
        },
        "markers": {marker: str(path) for marker, path in markers.items()},
        "environment": environment,
        "before": snapshot(),
    }
    observations["control"] = run_script(
        (), fixtures["valid"], home, environment, bash, root, "control-valid"
    )
    observations["after_control"] = snapshot()
    for path in markers.values():
        if path.is_file():
            path.unlink()
    observations["after_reset"] = snapshot()
    for name in ("valid", "invalid"):
        observations[name] = run_syntax_check(
            scenario, fixtures[name], home, environment, bash, root, f"noexec-{name}"
        )
        observations[f"after_{name}"] = snapshot()
    (root / "syntax-observations.json").write_text(
        json.dumps(observations, indent=2), encoding="utf-8"
    )
    return observations


def check_syntax_observations(observations: dict) -> None:
    """Assert ``-n`` parsed without executing the script or ``BASH_ENV``."""
    absent = dict.fromkeys(SYNTAX_MARKERS)
    assert observations["before"] == absent, observations["before"]
    control = observations["control"]
    assert (control["status"], control["stdout"], control["stderr"]) == (0, "", ""), control
    assert observations["after_control"] == {
        "valid": "valid-script\n",
        "invalid": None,
        "bash_env": "bash-env\n",
    }, observations["after_control"]
    assert observations["after_reset"] == absent, observations["after_reset"]

    valid = observations["valid"]
    assert (valid["status"], valid["stdout"], valid["stderr"]) == (0, "", ""), valid
    assert observations["after_valid"] == absent, observations["after_valid"]

    invalid = observations["invalid"]
    assert invalid["status"] != 0, invalid
    assert invalid["stdout"] == "", invalid
    assert "syntax error" in invalid["stderr"], invalid
    assert observations["fixtures"]["invalid"] in invalid["stderr"], invalid
    assert observations["after_invalid"] == absent, observations["after_invalid"]
