# 0010: iTerm2-owned agent notifications and completion bells

Date: 2026-11-13

Status: accepted; runtime feedback observed; notification-content acceptance open.

## Context

The Copilot Agents profile identifies repositories and worktrees in tab titles
and displays lifecycle status. Waiting agents need a stronger signal that
identifies their source and reveals the originating window, tab, and pane when
clicked. Completion should be quieter and should not produce a persistent alert.

macOS controls notification presentation per application, so a script cannot
reliably choose persistent waiting alerts and transient completion banners
under the same application identity.

## Decision

- Use iTerm2-owned system notifications for permission prompts and questions,
  with repo/worktree and branch context but no prompt or tool contents.
- Use a terminal bell for foreground-turn completion, not a system notification.
- Suppress waiting alerts only when the originating pane has keyboard focus in
  the active application. Completion bells may sound for focused panes.
- Scope new behavior to the Copilot Agents profile GUID; leave Default and
  Naked unchanged.
- Ask the operator to allow iTerm2 notifications and select persistent Alerts
  in macOS settings. Do not change system preferences automatically.
- Verify terminal-output delivery to an explicitly identified source session
  and click-to-reveal before implementation. Try the source tty, then iTerm2
  Python API output injection. Never inject notification bytes as application
  input. If neither transport satisfies routing, stop for a revised design.

## Alternatives

- A separate notification application adds dependencies and custom click
  routing.
- Completion notifications share iTerm2's application-wide persistence policy
  and would therefore be persistent along with waiting alerts.
- iTerm2's one-shot status-change watcher requires rearming and does not
  provide the approved distinction between waiting and completion.

## Consequences

- Clicking an alert must retain native source-session routing.
- macOS Focus, notification permissions, and sound settings remain authoritative.
- Persistence and click behavior require operator-visible verification; a
  successful notification submission alone is insufficient.
- No remote/tmux forwarding or multiple agents in one pane is introduced.
- The source-tty gate passed with operator-confirmed persistent presentation,
  exact-pane click routing, and bell-only completion; see
  [verification evidence](../../plans/2026-11-13-copilot-iterm-notifications/verification.md).
  Runtime acceptance is tracked separately.
- Live runtime testing confirmed persistence, click routing, focused-source
  suppression, and background-window delivery, but exposed the native
  conversation-title prefix. A profile-only session-title override passed an
  isolated API check but failed in a fresh Copilot session and was removed.
  The operator proposed keeping the working functionality and addressing
  notification text separately. The no-prompt-content requirement remains
  unmet; this limitation must be explicit, not treated as cosmetic.

## Source and approval

The user approved the [notification specification](../../plans/2026-11-13-copilot-iterm-notifications/spec.md)
on 2026-11-13: "I approve the notification spec." This record does not supersede
any existing decision.
