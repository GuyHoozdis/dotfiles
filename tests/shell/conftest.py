"""Pytest configuration and lazy guest-only fixtures for shell scenarios."""

import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

SCENARIO_MARKERS = ("characterization", "acceptance", "bash")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register explicit guest scenario inputs."""
    group = parser.getgroup("shell scenarios")
    group.addoption(
        "--shell-bash",
        metavar="PATH",
        help="explicit Bash executable for shell scenario tests",
    )
    group.addoption(
        "--shell-guest-root",
        metavar="PATH",
        help="writable root for test-owned guest files; this is not a security sandbox",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Validate guest inputs only when scenario tests are collected."""
    if not any(
        item.get_closest_marker(marker) is not None
        for item in items
        for marker in SCENARIO_MARKERS
    ):
        return

    missing = [
        option
        for option, value in (
            ("--shell-bash", config.getoption("--shell-bash")),
            ("--shell-guest-root", config.getoption("--shell-guest-root")),
        )
        if not value
    ]
    if missing:
        raise pytest.UsageError(
            "shell scenario tests require explicit " + " and ".join(missing)
        )

    bash_path = Path(config.getoption("--shell-bash")).expanduser()
    if not bash_path.is_file() or not os.access(bash_path, os.X_OK):
        raise pytest.UsageError(f"--shell-bash is not an executable file: {bash_path}")
    try:
        result = subprocess.run(
            [str(bash_path), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise pytest.UsageError(f"could not validate --shell-bash {bash_path}: {error}") from error

    version_line = next(
        (line for line in result.stdout.splitlines() if line.startswith("GNU bash,")),
        None,
    )
    if result.returncode != 0 or version_line is None:
        raise pytest.UsageError(f"--shell-bash did not report a valid Bash version: {bash_path}")

    guest_root = Path(config.getoption("--shell-guest-root")).expanduser()
    try:
        guest_root = guest_root.resolve(strict=True)
    except OSError as error:
        raise pytest.UsageError(f"--shell-guest-root is not an existing directory: {guest_root}") from error
    if not guest_root.is_dir() or not os.access(guest_root, os.W_OK | os.X_OK):
        raise pytest.UsageError(f"--shell-guest-root is not a writable directory: {guest_root}")
    try:
        with tempfile.TemporaryDirectory(prefix=".pytest-shell-check-", dir=guest_root):
            pass
    except OSError as error:
        raise pytest.UsageError(f"--shell-guest-root is not writable: {guest_root}: {error}") from error

    config._shell_bash_path = bash_path
    config._shell_bash_version = version_line
    config._shell_guest_root = guest_root


@pytest.fixture(scope="session")
def shell_bash(pytestconfig: pytest.Config) -> Path:
    """Return the validated scenario Bash executable."""
    return pytestconfig._shell_bash_path


@pytest.fixture(scope="session")
def shell_bash_version(pytestconfig: pytest.Config) -> str:
    """Return the validated scenario Bash version line."""
    return pytestconfig._shell_bash_version


@pytest.fixture(scope="session")
def shell_guest_root(pytestconfig: pytest.Config) -> Path:
    """Return the validated root for scenario-owned files."""
    return pytestconfig._shell_guest_root


def _bare_shell_environment(home: Path, bash: Path) -> dict[str, str]:
    """Build the controlled environment used by bare Bash startup tests."""
    user = pwd.getpwuid(os.getuid()).pw_name
    return {
        "HOME": str(home),
        "USER": user,
        "LOGNAME": user,
        "SHELL": os.path.abspath(bash),
        "LANG": "C",
        "LC_ALL": "C",
        "TERM": "dumb",
        "TERM_PROGRAM": "shell-startup-baseline",
        "HISTFILE": str(home / "history"),
        "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    }


@pytest.fixture
def bash_home(shell_tmp_factory: pytest.TempPathFactory, shell_bash: Path) -> dict:
    """Provide an empty home and controlled environment for Bash suite tests."""
    root = shell_tmp_factory.mktemp("bash")
    home = root / "home"
    home.mkdir()
    return {
        "root": root,
        "home": home,
        "environment": _bare_shell_environment(home, shell_bash),
        "bash": shell_bash,
    }


@pytest.fixture(scope="session")
def shell_tmp_factory(
    shell_guest_root: Path, pytestconfig: pytest.Config
) -> pytest.TempPathFactory:
    """Keep pytest's scenario temporary storage under the explicit guest root."""
    owned = Path(tempfile.mkdtemp(prefix="shell-pytest-", dir=shell_guest_root))
    factory = pytest.TempPathFactory.from_config(pytestconfig, _ispytest=True)
    factory._given_basetemp = owned / "pytest"
    return factory


@pytest.fixture
def dotfiles_home(
    request: pytest.FixtureRequest,
    shell_tmp_factory: pytest.TempPathFactory,
    shell_bash: Path,
) -> dict:
    """Install tracked dotfiles and optional synthetic local overrides."""
    return _create_dotfiles_home(
        getattr(request, "param", "tracked"),
        shell_tmp_factory,
        shell_bash,
    )


def _create_dotfiles_home(
    configuration: str,
    shell_tmp_factory: pytest.TempPathFactory,
    shell_bash: Path,
) -> dict:
    """Build an isolated home for one dotfiles fixture configuration."""
    configurations = {"tracked", "tracked+local", "tracked-home-spaces"}
    if configuration not in configurations:
        raise ValueError(f"unknown dotfiles home configuration: {configuration}")

    root = shell_tmp_factory.mktemp("scenario")
    home_name = "home with spaces" if configuration == "tracked-home-spaces" else "home"
    home = root / home_name
    config = home / ".local/etc/bashrc.d"
    config.mkdir(parents=True)
    source = Path(__file__).resolve().parents[2]
    shutil.copyfile(source / "etc/bash_profile.bash", home / ".bash_profile")
    shutil.copyfile(source / "etc/bashrc.bash", home / ".bashrc")
    if (source / ".git").exists():
        tracked_modules = subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "ls-files",
                "-z",
                "--",
                "etc/bashrc.d/*.bash",
            ],
            check=True,
            capture_output=True,
        ).stdout.decode().split("\0")
    else:
        # The guest source archive contains only tracked, allowlisted modules.
        tracked_modules = [
            str(path.relative_to(source))
            for path in sorted((source / "etc/bashrc.d").glob("*.bash"))
        ]
    modules = []
    for relative_path in tracked_modules:
        if not relative_path or relative_path.endswith(".local.bash"):
            continue
        path = Path(relative_path)
        shutil.copyfile(source / path, config / path.name)
        modules.append(path.stem)

    local_functions = {}
    if configuration == "tracked+local":
        for module in modules:
            function = "dotfiles_local_" + module.replace("-", "_")
            local_functions[module] = function
            lines = [
                f"{function}() {{ :; }}",
                f'LOCAL_LOG="${{LOCAL_LOG-}}{module}.local;"',
            ]
            if module == "aliases":
                lines.append("alias ll=local-override")
            (config / f"{module}.local.bash").write_text(
                "\n".join(lines) + "\n",
                encoding="utf-8",
            )

    managed = [
        home / ".local/bin",
        home / "node_modules/.bin",
        home / ".n/bin",
        home / ".rbenv/shims",
        home / ".pyenv/shims",
        home / ".go/bin",
        home / ".bun/bin",
        home / ".dotnet/tools",
    ]
    callers = [root / "caller one/bin", root / "caller two/bin"]
    marker = "shell_fixture_" + uuid.uuid4().hex
    identities = {}
    for index, directory in enumerate(managed + callers):
        directory.mkdir(parents=True, exist_ok=True)
        executable = directory / marker
        identity = f"marker-{index}"
        executable.write_text(f"#!/bin/sh\nprintf '%s\\n' '{identity}'\n")
        executable.chmod(0o755)
        identities[str(executable)] = identity

    user = pwd.getpwuid(os.getuid()).pw_name
    initial_path = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    environment = {
        "HOME": str(home),
        "USER": user,
        "LOGNAME": user,
        "SHELL": str(shell_bash),
        "LANG": "C",
        "LC_ALL": "C",
        "TERM": "dumb",
        "TERM_PROGRAM": "dotfiles-shell-fixture",
        "HISTFILE": str(root / "history"),
        "PATH": initial_path,
        "SHELL_MARKER": marker,
    }
    return {
        "root": root,
        "home": home,
        "configuration": configuration,
        "modules": modules,
        "local_functions": local_functions,
        "bash": os.path.abspath(shell_bash),
        "python": os.path.abspath(sys.executable),
        "managed": [str(path) for path in managed],
        "initial_path": initial_path.split(":"),
        "callers": [str(path) for path in callers],
        "marker": marker,
        "identities": identities,
        "environment": environment,
    }
