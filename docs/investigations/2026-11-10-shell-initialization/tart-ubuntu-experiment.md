# Local Tart Ubuntu experiment

Date: 2026-11-11

Outcome: direct Tart guest-agent execution also works for Ubuntu. Real Bash
startup reproduced duplicate Go entries and displacement of a caller-prepended
override, without Homebrew or macOS `path_helper`. Diagnostic retrieval, PTY
execution, stop, and fresh-clone reset all succeeded.

## Baseline and isolation

| Component | Observed value |
|-----------|----------------|
| Host/Tart | Same Apple Silicon host as the [macOS experiment](tart-experiment.md), Tart 2.41.1 |
| Image requested | `ghcr.io/cirruslabs/ubuntu:latest` |
| Resolved image | `ghcr.io/cirruslabs/ubuntu@sha256:97166c84ea5f102be33d2959f70e83861a36bd749f1715ab669d93e6c9f31476` |
| Guest | Ubuntu 24.04.5 LTS, aarch64, kernel `7.0.0-42-generic` |
| Bash | `/bin/bash`, 5.2.21(1)-release |
| Resources | 4 CPUs, 4096 MiB RAM, 20 GB virtual disk |
| Transfer/storage | 3.1 GB compressed download; Tart reported approximately 5 GB image size |
| Agent identity | Non-root `admin`, uid 1000 |
| Optional dependencies | Python 3 present; brew, pyenv, rbenv, n, and uv absent from agent PATH |

No Homebrew executable was found at `/usr/local/bin/brew`,
`/opt/homebrew/bin/brew`, or `/home/linuxbrew/.linuxbrew/bin/brew`. No packages
were installed. This is one provisioned Ubuntu image, not all Linux
distributions or an x86-64 compatibility result.

The unbooted baseline was named `dotfiles-shell-ubuntu-base-20261111`. Disposable
probe/reset clones used headless execution with audio, USB accessories, and
clipboard disabled, default networking, and no host directory mounts or
credential forwarding. Automatic pruning was disabled with
`TART_NO_AUTO_PRUNE=1`. The macOS baseline was not modified.

## Procedure

The lifecycle followed the macOS experiment with the Ubuntu image and names:

```bash
export TART_NO_AUTO_PRUNE=1
tart clone ghcr.io/cirruslabs/ubuntu:latest dotfiles-shell-ubuntu-base-20261111
tart clone dotfiles-shell-ubuntu-base-20261111 dotfiles-shell-ubuntu-probe-20261111
tart run --no-graphics --no-audio --no-usb-accessories --no-clipboard \
  dotfiles-shell-ubuntu-probe-20261111
```

Running state was checked with `tart list`; `tart exec ... /bin/uname -a`
confirmed guest-agent readiness. Only the tracked loader and exports module
from commit `a617a2f` were transferred through agent stdin.

Two independent temporary homes under `/tmp/dotfiles-shell-experiment` were
used: a system-only control without user startup files, and a repository home
with the loader at `.bash_login` and exports at
`.local/etc/bashrc.d/exports.bash`. Both had empty `.local/bin`, `.bun/bin`, and
`node_modules/.bin` directories. No local modules or `.bashrc` were deployed.

Each outer `/bin/bash --login -ic` received an `env -i` environment specifying
HOME, USER, LOGNAME, SHELL, TERM, TERM_PROGRAM, and this initial PATH:

```text
/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
```

Each outer shell captured its PATH, then independently launched a nested login,
a login with `/tmp/dotfiles-shell-experiment/caller/bin` prepended, and a plain
interactive non-login Bash. These were real startup invocations, not explicit
sourcing of simulated profiles. The host `script` PTY wrapper from the macOS
experiment allowed `tart exec -t` to run successfully.

Captured diagnostics included OS/kernel/Bash versions, `/etc/profile`,
`/etc/bash.bashrc`, `/etc/profile.d/*.sh`, dependency discovery, PATH, SHLVL,
and availability of the repository's `exists_in_path` function.

## Results

| Scenario | System-only control | Repository loader + exports |
|----------|---------------------|-----------------------------|
| Fresh login, SHLVL 1 | Original order retained; `/snap/bin` appended | Go, personal, Bun, Node directories precede system paths |
| Nested login, SHLVL 2 | PATH identical to outer shell | Go bin prepended again: two occurrences |
| Caller override + login, SHLVL 2 | Caller directory remains first | Go bin inserted before caller directory; caller becomes second |
| Plain interactive Bash, SHLVL 2 | Inherits PATH; no repository function | Inherits PATH, but `exists_in_path` is absent |

Ubuntu's system startup did not perform the macOS-style PATH reconstruction in
these cases. Its profile includes `/etc/bash.bashrc` and `/etc/profile.d/*.sh`;
the snap profile appends `/snap/bin` without duplicating it on the nested login.
The repository's unconditional Go prepend is independently sufficient to
violate both repeatability and caller-override precedence on Linux.

The non-login case demonstrates that inherited PATH is not equivalent to
per-shell function initialization. It does not establish custom prompt behavior:
the prompt module was deliberately not deployed in this bounded experiment.

Two diagnostic details matter for the future harness:

- The repository printed `Homebrew initialized` despite no Homebrew executable
  at either path checked by its initializer. The current function returns
  success when neither conditional branch runs; the message is not evidence
  that Homebrew was present.
- Ubuntu's system bashrc printed its sudo guidance in the temporary homes.
  System startup output must be distinguished from repository output, rather
  than blindly treating all interactive output as a test failure.

The initial macOS tar stream also produced GNU tar warnings about
`LIBARCHIVE.xattr.com.apple.provenance`. Extraction succeeded; future source
transfer should omit irrelevant macOS extended metadata.

## Reset, cleanup, and conclusion

A marker was written to the probe clone's experiment directory. The probe was
stopped, then a new clone of the unbooted baseline was booted. Agent execution
verified that `/tmp/dotfiles-shell-experiment` was absent and printed `RESET_OK`.
The reset clone was stopped; both disposable clones were deleted. Both runner
processes exited successfully, and the final Tart listing showed no running VMs.
The stopped Ubuntu baseline and OCI cache were retained.

Direct Tart plus its guest agent now has observed macOS and Ubuntu feasibility;
Cirrus CLI, SSH, and Testcontainers remain unnecessary for this scope. The next
design step is to revise the pytest/uv harness proposal around guest-native
tests and a thin host-side Tart lifecycle driver. Production startup changes,
full scenario coverage, provisioning, and GitHub Actions remain outside this
experiment.
