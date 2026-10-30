# Guided webcam evaluation

Launch `python live_test/guided_test.py` from the installed project environment. The explicitly launched test starts the camera; grant camera access if prompted. Follow each prompt and press Start next trial. No external slideshow keys are enabled by the test.

Protocol: ten four-second attempts each of thumbs up, palm, fist, peace, and neutral, in that block order after three-second countdowns; then empty frame (10 s), natural movement (20 s), and unsupported gesture (20 s). Classification uses the most frequent predicted label per attempt. Event success requires exactly one matching event, or zero for neutral. A modal tie in the historical script has no deterministic tie-break rule; this is a limitation of that protocol.

The archived 2026-10-30 session is immutable evidence, not a new benchmark. The full per-prediction JSON is retained in the private Drive evidence archive. It has been removed from current repository files; an earlier copy remains in Git history. No images/video were saved. The repository publishes the original CSV summary and derived JSON summary. The original guided_test.py expects the earlier local vscode_app directory layout; use the runnable launcher one directory above for a new session.

New run output goes to a fresh timestamped runs/ directory. Do not tune settings against the archived session and then call it an untouched final test. Use new sessions and independently verify slide movement for end-to-end claims. The original application/controller/model remain unchanged.
