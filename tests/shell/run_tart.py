#!/usr/bin/env -S uv run --script
"""Run the guest-native shell scenarios in an isolated Tart clone."""

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import time
import tomllib
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit


IMAGES = {
    "macos": "ghcr.io/cirruslabs/macos-tahoe-base@sha256:65c3133a633fda8753cf1f71f2d55727792d534a2125b0032466563dcc8e58fd",
    "ubuntu": "ghcr.io/cirruslabs/ubuntu@sha256:97166c84ea5f102be33d2959f70e83861a36bd749f1715ab669d93e6c9f31476",
}
UV_VERSION = "0.13.7"
UV_ASSETS = {
    "macos": (
        "uv-aarch64-apple-darwin.tar.gz",
        "81b811b57e4624df7ed3aac148e0359100d9962f3d9dce00aec533dc2e086731",
    ),
    "ubuntu": (
        "uv-aarch64-unknown-linux-gnu.tar.gz",
        "71279f8d3c67241e807b9d8db872d1bf541579fb9f08b7d1eb1682196d1e57dc",
    ),
}
SOURCE_FILES = (
    "etc/bash_profile.bash",
    "etc/bashrc.bash",
    "tests/shell/conftest.py",
    "tests/shell/scenarios.py",
    "tests/shell/probe.py",
    "tests/shell/test_bash.py",
    "tests/shell/test_dotfiles.py",
    "pyproject.toml",
    "uv.lock",
)
GUEST_ROOT = "/tmp/dotfiles-shell-harness"
READINESS_TIMEOUT = 180
READINESS_TIMEOUTS = {"macos": 600, "ubuntu": READINESS_TIMEOUT}
READINESS_INTERVAL = 2
READINESS_COMMAND_TIMEOUT = 10
# The macOS guest agent reports 125 for silent commands such as /bin/true.
READINESS_SENTINEL = "READY"
STOP_TIMEOUT = 30


class HarnessError(RuntimeError):
    """A setup, guest, artifact, or lifecycle operation failed."""


class CommandLog:
    def __init__(self, artifact_dir: Path):
        self.artifact_dir = artifact_dir
        self.records = []

    @staticmethod
    def _output(value):
        if value is None:
            return ""
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return {
                    "binary_bytes": len(value),
                    "sha256": hashlib.sha256(value).hexdigest(),
                }
        return value

    def run(self, argv, *, cwd=None, env=None, input_data=None, timeout=None, binary=False):
        options = {
            "capture_output": True,
            "check": False,
            "timeout": timeout,
            "cwd": cwd,
            "env": env,
            "input": input_data,
            "text": not binary and not isinstance(input_data, bytes),
        }
        try:
            result = subprocess.run(argv, **options)
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or ""
            stderr = error.stderr or ""
            if not binary:
                if isinstance(stdout, bytes):
                    stdout = stdout.decode("utf-8", errors="replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode("utf-8", errors="replace")
            self.records.append(
                {
                    "argv": [str(part) for part in argv],
                    "status": 124,
                    "stdout": self._output(stdout),
                    "stderr": self._output(stderr),
                }
            )
            return subprocess.CompletedProcess(argv, 124, stdout, stderr)
        except OSError as error:
            self.records.append(
                {
                    "argv": [str(part) for part in argv],
                    "status": None,
                    "stdout": "",
                    "stderr": str(error),
                }
            )
            raise
        self.records.append(
            {
                "argv": [str(part) for part in argv],
                "status": result.returncode,
                "stdout": self._output(result.stdout),
                "stderr": self._output(result.stderr),
            }
        )
        return result

    def record_process(self, argv, process, stdout_path, stderr_path):
        self.records.append(
            {
                "argv": [str(part) for part in argv],
                "status": process.returncode,
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
            }
        )
        return self.records[-1]

    def write(self):
        path = self.artifact_dir / "host-commands.json"
        path.write_text(json.dumps(self.records, indent=2) + "\n", encoding="utf-8")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, choices=tuple(IMAGES))
    parser.add_argument("--bash", default="/bin/bash", help="guest Bash executable (default: /bin/bash)")
    parser.add_argument(
        "--suite",
        required=True,
        choices=("bash", "dotfiles"),
    )
    parser.add_argument("--marker", choices=("characterization", "acceptance"))
    parser.add_argument("--artifacts", required=True, type=Path)
    return parser.parse_args(argv)


