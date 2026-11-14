# Copilot Agents Notifications Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development
> (if subagents available) or superpowers:executing-plans to implement this plan.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add clickable, persistent waiting alerts for background Copilot Agents
panes and bell-only feedback when the foreground agent finishes a turn.

**Architecture:** Keep the existing status hook unchanged and register a second,
independent attention hook. That hook queues sanitized lifecycle events for a
short-lived per-session worker; separate context, state, and terminal-output
components resolve identity, deduplicate feedback, and target the correct pane.
An owned, ephemeral Python API helper bounds library authentication and cleanup
without holding the worker lock indefinitely. Verify native notification
routing before building the feature.

**Tech Stack:** Bash hook configuration; Python 3.12+, uv script metadata/locks,
stdlib unittest, the iTerm2 Python API, Git, and native iTerm2 OSC 9/BEL output.
No notification helper application or persistent daemon.

**Status:** Tasks 1–5 implemented and verified. Task 6 documentation and automated
checks are complete; live activation and the visible runtime acceptance matrix
are blocked on operator availability. The operator confirmed the transport gate
and approved remaining implementation in autopilot, without further feedback.
No live links were changed. The spec was approved on 2026-11-13.

---

## Context and execution boundaries

- Read [the approved spec](spec.md),
  [ADR 0010](../../design/decisions/0010-iterm-owned-agent-notifications.md),
  and [ADR 0011](../../design/decisions/0011-separate-agent-attention-from-status-coalescing.md).
- Work only in `.worktrees/copilot-iterm-notifications`, on
  `copilot-iterm-notifications`. Do not change `main` or publish a PR as part of
  this plan. Recheck target-branch ADR numbering before a later PR and merge.
- The production `~/dotfiles` symlink points at the main checkout, not this
  worktree. Editing this branch will not automatically activate its hooks.
  Keep installation and live-test activation explicit.
- Existing macOS notification settings may already satisfy the requirements.
  Test them unchanged before recommending permission or presentation changes.
  A successful baseline needs no macOS reconfiguration.
- `bin/copilot-iterm-status` currently discards stdin, coalesces states into
  `latest`, and runs an asynchronous `it2` worker. Do not send notifications
  from that worker or refactor its locking as part of this feature.
- `share/copilot/hooks/iterm2-session-status.json` already registers
  `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`,
  `Notification`, `Stop`, and `SessionEnd`.
- The existing pytest/Tart shell suites are unrelated. Use unittest for this
  new host-safe suite, without modifying their runner or installing pytest.
- Existing Python project configuration is for shell fixtures. Do not change
  its manifests or lockfile. New runtime scripts use uv inline metadata.
- Follow `bin/python-script-template.py` for executable shebang, `main`, and
  structured error reporting, not its unrelated example dependencies.

## File responsibilities

