# Notification transport verification

## Gate: PENDING

Probe prepared and the current source session inspected read-only. No live
session was created or sent an alert. No notification, bell, presentation, or
click-routing result has been observed. No transport is selected. Tasks 2–6
remain blocked pending operator confirmation.

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
- macOS permission, Focus, and presentation: **not observed; unchanged**.
- tty waiting, visibility, persistence, click routing, input: **pending**.
- tty done bell and absence of popup: **pending**.
- API fallback, if needed: **not tested**.
- Approved adjustments: **none**.
- Chosen transport: **pending operator confirmation**.