def prepare_artifacts(path):
    if path.is_symlink():
        raise HarnessError(f"artifact destination must not be a symlink: {path}")
    if path.exists():
        if not path.is_dir():
            raise HarnessError(f"artifact destination is not a directory: {path}")
        if any(path.iterdir()):
            raise HarnessError(f"artifact destination is not empty: {path}")
    else:
        path.mkdir(parents=True)
    return path.resolve()


def regular_source(root: Path, relative: str) -> tuple[Path, bytes]:
    path = root
    for component in PurePosixPath(relative).parts:
        path = path / component
        if path.is_symlink():
            raise HarnessError(f"refusing symlinked source input: {relative}")
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as error:
        raise HarnessError(f"cannot read source input {relative}: {error}") from error
    if not path.is_file() or not metadata:
        raise HarnessError(f"source input is not a regular file: {relative}")
    return path, path.read_bytes()


def source_files(root: Path):
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", *SOURCE_FILES, "etc/bashrc.d/*.bash"],
            cwd=root, capture_output=True, check=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise HarnessError(f"could not list git source files: {error}") from error
    tracked = {os.fsdecode(name) for name in result.stdout.split(b"\0") if name}
    missing = set(SOURCE_FILES) - tracked
    if missing:
        raise HarnessError(f"required source files are not tracked: {', '.join(sorted(missing))}")
    modules = sorted(
        name for name in tracked
        if PurePosixPath(name).parent == PurePosixPath("etc/bashrc.d")
        and name.endswith(".bash") and not name.endswith(".local.bash")
    )
    return (*SOURCE_FILES, *modules)


def source_archive(root: Path):
    stream = io.BytesIO()
    hashes = {}
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for relative in source_files(root):
            path, data = regular_source(root, relative)
            info = tarfile.TarInfo(relative)
            info.size = len(data)
            info.mode = path.stat(follow_symlinks=False).st_mode & 0o777
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.pax_headers = {}
            archive.addfile(info, io.BytesIO(data))
            hashes[relative] = hashlib.sha256(data).hexdigest()
    return stream.getvalue(), hashes


def git_state(log: CommandLog, root: Path):
    revision = log.run(
        ["git", "rev-parse", "HEAD"], cwd=root, timeout=10
    )
    if revision.returncode:
        raise HarnessError(f"could not read git revision: {revision.stderr}")
    dirty = log.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        timeout=10,
    )
    if dirty.returncode:
        raise HarnessError(f"could not read git dirty status: {dirty.stderr}")
    return revision.stdout.strip(), bool(dirty.stdout.strip())


def guest_command(log: CommandLog, clone: str, command, *, input_data=None, binary=False, timeout=180):
    argv = ["tart", "exec"]
    if input_data is not None:
        argv.append("-i")
    argv.extend([clone, *command])
    return log.run(
        argv,
        input_data=input_data,
        binary=binary,
        timeout=timeout,
    )


def require_success(result, operation):
    if result.returncode:
        detail = result.stderr.decode(errors="replace") if isinstance(result.stderr, bytes) else result.stderr
        raise HarnessError(f"{operation} failed with status {result.returncode}: {detail.strip()}")


def safe_extract_results(archive_bytes: bytes, destination: Path):
    seen = {}
    safe_members = []
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        members = archive.getmembers()
        for member in members:
            name = member.name
            raw_path = name[:-1] if name.endswith("/") else name
            parts = raw_path.split("/")
            if (
                not name
                or "\\" in name
                or name.startswith("/")
                or any(part in ("", ".", "..") for part in parts)
                or not (member.isdir() or member.isfile() or member.issym())
                or (name.endswith("/") and not member.isdir())
            ):
                raise HarnessError(f"unsafe artifact archive entry: {name!r}")
            normalized = "/".join(parts)
            if normalized in seen:
                raise HarnessError(f"duplicate artifact archive entry: {name!r}")
            seen[normalized] = (
                "directory" if member.isdir()
                else "symlink" if member.issym()
                else "file"
            )
            safe_members.append((member, normalized))
        for _, name in safe_members:
            parts = PurePosixPath(name).parts
            for index in range(1, len(parts)):
                parent = "/".join(parts[:index])
                if seen.get(parent) in {"file", "symlink"}:
                    raise HarnessError(f"unsafe artifact path: {name!r}")
        skipped_symlinks = 0
        for member, normalized in safe_members:
            # pytest's basetemp keeps *current symlinks; never recreate or follow them.
            if member.issym():
                skipped_symlinks += 1
                continue
            target = destination.joinpath(*PurePosixPath(normalized).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise HarnessError(f"could not read artifact entry: {member.name}")
            with target.open("xb") as output:
                output.write(source.read())
            target.chmod(member.mode & 0o777)
    return skipped_symlinks


def validate_junit_result(destination: Path):
    junit = destination / "results/pytest.xml"
    if not junit.is_file():
        raise HarnessError("artifact collection is missing results/pytest.xml")
    try:
        root = ET.parse(junit).getroot()
    except (ET.ParseError, OSError) as error:
        raise HarnessError(f"artifact collection contains invalid JUnit XML: {error}") from error
    if root.tag not in {"testsuite", "testsuites"}:
        raise HarnessError(f"artifact collection contains invalid JUnit root element: {root.tag!r}")


def bootstrap_command(image):
    asset, digest = UV_ASSETS[image]
    script = r'''
import hashlib, io, pathlib, sys, tarfile
version, asset, expected, target = sys.argv[1:]
bundle = sys.stdin.buffer.read()
with tarfile.open(fileobj=io.BytesIO(bundle), mode="r:") as package:
    members = package.getmembers()
    if len(members) != 2 or any(not item.isfile() for item in members):
        raise SystemExit("invalid uv bootstrap bundle contents")
    if {item.name for item in members} != {"sha256.sum", asset}:
        raise SystemExit("invalid uv bootstrap bundle entries")
    files = {}
    for member in members:
        source = package.extractfile(member)
        if source is None:
            raise SystemExit(f"could not read uv bootstrap entry: {member.name}")
        files[member.name] = source.read()
metadata = files["sha256.sum"].decode("ascii")
published = None
for line in metadata.splitlines():
    fields = line.split()
    if len(fields) == 2 and fields[1].lstrip("*") == asset:
        published = fields[0].lower()
        break
if published != expected:
    raise SystemExit(f"official uv checksum metadata mismatch for {asset}: {published!r}")
payload = files[asset]
actual = hashlib.sha256(payload).hexdigest()
if actual != expected:
    raise SystemExit(f"uv archive checksum mismatch: {actual}")
with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
    matches = [item for item in archive.getmembers() if item.name.endswith("/uv") and item.isfile()]
    if len(matches) != 1:
        raise SystemExit("uv release archive has no unique regular uv executable")
    member = matches[0]
    source = archive.extractfile(member)
    if source is None:
        raise SystemExit("could not read uv executable from release archive")
    destination = pathlib.Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read())
    destination.chmod(0o755)
'''
    interpreter = "/opt/homebrew/bin/python3" if image == "macos" else "/usr/bin/python3"
    target = f"{GUEST_ROOT}/bin/uv"
    return interpreter, script, asset, digest, target


def fetch_uv_bootstrap_bundle(image):
    asset, _ = UV_ASSETS[image]
    base = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}"

    def download(filename):
        url = f"{base}/{filename}"
        request = urllib.request.Request(
            url, headers={"User-Agent": "dotfiles-shell-fixture"}
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (OSError, urllib.error.URLError) as error:
            raise HarnessError(f"could not download pinned uv release file {filename}: {error}") from error

    files = {
        "sha256.sum": download("sha256.sum"),
        asset: download(asset),
    }
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, content in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            member.mode = 0o600
            member.mtime = 0
            archive.addfile(member, io.BytesIO(content))
    return stream.getvalue()


def fetch_locked_wheelhouse(root: Path):
    try:
        lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HarnessError(f"could not read locked dev dependencies: {error}") from error
    packages = lock.get("package")
    if not isinstance(packages, list):
        raise HarnessError("uv.lock has no package list")
    by_name = {}
    for package in packages:
        name = package.get("name")
        if not isinstance(name, str) or name in by_name:
            raise HarnessError(f"uv.lock has an invalid or ambiguous package: {name!r}")
        by_name[name] = package
    roots = [
        package for package in packages
        if package.get("source", {}).get("virtual") == "."
    ]
    if len(roots) != 1:
        raise HarnessError("uv.lock must contain exactly one virtual project")
    dev_dependencies = roots[0].get("dev-dependencies", {}).get("dev", [])
    pending = [dependency.get("name") for dependency in dev_dependencies]
    required = set()
    while pending:
        name = pending.pop()
        if not isinstance(name, str):
            raise HarnessError("uv.lock contains an invalid dev dependency")
        if name in required:
            continue
        package = by_name.get(name)
        if package is None:
            raise HarnessError(f"uv.lock is missing dev dependency {name!r}")
        required.add(name)
        pending.extend(
            dependency.get("name")
            for dependency in package.get("dependencies", [])
        )

    wheels = {}
    for name in sorted(required):
        package = by_name[name]
        candidates = [
            wheel for wheel in package.get("wheels", [])
            if urlsplit(wheel.get("url", "")).path.endswith(
                ("-py3-none-any.whl", "-py2.py3-none-any.whl")
            )
        ]
        if len(candidates) != 1:
            raise HarnessError(
                f"dev dependency {name!r} has no unique universal wheel for offline transfer"
            )
        wheel = candidates[0]
        parsed = urlsplit(wheel["url"])
        filename = Path(parsed.path).name
        digest = wheel.get("hash", "")
        if (
            parsed.scheme != "https"
            or parsed.hostname != "files.pythonhosted.org"
            or not filename
            or not filename.endswith(".whl")
            or not digest.startswith("sha256:")
            or len(digest) != 71
        ):
            raise HarnessError(f"uv.lock has an invalid wheel record for {name!r}")
        request = urllib.request.Request(
            wheel["url"], headers={"User-Agent": "dotfiles-shell-fixture"}
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
        except (OSError, urllib.error.URLError) as error:
            raise HarnessError(
                f"could not download locked dev wheel {filename}: {error}"
            ) from error
        actual = hashlib.sha256(payload).hexdigest()
        if actual != digest.removeprefix("sha256:"):
            raise HarnessError(
                f"locked hash mismatch for dev wheel {filename}: {actual}"
            )
        if filename in wheels:
            raise HarnessError(f"duplicate dev wheel filename in uv.lock: {filename}")
        wheels[filename] = (payload, actual)

    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for filename, (payload, _) in wheels.items():
            member = tarfile.TarInfo(f"wheelhouse/{filename}")
            member.size = len(payload)
            member.mode = 0o600
            member.mtime = 0
            archive.addfile(member, io.BytesIO(payload))
    return stream.getvalue(), {
        filename: digest for filename, (_, digest) in wheels.items()
    }


def offline_install_commands(uv: str, interpreter: str):
    # `uv sync` follows lockfile registry URLs even with --find-links, so a
    # network-less guest installs the exported, hash-pinned lock instead.
    requirements = f"{GUEST_ROOT}/requirements.txt"
    venv = f"{GUEST_ROOT}/venv"
    return [
        [
            uv, "export", "--locked", "--offline", "--group", "dev",
            "--no-emit-project", "--format", "requirements.txt",
            "--output-file", requirements,
        ],
        [uv, "venv", "--offline", "--python", interpreter, venv],
        [
            uv, "pip", "install", "--offline", "--no-index",
            "--find-links", f"{GUEST_ROOT}/wheelhouse", "--require-hashes",
            "--python", f"{venv}/bin/python",
            "--requirement", requirements,
        ],
    ]


def parse_uv_version(output: str):
    """Return 'uv X.Y.Z' from `uv --version`, ignoring trailing build metadata."""
    fields = output.split()
    if (
        len(fields) >= 2
        and fields[0] == "uv"
        and all(part.isdigit() for part in fields[1].split("."))
        and len(fields[1].split(".")) == 3
    ):
        return f"uv {fields[1]}"
    return None


def ensure_guest_uv(log: CommandLog, clone: str, image: str, metadata: dict):
    interpreter, script, asset, digest, target = bootstrap_command(image)
    probe = guest_command(
        log,
        clone,
        [
            "/bin/bash",
            "-lc",
            'uv_path=$(command -v uv) || exit $?; printf "__DOTFILES_UV_PATH__%s\\n" "$uv_path"',
        ],
    )
    marker = "__DOTFILES_UV_PATH__"
    selected_uv = next(
        (
            line[len(marker):]
            for line in probe.stdout.splitlines()
            if line.startswith(marker)
        ),
        "",
    ) if probe.returncode == 0 else ""
    selected_version = None
    bootstrapped = False
    if selected_uv:
        existing_version = guest_command(log, clone, [selected_uv, "--version"])
        if existing_version.returncode == 0:
            selected_version = parse_uv_version(existing_version.stdout)
    if selected_version is None:
        bundle = fetch_uv_bootstrap_bundle(image)
        result = guest_command(
            log,
            clone,
            [interpreter, "-c", script, UV_VERSION, asset, digest, target],
            input_data=bundle,
            timeout=180,
        )
        require_success(result, "pinned uv bootstrap")
        selected_uv = target
        bootstrapped = True
        installed_version = guest_command(log, clone, [selected_uv, "--version"])
        require_success(installed_version, "bootstrapped uv version check")
        selected_version = parse_uv_version(installed_version.stdout)
        if selected_version != f"uv {UV_VERSION}":
            raise HarnessError(
                f"unexpected bootstrapped uv version: {installed_version.stdout.strip()!r}"
            )
    elif not selected_uv:
        require_success(probe, "uv executable check")
    metadata["uv_version"] = selected_version
    metadata["uv_path"] = selected_uv
    metadata["uv_asset"] = asset if bootstrapped else None
    metadata["uv_sha256"] = digest if bootstrapped else None
    return interpreter, selected_uv


def run_guest_workdir(log, clone, argv, *, timeout=600):
    return guest_command(
        log,
        clone,
        [
            "/bin/bash",
            "-c",
            'cd "$1" && shift && exec "$@"',
            "shell-harness",
            f"{GUEST_ROOT}/source",
            *argv,
        ],
        timeout=timeout,
    )


def wait_for_guest(log: CommandLog, clone: str, process, metadata: dict, image: str):
    timeout = READINESS_TIMEOUTS[image]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise HarnessError(f"tart run exited before guest-agent readiness: {process.returncode}")
        result = guest_command(
            log,
            clone,
            ["/usr/bin/printf", READINESS_SENTINEL],
            timeout=READINESS_COMMAND_TIMEOUT,
        )
        if result.returncode == 0 and result.stdout == READINESS_SENTINEL:
            return
        metadata["readiness_failures"].append({
            "attempt": len(metadata["readiness_failures"]) + 1,
            "status": result.returncode,
            "stderr": CommandLog._output(result.stderr),
        })
        time.sleep(READINESS_INTERVAL)
    raise HarnessError(
        f"guest agent readiness timed out after {timeout}s for {clone}"
    )


def clone_is_stopped(log: CommandLog, clone: str):
    result = log.run(["tart", "list", "--format", "json"], timeout=20)
    if result.returncode:
        return False, f"could not confirm {clone} stopped: {result.stderr}"
    try:
        machines = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as error:
        return False, f"could not parse Tart state while checking {clone}: {error}"
    if not isinstance(machines, list):
        return False, f"malformed Tart VM list while checking {clone}: expected a list"
    if any(
        not isinstance(item, dict)
        or not isinstance(item.get("Name"), str)
        or not isinstance(item.get("State"), str)
        for item in machines
    ):
        return False, f"malformed Tart VM list while checking {clone}: invalid VM record"
    record = next((item for item in machines if item["Name"] == clone), None)
    return (record is not None and record.get("State") == "stopped"), (
        "" if record is not None and record.get("State") == "stopped"
        else f"could not confirm owned clone {clone} is stopped"
    )


def cleanup_clone(log, clone, process, runner_logs, metadata):
    errors = []
    stopped = False
    deleted = False
    if clone is not None:
        try:
            stop = log.run(
                ["tart", "stop", clone, "--timeout", str(STOP_TIMEOUT)],
                timeout=STOP_TIMEOUT + 10,
            )
            if stop.returncode:
                errors.append(f"tart stop failed with status {stop.returncode}: {stop.stderr}")
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(f"could not stop owned clone {clone}: {error}")
        try:
            stopped, stop_error = clone_is_stopped(log, clone)
        except (OSError, subprocess.SubprocessError) as error:
            stop_error = f"could not confirm owned clone {clone} stopped: {error}"
        if not stopped:
            errors.append(stop_error)
        else:
            try:
                deletion = log.run(["tart", "delete", clone], timeout=60)
                if deletion.returncode:
                    errors.append(
                        f"tart delete failed with status {deletion.returncode}: {deletion.stderr}"
                    )
                else:
                    deleted = True
            except (OSError, subprocess.SubprocessError) as error:
                errors.append(f"could not delete stopped owned clone {clone}: {error}")
    if process is not None:
        try:
            if process.poll() is None:
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
            runner_logs["record"]["status"] = process.returncode
            runner_logs["record"]["stdout"] = runner_logs["stdout_path"].read_text(
                encoding="utf-8", errors="replace"
            )
            runner_logs["record"]["stderr"] = runner_logs["stderr_path"].read_text(
                encoding="utf-8", errors="replace"
            )
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(f"could not reap tart run process: {error}")
    metadata["clone_retained"] = clone if clone is not None and not deleted else None
    return errors


def execute(options):
    artifacts = prepare_artifacts(options.artifacts)
    root = Path(__file__).resolve().parents[2]
    log = CommandLog(artifacts)
    metadata = {
        "image": options.image,
        "image_reference": IMAGES[options.image],
        "suite": options.suite,
        "marker": options.marker,
        "bash": options.bash,
        "git_revision": None,
        "git_dirty": None,
        "source_sha256": {},
        "clone": None,
        "pytest_status": None,
        "readiness_failures": [],
        "uv_version": None,
        "uv_path": None,
        "uv_asset": None,
        "uv_sha256": None,
        "wheelhouse_sha256": {},
        "skipped_result_symlinks": None,
        "error": None,
        "cleanup_error": None,
        "clone_retained": None,
        "pty": False,
        "interactive_bash_note": "No guest PTY is allocated; interactive Bash may report that job control is unavailable.",
    }
    clone = None
    owned = False
    process = None
    runner_logs = None
    primary_error = None
    cleanup_errors = []
    try:
        metadata["git_revision"], metadata["git_dirty"] = git_state(log, root)
        source_data, metadata["source_sha256"] = source_archive(root)
        wheelhouse_data, metadata["wheelhouse_sha256"] = fetch_locked_wheelhouse(root)
        clone = f"dotfiles-shell-{options.image}-{uuid.uuid4().hex[:12]}"
        metadata["clone"] = clone
        clone_env = os.environ.copy()
        clone_env["TART_NO_AUTO_PRUNE"] = "1"
        clone_result = log.run(
            ["tart", "clone", IMAGES[options.image], clone],
            env=clone_env,
            timeout=900,
        )
        require_success(clone_result, "Tart clone")
        owned = True

        runner_argv = [
            "tart", "run", "--no-graphics", "--no-audio",
            "--no-usb-accessories", "--no-clipboard", clone,
        ]
        stdout_path = artifacts / "tart-run.stdout.log"
        stderr_path = artifacts / "tart-run.stderr.log"
        try:
            with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr:
                process = subprocess.Popen(
                    runner_argv,
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                )
        except OSError as error:
            log.records.append({
                "argv": runner_argv,
                "status": None,
                "stdout": "",
                "stderr": str(error),
            })
            raise
        runner_logs = {
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
        }
        runner_logs["record"] = log.record_process(
            runner_argv, process, stdout_path, stderr_path
        )
        wait_for_guest(log, clone, process, metadata, options.image)

        result = guest_command(
            log,
            clone,
            [
                "/bin/mkdir", "-p", f"{GUEST_ROOT}/source",
                f"{GUEST_ROOT}/results", f"{GUEST_ROOT}/wheelhouse",
            ],
        )
        require_success(result, "guest harness directory creation")
        result = guest_command(
            log,
            clone,
            ["/usr/bin/tar", "-xpf", "-", "-C", f"{GUEST_ROOT}/source"],
            input_data=source_data,
            timeout=120,
        )
        require_success(result, "source transfer")

        result = guest_command(
            log,
            clone,
            ["/usr/bin/tar", "-xpf", "-", "-C", GUEST_ROOT],
            input_data=wheelhouse_data,
            timeout=120,
        )
        require_success(result, "locked dev wheelhouse transfer")

        interpreter, uv = ensure_guest_uv(log, clone, options.image, metadata)
        for command in offline_install_commands(uv, interpreter):
            install = run_guest_workdir(log, clone, command)
            require_success(install, f"offline locked dependency install ({command[1]})")
        test_command = [
            f"{GUEST_ROOT}/venv/bin/python", "-m", "pytest",
            f"tests/shell/test_{options.suite}.py",
            "-rs",
            "--shell-bash", options.bash,
            "--shell-guest-root", f"{GUEST_ROOT}/results",
            "--basetemp", f"{GUEST_ROOT}/results/pytest",
            "--junitxml", f"{GUEST_ROOT}/results/pytest.xml",
        ]
        if options.marker:
            test_command.extend(["-m", options.marker])
        test_result = run_guest_workdir(log, clone, test_command)
        metadata["pytest_status"] = test_result.returncode
        (artifacts / "guest-stdout.log").write_text(
            test_result.stdout, encoding="utf-8"
        )
        (artifacts / "guest-stderr.log").write_text(
            test_result.stderr, encoding="utf-8"
        )

        collected = guest_command(
            log,
            clone,
            ["/usr/bin/tar", "-cf", "-", "-C", GUEST_ROOT, "results"],
            binary=True,
            timeout=180,
        )
        require_success(collected, "artifact collection")
        if not isinstance(collected.stdout, bytes):
            raise HarnessError("artifact collection returned no binary archive")
        metadata["skipped_result_symlinks"] = safe_extract_results(
            collected.stdout, artifacts
        )
        validate_junit_result(artifacts)
    except Exception as error:
        primary_error = str(error)
        metadata["error"] = primary_error
        print(f"error: {primary_error}", file=sys.stderr)
    finally:
        if owned:
            cleanup_errors = cleanup_clone(
                log, clone, process, runner_logs, metadata
            )
        if cleanup_errors:
            metadata["cleanup_error"] = "; ".join(cleanup_errors)
            print(f"cleanup error: {metadata['cleanup_error']}", file=sys.stderr)
        try:
            log.write()
            (artifacts / "run.json").write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as error:
            print(f"error: could not write run metadata: {error}", file=sys.stderr)
            return 1

    if primary_error or cleanup_errors:
        return 1
    return metadata["pytest_status"] or 0


def main(args):
    try:
        return execute(args)
    except (HarnessError, OSError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(parse_args()))