| Path | Change and responsibility |
| --- | --- |
| `tests/copilot/probe_notifications.py` | Executable, explicit opt-in native transport/click-routing probe; never runs under test discovery |
| `tests/copilot/probe_notifications.py.lock` | uv script dependency lock for the probe |
| `share/copilot/iterm_notifications/__init__.py` | Package marker; no import-time effects |
| `share/copilot/iterm_notifications/context.py` | Safe hook-event parsing and repo/worktree/branch message context |
| `share/copilot/iterm_notifications/state.py` | Pure feedback reducer, state encoding, and replay watermark |
| `share/copilot/iterm_notifications/safefs.py` | Owner-only, no-follow descriptors and atomic publication |
| `share/copilot/iterm_notifications/spool.py` | Ordered queue, permanent locks, persisted state, and bounded log |
| `share/copilot/iterm_notifications/worker.py` | Serialized drain and lazy delivery seam |
| `share/copilot/iterm_notifications/diagnostics.py` | Payload-free diagnostic codes and JSON lines |
| `share/copilot/iterm_notifications/terminal.py` | Source profile/focus lookup and verified terminal-output transport |
| `share/copilot/iterm_notifications/terminal_api.py` | Bounded iTerm2 connection, source identity, and focus lookup |
| `share/copilot/iterm_notifications/api_types.py` | Typed public API interfaces without eager GUI dependencies |
| `share/copilot/iterm_notifications/api_guard.py` | Per-call library output isolation and wall-clock guard |
| `share/copilot/iterm_notifications/tty.py` | Source-owned tty descriptor checks and bounded output |
| `share/copilot/iterm_notifications/isolation.py` | Owned helper lifetime, deadline, and process-group cleanup |
| `share/copilot/iterm_notifications/ipc.py` | Versioned, bounded, nonblocking helper protocol |
| `share/copilot/iterm_notifications/helper.py` | One API connection and parent-lifeline watchdog per helper |
| `share/copilot/iterm_notifications/cli.py` | Enqueue/worker orchestration and bounded integration errors |
| `bin/copilot-iterm-notify.py` | Thin executable uv entrypoint importing the package relative to its resolved path |
| `bin/copilot-iterm-notify.py.lock` | uv script dependency lock for runtime |
| `tests/copilot/test_context.py` | Synthetic hook and temporary Git repository cases |
| `tests/copilot/test_state.py` | State transitions, ordered queue, locking/crash and bounded diagnostics cases |
| `tests/copilot/test_terminal.py` | Fake API/session, output-byte and focus cases |
| `tests/copilot/test_isolation.py` | Real owned-subprocess timeout, protocol, and orphan-cleanup cases |
| `tests/copilot/test_hooks.py` | Fake-worker subprocess/hook integration and failure isolation |
| `tests/copilot/test_registration.py` | Actual hook commands, quoting, and effective profile alert policy |
| `tests/copilot/README.md` | Navigation and focused test/probe commands |
| `share/copilot/hooks/iterm2-session-status.json` | Add attention hook entries without changing existing status commands |
| `etc/iterm/DynamicProfiles/copilot-agents.json` | Notification/bell overrides for this profile alone |
| `etc/iterm/README.md` | Link installation, macOS settings, and operation to the runbook |
| `docs/plans/2026-11-13-copilot-iterm-notifications/usage.md` | Setup/rollback and diagnostic guidance |
| `docs/plans/2026-11-13-copilot-iterm-notifications/verification.md` | Transport gate and final automated/operator evidence, honestly labeled |

Keep the modules focused and ordinarily below 250 lines each. Split only if
necessary to preserve the boundaries above; do not introduce a plugin framework.
Tests add `share/copilot` to their import path using their resolved repository
root. Runtime entrypoints do the same, independent of the hook's cwd.

Implementation review established that `asyncio.wait_for` alone cannot bound
synchronous AppleScript authentication or `asyncio.Runner.close()` waiting for a
resolver thread. The terminal boundary therefore uses an owned, ephemeral
Python subprocess with bounded IPC and process-group cleanup. This strengthens
the existing timeout/failure contract; it does not add a notification helper
application, persistent service, or new output transport.

## Chunk 1: Verify, implement, and activate attention delivery

### Task 1: Prove source-targeted output and click routing

**Files:** Create `tests/copilot/probe_notifications.py`, its script lock,
`tests/copilot/README.md`, and the plan-local `verification.md`.

- [x] **Step 1: Inspect the installed API and create the opt-in probe.**
  Use the uv shebang `#!/usr/bin/env -S uv run --script`, Python `>=3.12`,
  and inline `dependencies = ["iterm2"]`; make the probe executable.
  Implement `--session UUID --transport tty|api --kind waiting|done`.
  Require an explicit UUID; never default to the active pane. No hooks are
  installed and no persistent preferences are changed by this probe.
- [x] **Step 2: Resolve the exact source and profile through the Python API.**
  Connect using `iterm2.run_until_complete`, obtain the app with
  `async_get_app`, and find the session by UUID. Fetch
  `await session.async_get_profile()` and use
  `profile.original_guid or profile.guid`. Require
  `870214EA-844A-4654-A241-B7EB0B766076`, including session-local modifications
  that retain this original GUID. A display-name match is insufficient.
  Check the installed library exposes these methods; do not assume remote
  master source exactly matches the installed version.
- [x] **Step 3: Test the source tty transport first.**
  Resolve `await session.async_get_variable("tty")` and verify it is an
  existing character-device tty belonging to this user under `/dev/`.
  Write only `b"\x1b]9;Copilot test: waiting for input\x07"` or `b"\x07"`
  to that device as output. Never use `it2 session send`, `run`,
  `async_send_text`, keyboard scripting, inherited stdout, or an active-session
  proxy. Confirm no bytes land in shell/Copilot input.
