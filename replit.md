# Hearth on Replit

Select **Run** to start the **Run Hearth** workflow (`python3 server.py --host 0.0.0.0 --port 5000`). Hearth uses Python 3.11+ and has no runtime packages to install.

Open the Replit development preview **in a new browser tab**: Hearth blocks embedding in the editor frame. Sign in at the browser prompt with username `owner` (or your custom `HEARTH_USERNAME`) and the password stored in `HEARTH_PASSWORD`. The server requires at least 12 characters in that password.

Private records and uploads are excluded from Git. The development workspace uses `data/` for SQLite and uploads; this is not a production deployment or backup. See [Replit preparation](docs/REPLIT.md) before publishing.

Run `python3 -m unittest discover -s tests -v` and `node tests/test_ui_helpers.mjs` to check the app.
