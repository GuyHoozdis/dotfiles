# Local Tart macOS experiment

Date: 2026-11-11

Outcome: a disposable macOS VM reproduced the nested-login PATH regression using
real system profiles, Homebrew, and the repository's unmodified loader/exports.
Guest-agent command execution, diagnostic retrieval, stop, and fresh-clone reset
all worked. No production startup files were changed.

## Environment and isolation

| Component | Observed value |
|-----------|----------------|
| Host | Apple Silicon, macOS 26.7.1 (25G241), 64 GiB RAM, approximately 381 GiB initially free |
| Tart | 2.41.1, installed by the user |
| Image requested | `ghcr.io/cirruslabs/macos-tahoe-base:latest` |
| Resolved image | `ghcr.io/cirruslabs/macos-tahoe-base@sha256:65c3133a633fda8753cf1f71f2d55727792d534a2125b0032466563dcc8e58fd` |
| Guest | macOS 26.6.2 (25G83), arm64 |
| Guest Bash | `/bin/bash`, 3.2.57(1)-release |
| Image resources | 4 CPUs, 8192 MiB RAM, 50 GB virtual disk |
| Transfer/storage | 27.0 GB compressed download; Tart reported approximately 32 GB image size |
| Guest Homebrew | 7.0.12; includes rbenv, Node, Python, CI tooling, and guest agent |

This is a provisioned base image, not a pristine consumer macOS installation.
`latest` was resolved once; use the recorded digest to reproduce this baseline.
Tart's image and clone sizes must not be added together as physical consumption:
APFS clones share unchanged storage.

The VM ran headlessly with audio, USB accessories, and clipboard disabled.
No host directories, HOME, credentials, or personal local overrides were shared.
Only tracked `etc/bash_login.bash` and `etc/bashrc.d/exports.bash` from commit
`baa7227` were copied through the guest agent. Default VM networking was used.
`TART_NO_AUTO_PRUNE=1` disabled automatic cache reclamation during cloning.
No host DHCP settings were changed.

## Procedure

