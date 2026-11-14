# Notification transport verification

## Gate: PASSED (2026-11-13)

The operator confirmed persistent waiting presentation, exact source click
routing, unchanged shell input, and bell-only completion. Selected transport:
**source tty output**. API fallback is unnecessary and was not tested.
Runtime implementation is complete; supervised runtime acceptance is in progress.

Installed iTerm2: **3.7.7** (build 3.7.7). The locked Python `iterm2` package is
**2.30**. Local inspection of that package confirmed `run_until_complete`,
`async_get_app`, `App.get_session_by_id`, `Session.async_get_profile`,
`Session.async_get_variable`, `Session.async_inject(bytes)`, and `Profile`'s
`original_guid`, `guid`, and `all_properties`. `async_inject` documents
injection as program output. These findings do not establish actual delivery.

Preparation checks: the locked script's `--help` and `uv lock --check --script`
passed; invalid UUID and incomplete invocation failed before connection. The
host-safe unittest suite uses mocks and does not connect to iTerm. All nine
cases passed with Python 3.12. Spec compliance and code quality were reviewed
directly before live inspection; no blocking probe issues were identified.

## Operator procedure

Work in this checkout, not `~/dotfiles` (which points to main). Use a
disposable **Copilot Agents** source pane. Do not install hooks or change
symlinks. Retain all current macOS permission, Focus, and presentation
settings. Obtain the UUID from the source pane, for example by reading the
UUID portion after the colon of `$ITERM_SESSION_ID`; do not use an active-pane
proxy. Record the UUID and source window/tab/pane for later comparison.

Run from another terminal or pane, replacing `SOURCE_UUID` with that exact
UUID:

```bash
uv run --locked --script tests/copilot/probe_notifications.py --session SOURCE_UUID --inspect
```

Record the returned session, window, tab, tty, profile GUIDs, and all nine
baseline values here. `null` and `baseline_unavailable` mean the API did not
provide a usable value, not that the setting is false; investigate those
values before claiming a complete baseline. The inspection reads only the
effective session profile; it does not validate tty writability.

Focus elsewhere before each submission. First try tty:

```bash
uv run --locked --script tests/copilot/probe_notifications.py --session SOURCE_UUID --transport tty --kind waiting
```

Leave the notification untouched for at least 30 seconds. Separately record
whether it visibly appeared, whether it remained on screen until clicked or
dismissed (not merely in Notification Center), and whether clicking revealed
the exact source window, tab, and pane. Thirty seconds is an observation
interval, not proof of indefinite persistence. Check that no control bytes
reached shell or Copilot input. A successful submission is not proof of any
of these observations.

Then focus elsewhere and separately check the done bell:

```bash
uv run --locked --script tests/copilot/probe_notifications.py --session SOURCE_UUID --transport tty --kind done
```

Record whether a bell sounded without a popup and whether input stayed clean.
If tty fails, distinguish a tty delivery error from iTerm profile filters and
macOS permission, Focus, or presentation behavior; a missing alert alone does
not identify the cause. Only if needed, repeat the waiting and done commands
with `--transport api`, never as an automatic fallback. A timeout, partial
write, or API error can leave delivery unknown; inspect before retrying.

Record unchanged-baseline observations, relevant permission/Focus/presentation
state, any operator-approved adjustments, and separate appearance, persistence,
routing, input, and bell outcomes below. Do not change settings without
operator agreement. If adjustments are warranted, obtain agreement first;
apply only necessary session-local profile overrides, read them back, and ask
the operator to change macOS settings only if observations warrant it. Restore
disposable overrides or close only the created session afterward. If both
transports fail, stop and request a revised design.

## Live evidence

