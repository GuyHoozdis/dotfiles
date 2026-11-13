# Copilot notification probe

- [Transport gate and operator procedure](../../docs/plans/2026-11-13-copilot-iterm-notifications/verification.md)
- `probe_notifications.py`: explicit opt-in inspection and transport probe;
  never run by test discovery.
- `test_probe_notifications.py`: host-safe, mocked unit tests.

Run the unit tests without connecting to iTerm:

```bash
python3 -m unittest discover -s tests/copilot -p 'test_*.py'
```