The baseline was never booted. Two disposable clones were booted sequentially.
The [Tart quick start](https://tart.run/quick-start/#vm-images) describes image
cloning; locally installed `tart clone/run/exec/stop/delete --help` supplied the
exact command options used here.

```bash
export TART_NO_AUTO_PRUNE=1
tart clone ghcr.io/cirruslabs/macos-tahoe-base:latest dotfiles-shell-base-20261111
tart clone dotfiles-shell-base-20261111 dotfiles-shell-probe-20261111
tart run --no-graphics --no-audio --no-usb-accessories --no-clipboard \
  dotfiles-shell-probe-20261111
```

`tart run` stays attached until shutdown; guest commands ran from another host
process. `tart list --format json` confirmed running state, and
`tart exec ... /usr/bin/sw_vers` confirmed agent readiness.

Inside the guest, `/tmp/dotfiles-shell-experiment/home` served as HOME:

- The tracked loader was copied to `.bash_login`.
- Only tracked `exports.bash` was placed in `.local/etc/bashrc.d/`.
- Empty `.local/bin`, `node_modules/.bin`, and `.bun/bin` directories enabled
  their existing directory-sensitive initialization.
- An arbitrary override directory was created at
  `/tmp/dotfiles-shell-experiment/caller/bin`.
- No `.bash_profile`, `.profile`, `.bashrc`, local modules, aliases, app config,
  or custom prompt were deployed.

The outer shell was invoked with a clean environment:

```bash
/usr/bin/env -i HOME=/tmp/dotfiles-shell-experiment/home \
  USER="$(id -un)" LOGNAME="$(id -un)" SHELL=/bin/bash \
  TERM=dumb TERM_PROGRAM=dotfiles-experiment \
  PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  /bin/bash --login -ic 'source /tmp/dotfiles-shell-experiment/outer.sh'
```

`outer.sh` captured PATH and SHLVL, then launched each child from that same outer
shell, not sequentially from one another:

```bash
printf 'PATH_FRESH=%s\nSHLVL_FRESH=%s\n' "$PATH" "$SHLVL"
/bin/bash --login -ic 'printf "PATH_NESTED=%s\nSHLVL_NESTED=%s\n" "$PATH" "$SHLVL"'
PATH="/tmp/dotfiles-shell-experiment/caller/bin:$PATH" \
  /bin/bash --login -ic 'printf "PATH_OVERRIDE=%s\n" "$PATH"'
```

Both automatic system startup and repository startup ran normally. No simulated
`path_helper`, fake Homebrew, or test-only PATH correction was used. Captured
diagnostics included guest OS/Bash versions, `/etc/profile`, `/etc/bashrc`,
`/etc/paths`, `/etc/paths.d/*`, Homebrew version/formula inventory, and each PATH.

## Observations

Positions below are one-based; personal bin means the fixture HOME's `.local/bin`.

| Scenario | SHLVL | PATH entries | Homebrew bin position | Personal bin position | Other evidence |
|----------|-------|--------------|-----------------------|-----------------------|----------------|
| Fresh login | 1 | 18 | 6 | 2 | Homebrew bin occurs twice |
| Nested login | 2 | 20 | 2 | 16 | Go bin, Homebrew bin, and Homebrew sbin each occur twice |
| Caller-prepended override, then login | 2 | 21 | 2 | 17 | Caller directory displaced to position 15 |

Thus a real guest reproduces both relevant failures: Homebrew overtakes personal
executables in a nested login, and an arbitrary explicit caller override loses
precedence. Go's unconditional prepend remains first. The approved target
ordering is not implemented by this experiment.

The guest's `/etc/profile` invokes `/usr/libexec/path_helper -s`, then sources
`/etc/bashrc`. Its paths include the Cryptex entries, `/pkg/env/global/bin`, and
`/opt/homebrew/bin`. Homebrew and rbenv initialization are real image
dependencies, so results are baseline-specific, not missing-tool coverage.

### PTY transport caveat and recovery

The first `tart exec -t` attempt failed on the host with exit 133:

```text
Fatal error: 'try!' expression unexpectedly raised an error:
failed to get terminal size: Inappropriate ioctl for device
```

This command runner does not supply a host terminal. Execution without `-t`
worked, but interactive Bash reported no job control. Wrapping Tart with macOS
`script` supplied a host PTY and allowed successful guest PTY allocation:

```bash
/usr/bin/script -q /dev/null \
  tart exec -t dotfiles-shell-probe-20261111 \
  /bin/bash /tmp/dotfiles-shell-experiment/probe.sh \
  < /dev/null > diagnostics.txt 2>&1
```

Both runs produced identical captured PATH values; the PTY run had no job-control
warnings. An eventual harness should deliberately choose a non-PTY shell case or
provide a PTY rather than assuming `tart exec -t` works in every host runner.
This exercised interactive shell startup, not GUI launchers or prompt rendering.

## Reset and final state

A marker was written inside the probe clone at
`/tmp/dotfiles-shell-experiment/reset-marker`. After stopping that clone, a new
clone was made from the unbooted baseline and booted with the same isolation
options. Guest-agent execution verified that the entire experiment directory
was absent, not merely that the fixture HOME had been cleaned:

```bash
tart stop dotfiles-shell-probe-20261111
tart clone dotfiles-shell-base-20261111 dotfiles-shell-reset-20261111
# Run the reset clone, then:
tart exec dotfiles-shell-reset-20261111 /bin/bash -c \
  'test ! -e /tmp/dotfiles-shell-experiment && echo RESET_OK'
tart stop dotfiles-shell-reset-20261111
tart delete dotfiles-shell-probe-20261111 dotfiles-shell-reset-20261111
```

`RESET_OK` was observed. Both VM runner processes exited successfully, both
disposable clones were deleted, and the final Tart listing contained no running
VMs. The stopped baseline `dotfiles-shell-base-20261111` and reusable OCI image
cache were retained to avoid another large download.

## Implications and limits

Direct Tart plus its guest agent is sufficient for this initial macOS workflow;
SSH credentials, Testcontainers, Cirrus CLI, and a GitHub App were unnecessary.
The experiment supports building pytest HOME fixtures inside real guests,
keeping assertions independent of the VM driver.

It does not yet establish Linux image/agent behavior, Bash 5 compatibility,
full dotfiles installation, install/uninstall/reset correctness, selective
deployment, actual Terminal/iTerm/VS Code/Herdr launch behavior, or the complete
approved scenario matrix. No pytest harness, Actions workflow, or production
startup fix has been implemented. A small Ubuntu experiment is the next
environment feasibility check before selecting a shared macOS/Linux driver.