- Read-only baseline from the current agent pane, before any changes:
  session `4C2C5FBB-CE22-4C7F-9116-D469BC5ED8B6`,
  window `pty-AF051993-E271-47F6-B812-7EA32A416EB1`, tab `23`,
  tty `/dev/ttys036`. Its original profile GUID matches Copilot Agents;
  its session-local GUID is `DEA5F930-46F3-493C-9166-48B85E1A4493`.
  This is not yet a disposable probe source selected by the operator.

  | Effective setting | Value |
  | --- | --- |
  | BM Growl | 1 |
  | Send Terminal Generated Alerts | 1 |
  | Send Bell Alert | 1 |
  | Send Idle Alert | 0 |
  | Send New Output Alert | 0 |
  | Send Session Ended Alert | 0 |
  | Suppress Alerts in Active Session | 1 |
  | Send Alerts To Companion | 0 |
  | Silence Bell | 1 |

  Current inherited settings may suppress the audible done bell and convert
  BEL into a popup; observe unchanged behavior first rather than changing them
  preemptively. Inspect the eventual disposable source separately.
- Disposable source used for the successful gate:
  `3F6B1E38-D27C-4E4D-9A75-76F993E539C3`, tab `25`,
  tty `/dev/ttys014`, same window as above. Its original effective profile
  GUID was the Copilot Agents GUID with no session-local GUID. All nine
  baseline settings matched the table above.
- Initial identifier `97ECA827-CB54-466C-A10F-2B747952C0E6` was rejected
  because it was not Copilot Agents; no alert was sent.
  An earlier disposable source `846AD4A1-67A4-4F96-A8D6-85EA6F37DEC0`
  produced a visible, self-disappearing notification before the operator
  selected the final source.
- Unchanged baseline on the final source: waiting alert visibly appeared but
  disappeared on its own. A separate click before disappearance focused the
  exact source pane; the operator confirmed unchanged shell input. Baseline
  completion produced both an audible bell and a system popup, despite the
  effective `Silence Bell=1`; observations take precedence over assumptions
  about that key.
- After observing the baseline shortfall, the operator explicitly approved
  testing session-local bell overrides and changed macOS iTerm2 presentation
  to Alerts/Persistent themselves. Notification permission permits observed
  delivery; the specific permission and Focus toggles were not inspected.
- With persistent presentation, the operator left the waiting alert untouched
  for at least 30 seconds and reported it stayed until clicked/dismissed and
  met their needs. Clicking focused the exact source pane. Shell input stayed
  unchanged. This is operator assessment, not proof of indefinite persistence.
- With only `Silence Bell=false` and `Send Bell Alert=false` applied to the
  disposable session, completion rang without a system popup and without
  changing shell input. The API read back both overrides as `0`.
- Both disposable-session settings were restored and read back as `1` after
  testing. No saved profile, Default/Naked, hook, or installation symlink was
  changed. The operator's app-wide macOS presentation choice was retained.
- API fallback, if needed: **not tested**.
- Chosen transport: **tty, operator-confirmed**.

## Runtime activation and remaining acceptance

After automated implementation, the operator returned and approved supervised
live acceptance. The following original targets were recorded before temporarily
activating this worktree:

- Dynamic profile:
  `/Users/ssulliva/dotfiles/etc/iterm/DynamicProfiles/copilot-agents.json`
- User hook:
  `/Users/ssulliva/dotfiles/share/copilot/hooks/iterm2-session-status.json`

`~/dotfiles` resolves to the main checkout, not this worktree. During testing the
profile link selected this worktree's profile and the hook link selected a
session-local generated manifest with all 14 commands targeting absolute
worktree executable paths. **Both original links have now been restored** at
the operator's request; the unlinked temporary manifest was removed. Rollback
metadata is retained outside the repository. The live test did not merge or
publish this branch.
Running test Copilot sessions may retain cached hooks until restarted.

### Supervised runtime observations

- First source: `28FDEB84-4D68-4C61-BB1B-EDB1380DB696`, tab `39`,
  tty `/dev/ttys019`. Exact original profile GUID and all nine notification/bell
  overrides read back correctly. The source was in `~/Development`, outside Git,
  with no `user.repoLabel`; fallback context `Development` was therefore expected.