- [x] **Step 4: If tty output fails, test Python output injection.**
  Use `await session.async_inject(data)` with the same bytes. This API takes
  bytes and simulates program output. Record one chosen transport; do not
  silently switch to another transport on each delivery or send twice.
  Not needed: tty passed the live gate.
- [x] **Step 5: Record the unchanged notification baseline.**
  On a disposable Copilot Agents session, read and record the effective
  profile key/value settings listed in Task 5 Step 3 without applying
  overrides yet. Leave macOS notification permission, presentation style,
  and Focus settings unchanged. The system may already be configured as
  desired; do not make selecting Alerts a prerequisite for the first test.
- [x] **Step 6: Trigger one baseline notification and ask the operator to assess it.**
  From this worktree, use the probe against the explicit source UUID:

  ```bash
  uv lock --script tests/copilot/probe_notifications.py
  uv run --locked --script tests/copilot/probe_notifications.py \
    --session SOURCE_UUID --transport tty --kind waiting
  ```

  Replace `SOURCE_UUID` with the disposable session's actual UUID. If needed,
  repeat with `--transport api`. Move focus to another pane/window/app before
  submission. Label the notification clearly as a test. Ask the operator to
  leave it untouched for at least 30 seconds, then confirm separately:

  - Did a visible system notification appear?
  - Did it remain displayed until deliberately clicked or dismissed, rather
    than disappearing as a banner? Does that meet the desired persistence?
  - After clicking it, was the exact source window/tab/pane revealed?

  Thirty seconds is an observation interval, not proof of indefinite
  persistence; record the operator's assessment rather than inferring it
  from API success or an entry retained only in Notification Center.
  Also run the done probe and ask whether it produced a bell without a popup.
  If all desired behavior already exists, record the baseline as passing and
  retain the current macOS settings.

  If behavior differs, distinguish terminal delivery, iTerm profile filters,
  and macOS permission/Focus/presentation issues before proposing changes.
  A missing alert is not proof of a transport failure or of incorrect macOS
  settings. With operator agreement, apply only necessary session-local
  profile overrides from Task 5 Step 3 and read them back. Ask the operator
  to adjust macOS settings only if the observations warrant it, then repeat
  the affected checks. Never change macOS settings automatically or alter
  Default/Naked. Restore disposable session overrides or close only the
  created session after testing.
- [x] **Step 7: Record the gate outcome and commit.**
  Record iTerm2/API versions, selected transport, unchanged-baseline results,
  any operator-approved adjustments, permission state, and operator-confirmed
  routing/presentation in `verification.md`. Until confirmed, mark
  the gate pending and **stop before Task 2**. If both transports fail,
  stop and request a revised design. Do not claim that successful submission
  proves visible delivery, persistence, or click routing.
  Commit only the probe, its lock, navigation, and evidence:
  `test(iterm): add opt-in notification transport probe`.

### Task 2: Define safe events, source labels, and feedback transitions

**Files:** Create the package marker, `context.py`, reducer portion of `state.py`,
`tests/copilot/test_context.py`, and `tests/copilot/test_state.py`.

- [x] **Step 1: Write failing context tests.**
  Accept only the known event names and waiting notification types. Parse the
  hook JSON object, retaining only event, `cwd`, and `notification_type` plus
  the validated UUID from the environment; never retain other payload fields.
  Limit input to 10 MiB plus one overflow byte and reject malformed, oversized,
  and non-object input with a bounded diagnostic. Invalid events must not
  create notifications; never dump the rejected input.
- [x] **Step 2: Cover source context with temporary Git fixtures.**
  Test a regular repo, linked worktree outside and inside `.worktrees/`,
  branch names containing `/`, detached HEAD, unborn branch, non-Git cwd,
  missing/unreadable cwd, spaces and non-ASCII names. Prefer the source
  session's nonempty `repoLabel`; otherwise derive the repo and linked
  worktree from Git common-dir/toplevel, not a guessed `.worktrees` segment.
  Use `git -C cwd symbolic-ref --quiet --short HEAD`, then
  `git -C cwd rev-parse --short HEAD` for detached HEAD. Treat expected
  non-Git results as context absence; surface unexpected execution failures.
