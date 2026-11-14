# Copilot Agents attention feedback

## Check existing notification settings first

Your macOS notification settings may already work. Before changing them, follow
the [opt-in probe procedure](verification.md#operator-procedure) with a disposable
**Copilot Agents** pane. It tests waiting visibility, persistence, exact source
click routing, and completion sound separately. Reuse a passing baseline unless
behavior changes. A successful script submission alone proves none of these.

The [recorded transport gate](verification.md) passed using source-tty output.
The operator changed macOS iTerm2 presentation to persistent only after the
unchanged baseline showed temporary banners. No additional notification app
is needed.

## Requirements and activation

- macOS with iTerm2's Python API enabled; the gate used iTerm2 3.7.7 and the
  locked `iterm2` Python package 2.30.
- `uv`, Python 3.12 or newer, and Git for branch/worktree context.
- A **Copilot Agents** pane, outside tmux. Default and Naked are not eligible.
  Scope follows the profile's GUID, including session-local modifications and
  renamed profiles, not its display name.

The saved dynamic profile enables terminal-generated alerts and audible bells,
but disables bell-to-popup conversion and unrelated alert categories. It
inherits its other settings from Default without editing Default.

Its session title shows only the profile name. This matters because iTerm2
prepends the session title to native notifications: inheriting Default's title
components would expose Copilot conversation/intent text even though the hook
never includes it. Repo/worktree tab titles still use the separate `repoLabel`
expression; outside Git the tab falls back to **Copilot Agents**. Existing panes
can retain local title overrides; use a new pane when checking this policy.

To check the profile from inside a pane, rather than relying on its title:

```bash
/Applications/iTerm.app/Contents/Resources/utilities/it2 session get-var profileName \
  --session "${ITERM_SESSION_ID##*:}"
```

From the checkout you intend to use, warm the script dependencies before
starting new Copilot sessions:

```bash
uv run --locked --script bin/copilot-iterm-notify.py --help
```

Cold dependency setup may exceed Copilot's five-second hook timeout. The
detached worker does not resolve a second uv environment.
API work runs in an owned, short-lived Python helper within that worker's
delivery path. This is not a separately installed notification app or daemon.
It isolates blocking authentication and asynchronous-client cleanup so a
timeout can terminate the helper and its authentication children without
stranding the session's queue lock.

For the normal `~/dotfiles` installation:

```bash
ln -sfn "$HOME/dotfiles/etc/iterm/DynamicProfiles/copilot-agents.json" \
  "$HOME/Library/Application Support/iTerm2/DynamicProfiles/copilot-agents.json"
ln -sfn "$HOME/dotfiles/share/copilot/hooks/iterm2-session-status.json" \
  "$HOME/.copilot/hooks/iterm2-session-status.json"
```

**Worktree caution:** `~/dotfiles` currently resolves to the main checkout.
These commands do not activate unmerged worktree changes. For an explicitly
approved temporary worktree test, first record both existing symlink targets
with `readlink`. **Linking the worktree's hook JSON alone is insufficient**:
its commands deliberately use `"$HOME/dotfiles/bin/..."` for normal installation.
Generate a temporary copy with explicit worktree executable paths instead:

```bash
# Run from this worktree, only after approving temporary live activation.
worktree="$(pwd -P)"
profile_link="$HOME/Library/Application Support/iTerm2/DynamicProfiles/copilot-agents.json"
hook_link="$HOME/.copilot/hooks/iterm2-session-status.json"
# Confirm both paths are symlinks before proceeding; do not overwrite real files.
ls -ld "$profile_link" "$hook_link"
profile_before="$(readlink "$profile_link")"
hook_before="$(readlink "$hook_link")"
printf 'Rollback profile: %s\nRollback hooks: %s\n' "$profile_before" "$hook_before"
hook_config="$(mktemp "${TMPDIR:-/tmp}/copilot-iterm-hooks.XXXXXX")"
python3 - "$worktree" "$hook_config" <<'PY'
import json
import os
import shlex
import sys
from pathlib import Path

root, output = map(Path, sys.argv[1:])
config = json.loads((root / "share/copilot/hooks/iterm2-session-status.json").read_text())
for event, entries in config["hooks"].items():
    for entry, name in zip(
        entries, ("copilot-iterm-status", "copilot-iterm-notify.py"), strict=True
    ):
        executable = root / "bin" / name
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise SystemExit("Missing executable; do not activate")
        entry["bash"] = f"{shlex.quote(str(executable))} {event}"
output.write_text(json.dumps(config, indent=2) + "\n")
PY
# Inspect the generated commands before changing either live link.
cat "$hook_config"
ln -sfn "$worktree/etc/iterm/DynamicProfiles/copilot-agents.json" \
  "$HOME/Library/Application Support/iTerm2/DynamicProfiles/copilot-agents.json"
ln -sfn "$hook_config" "$HOME/.copilot/hooks/iterm2-session-status.json"
```

Keep the recorded rollback targets and temporary config path. Restore both
original targets after testing, then remove only that temporary config file;
never delete a config while its live symlink still points to it. Do not overwrite
an existing regular file with these commands: the installation above assumes
both live paths are symlinks, as recorded in [verification](verification.md).

```bash
ln -sfn "$profile_before" "$profile_link"
ln -sfn "$hook_before" "$hook_link"
readlink "$profile_link"
readlink "$hook_link"
rm -- "$hook_config"
```

Do not edit `~/.copilot/settings.json` or enable Copilot's global notification
or beep settings; those could duplicate feedback or bypass profile scoping.

iTerm2 loads the dynamic profile; open a new pane with it. Start a **new Copilot
session** to pick up hook changes. The status command and attention command
receive separate copies of the original event input.

## Behavior

Waiting permission prompts and questions produce:

```text
Copilot needs your attention: repo|worktree [branch]
```

The label belongs to the source pane, not the pane currently focused. Missing
labels fall back to Git/cwd context and finally the source UUID; detached HEAD
uses an abbreviated commit. Prompt contents, tool arguments, and question text
are not included. Clicking an alert reveals the originating window/tab/pane.

Waiting is suppressed only when iTerm2 is frontmost and that source pane is
selected in the current window and tab. A selected pane in a background window
still alerts. Unknown focus logs an error and allows delivery; unknown profile
identity logs an error and skips delivery.

Completion means the **foreground turn** finished, not that every background
agent or command finished. It rings once even when the source is focused, with
no completion system popup. Repeated waiting/completion events are suppressed
until prompt/tool activity or a new session rearms them. Sessions are independent.

## Conditional troubleshooting

If waiting alerts are missing, distinguish transport failure from profile
filters and macOS policy. Inspect the effective source profile with the probe,
then repeat a single clearly labeled waiting test while focused elsewhere.
Do not repeatedly resend after a timeout: delivery may be unknown.

Only if observations warrant it, use **macOS System Settings → Notifications →
iTerm2** to allow notifications and select **Alerts/Persistent**, rather than
Banners/Temporary. This presentation policy is application-wide, not a
per-event option. Focus modes can still suppress delivery; the integration
does not override them. Notification Center retention is not an on-screen
persistent alert.

For completion, check system volume/sound and the source pane's effective bell
settings. `Send Bell Alert=false` prevents BEL popups; `Silence Bell=false`
permits sound. Local profile modifications may override saved dynamic settings.
The gate observed a bell even with inherited `Silence Bell=1`, so verify actual
behavior rather than inferring it from a single preference.

## Diagnostics and failure guarantees

Attention state lives under
`${TMPDIR:-/tmp}/copilot-iterm-status/<source-UUID>/`, independently of the
existing status bridge. Worker diagnostics are sanitized JSON entries in
`notification-errors.log`, bounded to the newest 64 KiB. Producer failures go
to hook stderr. Neither channel contains raw hook input, notification bodies,
or commands. Hook stdout stays empty; handled integration failures return zero
and never change a permission decision.

Queues are ordered by sequence allocated under an enqueue lock. Simultaneous
Copilot events have only best-effort producer ordering. Workers use a separate
kernel-released lock; old PID metadata never authorizes stealing a live lock.
Observed state is persisted before output, so a crash can lose one alert.
Failures are not automatically retried; activity rearms future feedback.
This is best-effort delivery, not exactly-once.

Do not delete lockfiles or a session's state directory while workers may still
be running. The attention path never edits the status bridge's `latest`,
`sent`, or `lock`.

## Rollback

Restore the two saved live symlink targets, close only disposable test panes,
and start new Copilot sessions. If this checkout was already installed rather
than temporarily linked, remove only the attention registrations and
notification overrides using a reviewed revert; preserve the existing status
hook and title configuration. Do not remove all user hooks or profiles.

macOS presentation is an operator choice: rollback does not automatically undo
it. Restore it manually only if desired. See [verification](verification.md)
for what was actually tested and which operator checks remain outstanding.