- A new real Copilot session executed a delayed question through `ask_user`.
  The operator confirmed the waiting notification remained visible for at least
  30 seconds, clicked back to the exact source pane without unexpected input,
  and completion rang without a system popup. The attention spool reached
  sequence 8 with `done_seen=true` and no error log.
- Further real questions confirmed no waiting alert while the source was
  focused in frontmost iTerm2, an audible focused completion, and waiting
  delivery from a selected source pane in another iTerm2 window. New activity
  successfully rearmed feedback; the spool subsequently reached sequence 20.
- Second source: `B91EC5C6-5869-4660-87B6-297F23F72C5B`, tab `40`,
  tty `/dev/ttys022`, in this Git worktree. Its source `user.repoLabel` and
  rendered tab title both read `dotfiles|copilot-iterm-notifications`.
  Both sources use window `pty-1A16C383-B41D-4CE0-9CB5-F14EFD164973`.
- Cross-pane screenshots exposed a blocking presentation defect: iTerm2
  prepends the session name to OSC 9 messages, and the inherited title policy
  included Copilot conversation/intent text. The safe hook payload alone did
  not prevent that disclosure. The first, non-Git pane also fell back to the
  conversation title because its repo label was empty; the worktree pane's
  separate repo/tab-title expression was intact.
- Public iTerm2 `PTYSession/PTYSession.m`, `screenPostUserNotification:rich:`,
  confirms the native `Session <name> #<tab>: <message>` decoration. A scoped
  `Allow Title Setting=false` experiment did not reliably remove the intent
  from the running session's name and was not adopted. Temporary experiments
  restored their prior profile values.
- A source-local `Title Components=32` (profile name only) experiment read back
  `name=Copilot Agents` while retaining the correct repo/worktree tab title.
  That apparent fix was committed as `13a1683` for visible testing, then
  rejected by the fresh-session observation below. It is not retained.
- Overlapping completion sounds could not be counted separately. The operator
  liked the unobtrusive result, but this is not evidence of cross-source
  debouncing; the implementation still deduplicates independently per source.
- Saved Default/Naked profile fingerprints were identical before and immediately
  after initial temporary activation, and again after the title-policy correction.
  The saved Copilot Agents policy read back as `Title Components=32`.
  Both operator-provided test sources were subsequently found closed; no user
  panes were closed by the implementation or test scripts.
- Fresh regression source: `F13F4117-2F35-47A1-AA6C-580E6D64AEFA`, tab `42`,
  tty `/dev/ttys019`, window `pty-9A3E47B0-C053-4E9B-BADA-DDDB8C13D7A1`.
  The operator confirmed the correct repo/worktree tab, exact-pane click
  routing, and completion bell without popup, but still saw conversation text
  in the alert. Read-only inspection found `Title Components=2080` (profile name
  plus temporary session name), not the saved `32`; `name`, `autoName`, and
  terminal title variables were no longer the profile name. No conversation
  text was recorded in diagnostics. The ineffective override was removed.
- The operator proposed retaining the mostly working feedback and addressing
  notification text independently. Delivery success does not waive the open
  no-conversation-content requirement; use this version only where such system
  notification exposure is acceptable.

### Notification-content follow-up

Investigate the native prefix independently of the already verified queue,
source routing, focus predicate, and completion behavior. The installed release's
public source (tag `v3.7.7`) implements `OSC 1337;Notification=` with
base64-encoded `title`/`message` fields, using the same source window/tab/pane
routing without the OSC 9 session-name decoration. This is a candidate, not an
approved or live-verified replacement. A revised opt-in gate must establish
visible content, persistence, click routing, and unchanged input before adoption.

## Automated runtime evidence

