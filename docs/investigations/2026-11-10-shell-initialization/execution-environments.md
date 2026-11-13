# Execution environments: fixtures, hosted runners, and local VMs

Date: 2026-11-10

Status: comparison for discussion, followed by an authorized
[local Tart macOS experiment](tart-experiment.md) and
[Ubuntu experiment](tart-ubuntu-experiment.md). Both support direct guest-agent
execution and disposable-clone reset. No harness or Actions workflow has been
implemented. Statements below about tools not being installed describe
the initial research, before that experiment.

## Separate the test harness from its execution environment

Pytest and HOME fixtures define scenarios, set up files and caller environments,
launch Bash processes, and assert outcomes. They can run on a developer machine,
in a container, or inside a real macOS/Linux VM.

The meaningful choice is whether acceptance tests simulate system startup or
execute the real startup chain in a disposable OS. These are complementary
layers, not competing Python-versus-VM approaches.

## Comparison

| Environment | Strengths | Limitations |
|-------------|-----------|-------------|
| Controlled native fixtures | Fast feedback; precise pathological inputs; safe local checks with stubbed dependencies; easy failure inspection | Simulated profile dispatch and tool behavior can miss the actual bug; cannot intercept absolute Homebrew calls merely by changing PATH |
| GitHub-hosted macOS/Ubuntu VMs | Real kernel, Bash, system profiles, `path_helper` on macOS, and installed-tool interaction; fresh job environment; directly supports future CI | Queue/setup latency, network/tool downloads, usage costs depending on repository/runner type, and preconfigured images that evolve; not a fresh consumer installation or GUI terminal session |
| Local macOS VM | Real macOS startup with interactive debugging and a reusable clean baseline; optional GUI terminal reproduction; disposable guest changes protect host configuration | Guest image storage/RAM, setup and update maintenance, platform/licensing requirements; shared host folders and credentials can undermine isolation |
| Local Linux VM/container | VM provides full OS semantics; containers provide inexpensive reproducible userspace and are realistic for devcontainer targets | Containers do not reproduce macOS or every VM/service/login behavior; each image covers only its own distribution/setup |
| act | Useful for checking Actions wiring and local Linux container execution | Container images differ from hosted runner images; no built-in disposable macOS VM; direct-host mode is not safe isolation |

## GitHub-hosted VM acceptance tests

Use explicit supported macOS and Ubuntu runner labels rather than relying solely
on `-latest`. An explicit OS label does not pin the complete image: record image
version, architecture, Bash versions, system startup files, relevant installed
tools, and initial PATH in diagnostics.

A real-OS test should construct a temporary HOME and invoke the selected Bash
explicitly as login/non-login and interactive/non-interactive. Ordinary workflow
`run` steps are not themselves a test of login startup; see
[Actions shell invocation](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsshell).
Keep pytest/tooling dependencies outside the fixture HOME where possible.

Test the real repository configuration without a test-only PATH repair.
Use real optional tools for integration cases that require them; use fixture
marker executables for precedence collisions. A missing-tool case needs an
environment where the tool is actually absent or a genuine approved discovery
boundary, not a fake PATH that leaves an absolute installation reachable.

Within a dedicated disposable job, we can deliberately prepare system-level
fixtures or tools at fixed paths if needed. Keep that separate from the
unmodified-system-profile cases and never apply those operations on a developer
host. Prefer separate jobs/baselines for conflicting installed/missing-tool
setups. Serial scenarios still need reset between tests: a VM is fresh per job,
not per pytest case.

A CI VM can cover system terminal dispatch with controlled TERM_PROGRAM and
session markers, but claiming actual Terminal.app/iTerm/VS Code/Herdr behavior
requires launching and observing those applications. A PTY exercises prompts;
it does not create an authentic GUI launcher environment by itself.

GitHub documents standard macOS/Ubuntu runners as fresh VMs, with exceptions such
as `ubuntu-slim`, which is container-based. Standard runner usage is free for
public repositories; private-repository usage draws from included/paid usage.
Repository visibility and exact billing have not been checked here.

## act: what the installed command can and cannot do

