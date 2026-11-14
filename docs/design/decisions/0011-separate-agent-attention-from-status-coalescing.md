# 0011: Separate agent attention events from status coalescing

Date: 2026-11-13

Status: accepted; independent queue implemented and automatically verified.

## Context

The existing Copilot hook stores the newest state for a background worker to
forward to iTerm2. That coalescing is useful for tab status, where intermediate
states may be skipped. It is not sufficient for attention signals: a waiting
event followed quickly by activity could disappear before the worker sees it.
Conversely, repeating every state report as an alert would create noise.

## Decision

- Keep the existing coalesced tab-status path and process attention events
  independently of its latest-state slot.
- Serialize attention decisions per source-session UUID and keep notification
  state separate from status-forwarding state.
- Deduplicate waiting and done reports until intervening activity rearms them.
  Session lifecycle boundaries reset or clear attention state.
- Separate source/context resolution, event-state decisions, and terminal-output
  delivery so behavior can be tested without generating real notifications.
- Keep attention delivery best-effort and nonblocking. Failures must not
  prevent status forwarding, change permission decisions, or write decision
  JSON to hook stdout. Record bounded local diagnostics without hook contents.
- Treat concurrent lifecycle ordering as best-effort unless the producer
  supplies reliable sequence identifiers.

## Alternatives

- Deliver from the status worker's latest-state slot: simpler, but loses
  short-lived waiting events.
- Notify on every hook: avoids coalescing loss, but creates duplicate alerts
  and couples feedback latency to terminal API calls.
- Introduce a persistent event service or claim total lifecycle ordering:
  broader than this local integration and unsupported by current event data.

## Consequences

- Attention processing needs its own synchronization and crash recovery.
- Notification failures and state updates can be tested independently from
  iTerm2; live transport checks remain required by
  [decision 0010](0010-iterm-owned-agent-notifications.md).
- Avoiding coalescing loss does not promise exactly-once delivery across crashes
  or correct producer ordering for simultaneous events.
- Terminal API work uses an owned, short-lived Python helper, not a notification
  application or daemon. Review reproduced blocking authentication children and
  executor shutdown beyond async deadlines; process isolation allows bounded
  cleanup without stranding the queue lock.

## Source and approval

The user approved the [notification specification](../../plans/2026-11-13-copilot-iterm-notifications/spec.md)
on 2026-11-13: "I approve the notification spec." This record does not supersede
any existing decision.
