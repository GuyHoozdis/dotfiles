# Open questions

No answers below should be inferred as implementation approval.

## Blocking the first startup design

| ID | Question | Why it matters |
|----|----------|----------------|
| S1 | Resolved: default categories and the within-group order for persistent commands, version-managed runtimes, and other user-installed tools are approved. | See [decision 0004](../../design/decisions/0004-default-path-ordering.md); implementation and duplicate policy remain separate |
| S2 | Which startup integration should make user functions available in interactive non-login Bash without needlessly reinitializing inherited PATH? | The expected behavior is resolved: functions such as `codetree` and `jqless` must be available. Both pinned guests currently omit them from plain `bash`; the acceptance test now checks these user-facing functions rather than the internal `exists_in_path` helper. Resolved by [decision 0007](../../design/decisions/0007-split-bashrc-from-bash-profile.md): `.bashrc` loads per-shell modules and `.bash_profile` sources it; both guests now pass. |
| S3 | Must Apple Bash 3.2 work, or is a newer Bash an explicit prerequisite? Which Linux environments are initially supported? | Controls syntax, completion integration, and the test matrix |
| S4 | Which local modules affect PATH or prompt hooks, and are they safe to inspect with the user? | The tracked files are not the complete live configuration |
| S5 | Should non-interactive login Bash receive the environment without interactive UI, and what should remote command startup load? | Avoids breaking scripts, SSH commands, and tooling Not yet measured: the harness uses `tart exec`, not `sshd`. Deferred; revisit with real `ssh host`, `ssh host 'cmd'`, and `ssh -t host 'cmd'` against Tart clones. sshd takes HOME from the account database, so options are a dedicated test user with `/bin/bash` as its shell, or installing into the clone's admin HOME and changing its shell. |
| S6 | Partially resolved: same-HOME snapshot-backed prefix recovery repairs the four known PATH failures. What handles ambiguous overrides and launchers that discard state? | [Decision 0009](../../design/decisions/0009-snapshot-backed-path-reconstruction.md) implements the approved bounded mechanism; [decision 0003](../../design/decisions/0003-preserve-caller-path-overrides.md) remains broader. Managed/system directory reuse, reordered/replaced PATHs, and changed system providers do not have universal provenance recovery. |

The former pinned macOS fresh-login duplicate of `/opt/homebrew/bin` is repaired,
along with managed ordering, nested Go duplication, and supported caller
precedence. Both pinned guests pass all runnable tests in the
[verified results](../../../tests/shell/README.md#baselines-and-current-results).
Missing or unusable snapshot metadata initializes defaults without claiming
caller recovery; non-login inheritance is unchanged. S05/S06/S07, actual
IDE/SSH launches, PTY behavior, and live-HOME migration remain outside this
partial resolution. Integration was approved after operator review on 2026-11-12
and completed in `investigate-shell-initialization`.

## Deployment and layout

| ID | Question | Why it matters |
|----|----------|----------------|
| D1 | What is the smallest default selection, and what belongs only in opt-in workstation/tool selections? | Avoids turning configuration install into full machine provisioning |
| D2 | Are named profiles useful, individual components sufficient, or should profiles compose components? | Determines selection/dependency design |
| D3 | What should happen when a target is a real file, an unrelated symlink, or a file edited after install? | Defines safe conflict, uninstall, and restoration behavior |
| D4 | Does "factory reset" mean managed config only, or also packages, application data, and OS preferences? | These have different ownership and reversibility guarantees |
| D5 | Should container/image deployments copy config, symlink to a retained checkout, or support both? | Determines update behavior and image size/lifetime expectations |
| D6 | Does a link manager provide enough benefit to justify its dependency? | Stow remains an option, not a requirement or rejection |
| D7 | Which applications actually support XDG destinations, environment overrides, or only legacy paths? | Prevents a layout migration that applications do not read |
| D8 | Should local overrides run after shared config, and how should untracked overrides survive reinstall/reset? | Existing order is local-before-shared; changing it affects behavior |
| D9 | Should automation run locally on each target, centrally over SSH, or support both? | Distinguishes a small local installer from Ansible/Fabric orchestration |
| D10 | Is package/OS provisioning part of the same selected workflow, and what bootstrap dependencies are acceptable for minimal targets? | Determines whether Ansible/Chef adds enough value over a link-focused tool |

## Agent and IDE provisioning

| ID | Question | Why it matters |
|----|----------|----------------|
| A1 | Which settings and external skill sources should be included first? | Avoids inspecting or committing complete live directories |
| A2 | Pin sources to commits/releases, and how should updates and upstream review work? | Defines reproducibility and supply-chain review |
| A3 | Is an offline reinstall required? | Affects caching and artifact retention |
| A4 | Which harnesses can share skill installations, and which require adapters? | Avoids assuming identical path and configuration conventions |

## Remaining Herdr evidence

Record executable resolution and actual version inside Herdr, along with shell
mode, PATH, relevant alias, and `COPILOT_HOME`. The exact in-Herdr chain has not
been verified. Uninstalling the Homebrew binary can remove ambiguity but does not
by itself repair shell initialization.