`gh act -h` succeeds locally and exposes runner mappings through `-P`.
The [act runner documentation](https://nektosact.com/usage/runners.html#runners)
states that default local runners use containers. Mapping a platform to
`-self-hosted` executes directly on the host; it does not provision a VM.

Therefore:

- act on this Mac can run Linux-container jobs, with documented environment
  differences from GitHub-hosted VMs.
- Mapping a macOS job to direct-host execution would expose the working machine
  to its setup steps. Do not run disposable-guest provisioning that way.
- act could run inside a separately provisioned macOS VM, but then that VM
  provides the isolation; act merely executes workflow steps.
- act is optional. We can run pytest directly in a local guest and let Actions
  call the same command remotely, without reproducing the Actions engine locally.

## Local macOS options

- [Tart](https://tart.run/#virtualization-and-beyond): automation-oriented
  macOS/Linux VMs on Apple Silicon using Apple's Virtualization framework, with
  image/clone workflows. Promising for repeatable disposable test guests.
- [UTM](https://getutm.app/#virtualize-macos-as-well): macOS virtualization on
  Apple Silicon, plus Linux VM options; useful for interactive guest exploration.
  Its [CLI/scripting interface](https://docs.getutm.app/scripting/scripting/)
  can support automation.

No product was installed or selected. Verify host compatibility, guest licensing,
tool licensing, image provenance, and clone/reset behavior before choosing one.
Do not assume arbitrary VM images reproduce GitHub runner images.

## Revised recommendation

Make real macOS and Ubuntu VM runs the primary system-startup acceptance evidence,
using pytest HOME fixtures as the scenario driver. Keep controlled local tests
for inexpensive repeatability and targeted cases, but do not make a large
simulated startup system a prerequisite to the first real reproduction.

Start with GitHub-hosted runners if remote turnaround is acceptable. Add a local
macOS VM if debugging latency or GUI launcher reproduction justifies its setup.
Do not require act for either approach.

This reduces the need to modify production initialization solely to intercept
absolute tool calls during tests. A small dependency boundary may still improve
the production design, but it should be justified independently rather than
required by a host-only test strategy.

This revises the earlier controlled-driver-first proposal. Environment choice
and the first execution experiment still need agreement.

## Local-first Tart alternative

Subsequent user direction: evaluate local Tart macOS/Linux VMs for detailed
scenario coverage, with GitHub-hosted images providing a smaller durable
regression suite later. GitHub Actions can be deferred; installing a GitHub App
is not an available integration path.

This is a sound alternative to the earlier hosted-first recommendation:

- Keep pytest and scenario assertions independent of the VM driver. Run the
  same test code inside local guests and, later, GitHub-hosted runners.
- Begin with one macOS guest and one Ubuntu guest, selected versions/image
  identities, a clean baseline, disposable run clones, and captured diagnostics.
  Add broader matrices only when evidence warrants them.
- Separate cheap HOME resets from guest-wide mutations. HOME-only cases can
  share a guest when their state is isolated; package/system-file changes need
  a fresh clone or equivalent verified reset.
- Do not forward personal credentials or mount the host HOME. Copy the worktree
  into the guest or expose only the required source directory read-only.
- Later CI should retain representative startup and caller-override cases as
  well as install/reinstall/uninstall/selective-install checks. A smoke suite
  should not discard the regressions that motivated this investigation.

[Testcontainers](https://testcontainers.com/) primarily drives Docker-compatible
containers, not Tart VMs. It is not a necessary abstraction here; direct Tart
lifecycle orchestration and pytest are sufficient for an initial experiment.

[Cirrus CLI's Tart integration](https://tart.run/integrations/cirrus-cli/#cirrus-cli)
can run local tasks, copy source, and retrieve artifacts without subscribing to
Cirrus CI or installing a GitHub App. However, its
[documented supported execution types](https://github.com/cirruslabs/cirrus-cli#running-cirrus-tasks)
are Linux containers and macOS VMs. Do not assume it also drives Linux Tart VMs;
verify that specific capability before selecting it as a unified orchestrator.
Direct Tart plus guest SSH remains an option for both guest OSes.

Recommended next experiment: verify host resources and tool/image provenance,
then boot one disposable macOS guest, execute a real login-shell reproduction,
retrieve diagnostics, and validate stop/reset behavior. Repeat with Ubuntu
before investing in a full orchestrator. Tart and Cirrus CLI were not found on
PATH during the read-only check. No installation or image download was performed.

The [Tart quick start](https://tart.run/quick-start/#vm-images) lists macOS and
Linux guest images; its example macOS download is approximately 25 GB. Budget
disk and memory before provisioning. These are VMs, not containers, even though
images can be distributed through OCI registries.

The Tart repository URL redirected during research, and its installation
instructions differed from the website's Homebrew tap instructions. Verify the
current authoritative distribution and license before installing; do not blindly
reuse a previously fetched installation command.

## Sources

- [GitHub-hosted runners and VM/container distinctions](https://docs.github.com/en/actions/reference/runners/github-hosted-runners#supported-runners-and-hardware-resources)
- [Public runner availability and usage](https://docs.github.com/en/actions/reference/runners/github-hosted-runners#standard-github-hosted-runners-for-public-repositories)
- [Runner images and included software](https://github.com/actions/runner-images#available-images)
- [act runners and direct-host mappings](https://nektosact.com/usage/runners.html#runners)
- [act image differences](https://nektosact.com/usage/runners.html#default-runners-are-intentionally-incomplete)

Documentation consulted 2026-11-10. No current price figures or claims about
unverified local virtualization installations are assumed.
