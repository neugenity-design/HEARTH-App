# Replit preparation

Hearth can be imported from its private GitHub repository into a Replit App. The repository contains application code and tests only. The owner's database, uploaded receipts, backups, and Google credentials are deliberately excluded.

## Import and run the development workspace

1. In Replit, choose **Create → Import from GitHub** and select the private Hearth repository.
2. In **Secrets**, set `HEARTH_PASSWORD` to a unique password of at least 12 characters. The username defaults to `owner` unless you set `HEARTH_USERNAME`.
3. Select **Run** to start the **Run Hearth** workflow on `0.0.0.0:5000`.
4. Open the preview in a new browser tab and sign in. Hearth blocks embedded frames, so use the standalone tab rather than the in-editor frame.

The imported development workspace starts with an empty `data/` folder. Import records through Hearth after deciding where hosted production data will live.

## Before publishing

Do not publish the current SQLite/upload-folder storage as an autoscaled production app. Move relational records to Replit Database and uploaded receipts/documents to Replit App Storage first. These services provide production persistence; the repository and deployment build filesystem are not the property-data backup.

For a personal deployment, choose **Only you** or another private deployment option when the Replit plan supports it. Keep Hearth's password protection enabled as a second control. Replit's private published-app options are plan dependent.

Google Workspace email needs a hosted OAuth client and `HEARTH_BASE_URL` set to the final HTTPS origin. The callback will be:

`https://your-hearth-name.replit.app/oauth/google/callback`

## Local behavior remains unchanged

`python server.py` and the Windows launchers still bind only to `127.0.0.1:8768` and do not require a password. A nonlocal bind fails closed unless `HEARTH_PASSWORD` contains at least 12 characters.
