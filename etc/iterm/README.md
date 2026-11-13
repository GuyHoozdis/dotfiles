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