- [x] **Step 3: Specify payload formatting and test control-character removal.**
  Waiting notification body format is:

  ```text
  Copilot needs your attention: repo|worktree [branch]
  ```

  Omit absent pieces; use cwd basename, then source UUID if all labels are
  unavailable. Never substitute the focused pane's label or branch.
  Remove C0/C1 controls, ESC, BEL, CR, and LF from all interpolated text
  before encoding OSC 9; cap context to 240 printable characters. Preserve
  ordinary Unicode. Test that user-supplied names cannot terminate the OSC
  or add another terminal control sequence. Keep the constant message prefix
  first so a repository name beginning `4;` cannot select OSC 9's progress
  subcommand.
- [x] **Step 4: Write failing table-driven reducer tests.**
  Define `FeedbackState(waiting_seen=False, done_seen=False)` and the pure
  `reduce_event(state, event) -> (new_state, action)` contract:

  | Event | New state | Action |
  | --- | --- | --- |
  | `SessionStart` | both false | none |
  | `UserPromptSubmit`, `PreToolUse`, `PostToolUse` | both false | none |
  | first eligible `Notification` | waiting true, retain done | waiting |
  | repeated eligible `Notification` | unchanged | none |
  | first `Stop` | done true, retain waiting | done |
  | repeated `Stop` | unchanged | none |
  | `SessionEnd` | both false; discard persisted lifecycle state | none |
  | unrelated notification | unchanged | none |

  Test interleavings, including `waiting, done, waiting` without activity
  (one waiting alert), and `waiting, activity, waiting` (two).
- [x] **Step 5: Run tests red, implement the pure behavior, then run green.**

  ```bash
  uv run --no-project --python 3.12 python -m unittest discover \
    -s tests/copilot -p 'test_*.py' -v
  ```

  Before implementation, expect import/missing-function failures. Afterward,
  expect all context and reducer cases to pass without contacting iTerm2.
  Keep API imports lazy or in the terminal adapter so pure tests need no
  installed `iterm2` package.
- [x] **Step 6: Commit.**
  `feat(copilot): model attention events and source context`.

### Task 3: Add a lossless-within-process queue and crash-safe worker boundary

**Files:** Extend `state.py`; create `cli.py`, `bin/copilot-iterm-notify.py`,
and its script lock; extend `test_state.py`; create `test_hooks.py`.

- [x] **Step 1: Write failing queue and worker tests before implementation.**
  With an isolated `TemporaryDirectory`, enqueue waiting then working before
  draining; assert the waiting action remains in the drained history. Test
  two UUIDs, repeated events, concurrent producers, interrupted writes,
  a producer arriving during worker shutdown, and stale worker metadata.
  Use pipes/events/barriers and `subprocess.wait(timeout=...)`, not arbitrary
  sleeps to infer completion.
- [x] **Step 2: Implement the sanitized spool and owner-liveness locking.**
  Reuse `${TMPDIR:-/tmp}/copilot-iterm-status/<UUID>/`, but use separate
  `notification-queue/`, `notification-state.json`, `notification.lock`,
  and `notification-errors.log`. Validate the UUID before path construction.
  Create directories/files owner-only and reject symlinked state paths.
  Never touch the status worker's `latest`, `sent`, or `lock`.
  The inspected status script only recursively removes its own `lock`;
  it does not remove the parent directory on `SessionEnd`. Recheck that
  invariant at implementation time. Add a fake-it2 integration case that
  runs status `SessionEnd` while the attention worker holds its lock, and
  verify the queue and notification-lock inode remain intact.
  Under a short `fcntl.flock` enqueue lock, allocate a monotonic per-session
  sequence and atomically rename each sanitized event record into the queue.
  Allocate sequence and publish together; timestamps alone do not order events.
- [x] **Step 3: Implement ephemeral worker startup and serialized draining.**
  The hook entrypoint reads/validates input, publishes the record, starts
  a worker via `subprocess.Popen` with `start_new_session=True`,
  `close_fds=True`, and disconnected stdin/stdout, and returns. Route
  child stderr to `/dev/null`; its explicit diagnostic handler writes errors
  to stderr and mirrors the same sanitized entries through the bounded log
  writer. Do not retain inherited hook pipes or append unbounded logs.
  Detached child startup must not wait
  for API connection or notification delivery.
  Use the script's resolved absolute location and `sys.executable`, not a
  command-string shell or another uv environment resolution for the child.
  Each child takes the notification worker lock in blocking mode and drains
  records in sequence order before exiting. Waiting contenders acquire and
  recheck even if the prior worker found an empty queue, avoiding lost wakeups.
  Record the owning PID as diagnostic metadata. The kernel releases `flock`
  on process death; this is the PID-liveness mechanism, with no age-based
  lock eviction or racing directory deletion.
