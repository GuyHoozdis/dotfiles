"""Shared Bash probe and scenario runner."""

import inspect
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


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
