# iTerm2

- `profiles.json`, `older-profiles.json` — exported profiles (reference only).
- `DynamicProfiles/copilot-agents.json` — **Copilot Agents** profile for running
  several Copilot CLI agents, one per tab. Inherits everything from `Default`.

## Copilot Agents

- **Tab title** is `repo`, or `repo|worktree` inside a linked worktree. It comes
  from the `repoLabel` user variable that `_iterm2_set_repo_label` in
  `../bashrc.d/prompt.bash` sets at each prompt. The title follows the focused
  pane.
- **Tab status** (dot + subtitle: working, waiting, done, idle) comes from the
  Copilot hooks in `../../share/copilot/hooks/iterm2-session-status.json`,
  which call `../../bin/copilot-iterm-status`. That forwards to iTerm2's
  `it2 handle-agent-hook` (iTerm2 3.7+). "waiting" means a permission prompt
  or question needs you.

Install:

```bash
ln -sfn ~/dotfiles/etc/iterm/DynamicProfiles/copilot-agents.json \
  ~/Library/Application\ Support/iTerm2/DynamicProfiles/
ln -sfn ~/dotfiles/share/copilot/hooks/iterm2-session-status.json ~/.copilot/hooks/
```

Then open tabs with the **Copilot Agents** profile. New Copilot sessions pick up
the hooks.

## Nerdr

This was my first attempt at reworkig my iTerm2 profiles so that they would be better 
multi-Agent management.  I just can't get into `herdr`.

This was the last output of that session.
```
The plan already uses a new Dynamic Profile that inherits Default's settings without modifying Default or Naked. Waiting on the critique before implementing.
Clearing works. Creating the profile, hook script, and hook config.
I'll switch dedupe to a per-event token so iTerm's own heuristic status changes can't make a repeated state get skipped. Also creating the missing dirs.
Now the prompt hook that publishes the repo label.
Testing the label function in the main checkout, a worktree, and a non-git dir.
Label logic is correct. Now testing the hook script end-to-end against this session, including a concurrent burst that must settle on the last event.
All states map correctly, the burst settles on the last event, hooks return in ~20–70ms, and the lock is released. Installing symlinks and verifying iTerm2 loads the profile.
Profile loaded. Now verifying Copilot itself picks up the hooks with a tiny non-interactive run, then checking the recorded state.
I added a new **Copilot Agents** iTerm2 profile. It inherits its settings from Default; neither Default nor Naked was changed. It gives each tab a repo title and an agent status, committed in 3 commits on `main` (not pushed).

**Tab title:** shows `repo`, or `repo|worktree` when the shell is in a worktree. Your bash prompt sets it, and Copilot's own title changes now only affect the window title.

**Tab status:** iTerm2 3.7 added its own agent-status feature, but it only knows Claude Code and Codex. I connected Copilot's hooks to it, so the tab shows:
- **working** while it runs
- **waiting** when a permission prompt or question needs you
- **done** when the turn finishes
- **idle** after the session starts

When Copilot exits, the status clears. Each hook returns in about 20–70ms.

**What I tested:** the title and status work in iTerm2, and I ran the status script directly through every state. I couldn't confirm that Copilot fires the hooks itself: a non-interactive test run failed with "No supported model available". To check, start a new Copilot session in a tab using the profile.

**Limitations:**
- The title follows the focused pane, so the left Copilot pane at the repo root shows just `repo`.
- Status is skipped inside tmux.
- If several tools run in parallel, the status could briefly be wrong.

The links into iTerm2's profiles folder and `~/.copilot/hooks` are in place. I didn't commit anything to your `~/.copilot` git repo. Setup notes are in `etc/iterm/README.md`.
```

I'm not sure that the hooks are actually doing anything.  The `repoLabel`, which is set by `_iterm2_set_repo_label` in `../bashrc.d/prompt.bash`, seems to be doing most/all of the work that was missing
from iTerm2's own features.  It still needs a little tweaking, but it is a good start.