- [x] **Step 4: Bound failure handling and feedback state writes.**
  For each event, persist the reducer's observed state atomically, then
  attempt its one action and remove that queue record. There is no automatic
  delivery retry after a notification error; activity rearms future events.
  If a worker crashes after delivery but before record removal, replay must
  not repeatedly notify: observed state is already recorded. A crash before
  delivery can lose that one alert; document best-effort, not exactly-once.
  A focused-pane suppression also counts as observing the waiting state.
  `SessionEnd` clears lifecycle state, not the queue containing newer events.
  Do not delete an in-use worker lockfile.
- [x] **Step 5: Add bounded, payload-free structured diagnostics.**
  Catch specific JSON, filesystem, subprocess timeout, and API errors at
  their boundaries. Record an event code and exception class, not raw
  exceptions/commands/payloads. Keep only the newest 64 KiB of the per-session
  error log under the notification lock. Queue-publication failures go to
  hook stderr without suppressing the independent status hook. Stdout stays
  empty, including all library/worker normal output.
  In **hook mode**, every handled integration/input failure returns exit
  code 0 with empty stdout, after reporting the sanitized diagnostic:
  malformed JSON/UUID, oversized input, filesystem/queue publication,
  worker launch, and terminal/API failures must not change tool permissions.
  Assert this contract in subprocess tests for each failure. Normal
  `--help` returns 0; explicit CLI argument misuse and the opt-in diagnostic
  probe may use nonzero exit codes. Do not add a blanket exception catch
  that disguises programming bugs.
- [x] **Step 6: Provide the executable uv entrypoint and script lock.**

  ```python
  #!/usr/bin/env -S uv run --script
  # /// script
  # requires-python = ">=3.12"
  # dependencies = ["iterm2"]
  # ///
  from pathlib import Path
  import sys

  sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "share" / "copilot"))
  from iterm_notifications.cli import main

  if __name__ == "__main__":
      raise SystemExit(main())
  ```

  `main()` supports `EVENT` for hook input, private `--worker UUID`, and
  `--help` with no terminal side effects. Make the script executable, then
  run `uv lock --script bin/copilot-iterm-notify.py`. Missing iTerm context,
  tmux, and unsupported profiles are intentional no-ops; configuration/API
  failures are diagnostic errors, not successful delivery.
- [x] **Step 7: Run the focused unittest command from Task 2.**
  Expect all pure/queue/subprocess cases to pass using injected fake actions.
  Add a worker death/restart case and prove a live lock is never stolen,
  regardless of metadata age.
- [x] **Step 8: Commit.**
  `feat(copilot): queue per-session attention events independently`.

### Task 4: Implement terminal identity, focus, and the verified output adapter

**Files:** Create `terminal.py`, `test_terminal.py`; connect the adapter in
`cli.py`; extend `test_hooks.py`.

- [x] **Step 1: Write failing adapter tests with fake API objects.**
  Cover exact UUID lookup (never active-pane fallback), original/current
  profile GUID, renamed profile, nonmatching profiles, closed sessions,
  source label lookup, selected tab/pane in another window, iTerm2 not
  frontmost, unknown focus, focus API errors, unavailable tty, and a
  terminal-write/API failure. Fake sessions record output bytes and must
  reject any call to a keyboard-input API.
- [x] **Step 2: Implement source resolution through the Python API.**
  Lazily import `iterm2` in the worker, establish one connection for its
  drain, and find each source by UUID. Match `original_guid or guid`,
  obtain `user.repoLabel`, and resolve its tty for the chosen transport.
  Missing/closed sessions and other profiles do not alert; failure to
  determine profile identity must log and skip, never assume eligibility.
- [x] **Step 3: Implement the exact focused-source predicate.**
  Refresh app/focus state immediately before waiting delivery; suppress
  only if all three checks positively succeed:

  ```python
  focused = (
      app.app_active is True
      and source_window_is_current
      and source_tab_and_pane_are_selected
  )
  ```

  Resolve source window/tab using `get_tab_and_window_for_session`, and
  compare window, tab, and active-session identifiers. A selected pane in
  another window or a background iTerm2 application must alert.
  Unknown/failed focus lookup logs a bounded diagnostic and allows delivery.
  Do not reuse the suppression predicate for done bells.
