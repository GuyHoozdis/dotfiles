# Copilot notification tests and probe

- [Transport gate and operator procedure](../../docs/plans/2026-11-13-copilot-iterm-notifications/verification.md)
- [Setup, behavior, diagnostics, and rollback](../../docs/plans/2026-11-13-copilot-iterm-notifications/usage.md)
- `probe_notifications.py`: explicit opt-in inspection and transport probe;
  never run by test discovery.
- `test_probe_notifications.py`: host-safe, mocked unit tests.
- `test_context.py`: hook parsing and source Git context.
- `test_state.py`: feedback reducer, per-session spool, locking, and
  crash-replay cases with an injected fake sink.
- `test_hooks.py`: entrypoint, detached-worker, and status-helper coexistence
  subprocess cases; no iTerm2 connection.

Runtime modules live in `share/copilot/iterm_notifications/`: `context`
(input/labels), `state` (pure transitions), `safefs`/`spool` (owner-only queue
files and locks), `worker` (serialized drain with injected delivery), and `cli`
(hook producer and worker entry for `bin/copilot-iterm-notify.py`).

Run the unit tests without connecting to iTerm:

```bash
uv run --no-project --python 3.12 python -m unittest discover \
  -s tests/copilot -p 'test_*.py' -v
```

Discovery runs host-safe tests only. The probe requires an explicit source
UUID and action; it is never invoked by discovery.
