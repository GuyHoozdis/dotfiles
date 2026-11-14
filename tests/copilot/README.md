# Copilot notification probe

- [Transport gate and operator procedure](../../docs/plans/2026-11-13-copilot-iterm-notifications/verification.md)
- [Setup, behavior, diagnostics, and rollback](../../docs/plans/2026-11-13-copilot-iterm-notifications/usage.md)
- `probe_notifications.py`: explicit opt-in inspection and transport probe;
  never run by test discovery.
- `test_probe_notifications.py`: host-safe, mocked unit tests.

Run the unit tests without connecting to iTerm:

```bash
uv run --no-project --python 3.12 python -m unittest discover \
  -s tests/copilot -p 'test_*.py' -v
```

Discovery runs host-safe tests only. The probe requires an explicit source
UUID and action; it is never invoked by discovery.