- [x] **Step 4: Implement exactly the transport that passed Task 1.**
  Use `OSC 9` with sanitized UTF-8 body for waiting; use only `b"\x07"` for
  done. For tty, open only the verified source character device, without
  creating it, using a nonblocking descriptor and bounded failure handling.
  Revalidate source/session association before output and never cache a tty
  across worker runs. For API injection, use `async_inject(bytes)` only.
  Bound each external Git/API/output operation (15 seconds maximum);
  close connections/descriptors in `finally`/context managers.
- [x] **Step 5: Run the full new unittest suite.**
  Assert focus suppression, fail-open focus behavior, fail-closed profile
  behavior, precise OSC/BEL bytes, no key injection, and independent sessions.
  Tests must run without a live GUI, network, or notification permissions.
- [x] **Step 6: Commit.**
  `feat(iterm): deliver attention feedback to the source pane`.

### Task 5: Register attention hooks and configure Copilot Agents alone

**Files:** Modify the existing hooks JSON and dynamic profile; extend
`test_hooks.py` and `test_terminal.py`.

- [x] **Step 1: Write failing hook-registration/profile behavior cases.**
  Load the real hook JSON in the test. Run its new attention commands
  against a fake executable under a temporary HOME, including HOME with
  spaces; verify event names and stdin are delivered intact. Ensure every
  old status command remains present. Simulate attention launch/worker
  failures and assert status forwarding still receives the event.
  Assert hook exit code 0 and empty stdout for every handled attention failure,
  including malformed input, unwritable state storage, failed child startup,
  and terminal API failure.
  Assert the output-filter combination permits OSC alerts but not BEL
  popups, not merely that the profile contains arbitrary constants.
- [x] **Step 2: Append one attention entry to each existing event array.**
  Use the same `type`, `bash`, and `timeoutSec` conventions as status:

  ```json
  {
    "type": "command",
    "bash": "\"$HOME/dotfiles/bin/copilot-iterm-notify.py\" Notification",
    "matcher": "permission_prompt|elicitation_dialog",
    "timeoutSec": 5
  }
  ```

  Register the other six event names with their exact argument and no
  notification matcher. Both entries in the `Notification` array (existing
  status and new attention) retain `permission_prompt|elicitation_dialog`;
  no other array gets that matcher. Each command gets its own original stdin from
  Copilot; do not pipe status output into the attention hook.
- [x] **Step 3: Add only these Copilot Agents profile overrides.**
  Recheck keys against the installed iTerm2 version. Keep its GUID, parent,
  tags, tab-title expression, and unrelated settings intact.

  ```json
  {
    "BM Growl": true,
    "Send Terminal Generated Alerts": true,
    "Send Bell Alert": false,
    "Send Idle Alert": false,
    "Send New Output Alert": false,
    "Send Session Ended Alert": false,
    "Suppress Alerts in Active Session": false,
    "Send Alerts To Companion": false,
    "Silence Bell": false
  }
  ```

  Explicit suppression lives in the adapter, so native active-session
  suppression must not hide an alert for a background window.
- [x] **Step 4: Run focused checks and commit.**

  ```bash
  uv run --no-project --python 3.12 python -m unittest discover \
    -s tests/copilot -p 'test_*.py' -v
  bash -n bin/copilot-iterm-status
  git diff --check
  ```

  Expected: unittest passes, Bash syntax unchanged, whitespace check clean,
  and no modifications to Default/Naked exports.
  Confirm `pyproject.toml` still sets pytest `testpaths = ["tests/shell"]`
  and the Tart driver transfers only its explicit shell-suite inputs; do
  not broaden existing discovery or add Python API imports at test-module
  import time. A deliberate broad unittest run remains host-safe.
  Commit `feat(iterm): enable Copilot attention alerts and completion bells`.

### Task 6: Document activation/rollback and obtain end-to-end evidence

**Files:** Create plan-local `usage.md`; update `verification.md`,
`tests/copilot/README.md`, `etc/iterm/README.md`, and `docs/plans/README.md`.

