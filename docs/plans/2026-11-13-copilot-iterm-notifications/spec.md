# Copilot Agents notifications

## Goal and scope

Extend the existing Copilot Agents iTerm2 integration with stronger attention
alerts and quieter completion feedback. Keep Default and Naked unchanged.
Do not install a notification helper application or change macOS settings
automatically.

## Approved behavior

- Waiting: post an iTerm2-owned macOS notification for permission prompts and
  questions. Clicking it reveals the originating window, tab, and pane.
- Suppress waiting notifications when the originating pane has keyboard focus
  in the active application. A selected pane in a background window still
  qualifies for notification.
- Identify the source with the originating session's `repoLabel` and current
  branch. Derive missing context from the hook's working directory; use the
  directory name outside Git and identify detached HEAD by abbreviated commit.
  If the working directory is unavailable, use `repoLabel` or the originating
  session's identifier. Do not include prompts, tool arguments, or question contents.
- Done means the foreground agent has finished a turn, not that background
  agents or commands necessarily finished. Ring the originating terminal's bell
  once; do not post a completion notification. Allow the bell for focused panes.
- Preserve existing tab titles and status indicators. New behavior applies only
  to sessions using the Copilot Agents profile; other profiles remain unaffected.
- Session start, session end, and unrelated background notifications do not
  produce attention alerts.

## Components and event flow

### Transport verification gate

Before feature implementation, verify source-targeted output using the source
session's tty device (resolved through iTerm2, not inherited hook stdout).
If unavailable, evaluate iTerm2's Python API output injection. Either candidate
must process OSC 9 and BEL as terminal output, never application input, and a
test notification must reveal the correct session when clicked. If neither
passes, stop and request a revised design rather than silently dropping click
routing or installing another notification application.

The existing Copilot hook configuration remains the lifecycle entry point.
`bin/copilot-iterm-status` continues forwarding coalesced state updates through
`it2`; attention delivery must not depend solely on that latest-state slot,
because a waiting event may otherwise be overwritten before delivery.

Add a small notification component to process attention events, obtain source
context, and deliver terminal notification/bell output to the explicitly
identified source session. Never send these control bytes as keyboard input
using `it2 session send` or `run`. iTerm2 documents OSC 9 as its native notification
control sequence. The implementation must verify a supported session-targeted
output transport and click routing before treating that transport as usable.

Retain only the waiting notification types `permission_prompt` and
`elicitation_dialog`. Serialize notification decisions per session, suppress
duplicate reports of the same state, and rearm after intervening activity or a
new session lifecycle. Notification state must not be shared between panes.
Status forwarding may continue to re-send repeated states as it does today.

Notification processing has three independently testable seams: source/context
resolution, serialized event-state decisions, and terminal-output delivery.
Identify the source by the UUID portion of `ITERM_SESSION_ID`, and scope the
feature by the profile GUID `870214EA-844A-4654-A241-B7EB0B766076`, not its
editable display name.

Store notification state beneath the existing per-session temporary directory,
separately from status forwarding. Serialize state changes with a PID-liveness
lock; do not reclaim a lock solely because it is old. `SessionStart` resets
notification state. `UserPromptSubmit`, `PreToolUse`, and `PostToolUse` rearm
waiting and done notifications; repeated waiting or done events without
intervening activity are suppressed. `SessionEnd` clears notification state.
Use hook execution order as best-effort ordering; do not claim perfect ordering
for simultaneous lifecycle events without event sequence identifiers.

Profile overrides enable native notifications and audible bells for Copilot
Agents, disable bell-to-system-notification conversion, and suppress unrelated
alert categories without silencing the audible bell. Default to an explicit
check that iTerm2 is frontmost and the source pane is selected in its key window.
If focus lookup fails, notify rather than losing a waiting alert. Native
suppression may replace the explicit check only after verifying the same
frontmost-app/key-window/selected-pane behavior.

## macOS controls and limitations

Notification persistence is application-wide macOS policy, not a per-event
script option. The user must permit iTerm2 notifications and choose persistent
Alerts rather than transient Banners in System Settings. Done uses a bell so
it does not conflict with that persistent setting.

Focus modes, notification permissions, and system sound settings can suppress
delivery. Do not promise to override them or dismiss an unresolved notification
automatically. Multiple agents in one pane and remote/tmux forwarding are out
of scope; retain the current tmux guard.

## Failures and lifecycle

Notification failures must not block Copilot or change permission decisions.
Keep hook stdout free of notification text or hook decision JSON. Report
actionable integration failures to a local diagnostic channel, without saving
hook payloads, and keep status forwarding functional when notification
delivery fails. Missing iTerm2 context or an unsupported profile is an intentional
no-op. Synchronization must recover from crashed workers without reclaiming a
live worker's lock.

Write integration diagnostics to stderr and preserve asynchronous-worker stderr
in a per-session `notification-errors.log` in the temporary state directory.
Keep only the most recent 64 KiB, serialized by the notification lock. Do not
log notification bodies, hook input, or command arguments.

## Verification

Use focused automated cases for source identity, branch/detached-HEAD and
non-Git labels, profile scoping, duplicate suppression and rearming,
independent sessions, waiting events followed quickly by activity, completion
bell without completion notification, and delivery failures. Stub the terminal
transport for these tests; do not rely on arbitrary sleep intervals.

Verify live that a background pane's waiting alert appears, clicking it reveals
that exact session, a focused pane produces no alert, a selected pane in a
background window still alerts, and done rings for focused and background panes
without a system notification. The user must confirm persistent presentation after
selecting Alerts in macOS; automated submission alone does not establish that
the alert was visible or persistent.

## References

- [iTerm2 notification control sequence](https://iterm2.com/documentation-escape-codes.html)
- [Profile notification filters and bell settings](https://iterm2.com/documentation-preferences-profiles-terminal.html)
- [Session Status and one-shot status-change alerts](https://iterm2.com/documentation-session-status.html)