- Read-only live API smoke check with the runtime's `ItermBridge` and installed
  `iterm2==2.30`: a lowercase source UUID resolved the actual uppercase iTerm2
  session, the original GUID matched Copilot Agents, `user.repoLabel` was
  nonempty, and tty was `/dev/ttys036`. Connection cleanup completed without
  diagnostics. This check emitted no OSC or BEL and does not prove runtime
  notification presentation.
- Warm activity-hook latency: 25 actual executable invocations using
  `uv run --locked --script bin/copilot-iterm-notify.py PreToolUse`, each with
  synthetic input, a random source UUID, and one isolated temporary state
  directory. Median **57.97 ms**, p95 **62.08 ms**, maximum **88.09 ms**.
  Every producer returned zero with empty stdout/stderr, before the five-second
  timeout. A foreground drain and worker-exit observation confirmed all 25
  records processed before removing the temporary directory. No notifications
  were sent; activity events do not open the terminal sink.
- Separate unit/integration cases hold a fake delivery worker blocked while
  proving producer return and closure of inherited pipes. The latency sample
  above is the real executable, not an extrapolation from those fakes.
- After merging `origin/main` at `366c763` without rewriting history, the
  host-safe suite again reported **133 tests passed** with
  `uv run --no-project --python 3.12 python -m unittest discover -s tests/copilot -p 'test_*.py' -q`.
  Cases include source context, reducer/rearming, concurrent queue/crash replay,
  status-worker independence, exact profile/focus rules, output bytes, real
  helper-process cleanup, malformed protocol, and actual hook command quoting.
  The new suite imports no live iTerm2 API at discovery.
- Installed Ruff lint and formatting checks passed for the new entrypoint,
  notification package, and `tests/copilot` (120-character formatting).
  Bash syntax for the unchanged status bridge, both uv script locks, and the
  runtime's locked `--help` entrypoint were checked. Existing shell-suite
  manifests, Tart inputs, status bridge, and Default/Naked exports were not
  changed.
- Final review caught a worktree installation pitfall: merely linking the hook
  manifest still runs `~/dotfiles/bin/...` from main. The runbook now generates
  a temporary manifest with explicitly quoted worktree executable paths. All
  14 generated commands were dry-run from a temporary HOME containing spaces,
  with iTerm context absent; they returned zero with empty stdout/stderr.
  During that pre-activation dry run, no live symlink was changed and its
  temporary config was removed. The supervised activation above is separate.

## Runtime acceptance matrix

| Requirement | Automated evidence | Live runtime observation |
| --- | --- | --- |
| Permission prompt/question waiting types | Parser, reducer, actual hook matcher/command cases | Real question passed; permission prompt not separately exercised |
| Persistent waiting and exact-pane click | Source-only adapter and output-byte cases | Real runtime passed; conversation-title prefix remains a separate defect |
| Focused source suppression | Frontmost app/window/tab/pane fake API cases | Operator confirmed |
| Selected source in background window | Fake API predicate cases | Operator confirmed |
| iTerm2 behind another app | Fake API inactive-app case | Operator confirmed |
| Worktree/branch/detached context | Temporary Git repository/worktree cases | Worktree tab verified; alert presentation defective; detached context not separately exercised |
| Done bell, no popup | Exact BEL bytes and effective profile filter cases | Operator confirmed; overlapping sources not counted separately |
| Duplicates and activity rearming | Reducer and queued-event interleavings | Real activity rearmed; duplicate injection not separately exercised |
| Two independent source panes | Separate queues and exact UUID/tty selection | Both sources processed events; separate click routing not yet confirmed |
| Default/Naked unaffected | Nonmatching GUID cases and unchanged exports | Saved fingerprints unchanged at activation; no separate live session exercise |
| Integration failure isolation | Subprocess exit/stdout/log/lock/helper-death cases | Automated requirement passed |

**Handoff:** working feedback retained on the worktree branch; original live
installation links restored. Real Copilot hook discovery, routing, focus rules,
persistence, and bell-only completion are verified. Notification text remains
an explicit follow-up, and unexercised matrix cases are not claimed as passing.