- [x] **Step 1: Write the setup/rollback runbook.**
  Explain macOS notification permission, persistent Alerts, Focus limitations,
  audible-bell settings, foreground-turn semantics, focus suppression,
  best-effort ordering/crash semantics, and bounded local log location.
  Lead with the unchanged-settings probe: macOS may already be configured
  correctly. Treat permission/style changes as conditional troubleshooting,
  not mandatory setup, and reuse a passing baseline unless behavior changes.
  Keep READMEs navigational. Explain `uv` dependency warm-up:
  `bin/copilot-iterm-notify.py --help` before starting new Copilot sessions.
  Do not enable Copilot's global beep/notifications settings; they would
  bypass profile scoping or duplicate feedback.
- [x] **Step 2: Activate only in an explicitly approved live test.**
  **Completed:** supervised testing used temporary links and generated absolute
  hook executable paths. Both original links were restored at the operator's
  request and the unlinked temporary manifest removed. Default/Naked
  fingerprints remained unchanged.
  Record the current iTerm DynamicProfiles and user hook symlink targets
  before changing them. Temporarily point them at this worktree's updated
  files only with operator agreement, then warm runtime dependencies.
  Do not edit the separately versioned `~/.copilot/settings.json` or
  commit live-home files. Hook changes require a new Copilot session.
  Record rollback targets and restore them after the test unless the
  operator explicitly chooses to keep the worktree active.
- [ ] **Step 3: Execute the visible acceptance matrix.**
  **Partially verified:** real Copilot question/completion discovery, persistent alerts,
  exact-pane click routing, and both focus rules passed. Cross-pane testing
  exposed conversation text in iTerm2's native session-title prefix. A
  profile-only title correction failed in a fresh session and was removed.
  The operator proposed retaining the working functionality and treating
  notification text separately. Full content acceptance and unexercised matrix
  cases remain open; see `verification.md`.

  | Case | Expected |
  | --- | --- |
  | Background agent permission prompt | One identifiable waiting alert |
  | Background agent question | One identifiable waiting alert |
  | Click waiting alert | Reveal exact source window, tab, and pane |
  | Source pane focused in frontmost iTerm2 | No waiting alert |
  | Source pane selected in a background window | Waiting alert appears |
  | iTerm2 behind another application | Waiting alert appears |
  | Source pane in a worktree/detached HEAD | Correct worktree/branch-or-commit |
  | Done, source focused or background | Bell, no system notification |
  | Repeated waiting/done without activity | No duplicate feedback |
  | Activity then waiting/done again | Feedback rearms |
  | Two separate source panes | Independent routing and deduplication |
  | Default/Naked sessions | No new feedback; existing behavior unchanged |
  | Injected adapter failure in unit/integration harness | Status unaffected; bounded diagnostic |

  Exercise at least one real Copilot permission prompt or question and
  subsequent foreground completion; direct helper calls alone do not prove
  hook discovery or event format. Do not provoke destructive tool requests
  to manufacture a prompt. Let the operator supply safe interaction.
  After dependency warm-up, measure at least 20 safe, synthetic activity-hook
  invocations against an isolated state directory and record median/p95/max
  return latency. They must return before the five-second hook timeout and
  must not wait for terminal delivery; use the unit harness to hold the
  fake API worker blocked and prove the producer still exits. Report actual
  latency rather than claiming the previous status hook's timing.
- [x] **Step 4: Record evidence without overstating it.**
  Record test command/result, selected transport, actual hook discovery,
  operator-observed click routing, audible completion, and persistence.
  Persistence must remain pending until the operator confirms the alert
  stays until clicked/dismissed, whether the existing configuration already
  provides this or the operator chose to adjust macOS settings. Any failed
  source routing or visible behavior blocks completion; do not replace
  this with a submitted-notification proxy assertion.
- [x] **Step 5: Run final focused checks and commit documentation.**
  Repeat the Task 5 commands after the final changes. If this repository
  has acquired an applicable linter/formatter since planning, run it;
  otherwise do not introduce unrelated tooling or claim a lint run.
  Run `uv run --locked --script bin/copilot-iterm-notify.py --help` as a
  side-effect-free dependency/entrypoint check.
  Commit `docs(iterm): document attention notification operation`.

## Completion and handoff

All task checkboxes, including the operator checks, must be satisfied or
explicitly reported blocked before claiming completion. No automatic merge,
push, PR, worktree removal, or main-checkout activation is authorized here.
Use atomic Conventional Commits with scope and append:

```text
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

Keep the two ADR statuses at accepted/pending until implementation and its
corresponding evidence exist. Update them only for this feature's verified
state, without changing historical identifiers or unrelated ADRs.
