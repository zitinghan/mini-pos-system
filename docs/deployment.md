# Deployment and Recovery

## Development PC versus restaurant server

This workspace is the development PC. Do not configure its network interface, install printer drivers globally, or use its local address as the restaurant address. Transfer the repository/build images to a dedicated local restaurant server. Use Docker Compose v2 and reserve stable addresses on the restaurant router for the server and printer. Disable sleep on the deployment server and configure time synchronization before service; the application stores UTC and reports Asia/Kuala_Lumpur days.

## First deployment

For the native Windows installation, the built frontend and API share port 8080 and listen on `0.0.0.0` by default. Connect a phone to the same Wi-Fi and open the PC's current IPv4 address on port 8080, as printed by `Start-POS.cmd`. Run `scripts/enable-lan-access.ps1` in an administrator PowerShell once to add the Python-specific TCP 8080 inbound rule for Private networks and LocalSubnet clients. This does not change the network profile, disable the firewall, or configure the router. Keep the host and application running. PC-only mode remains available through the `POS_BIND_ADDRESS=127.0.0.1` launch environment setting. Phone browser access over LAN HTTP does not require an installable PWA.

For a Wi-Fi connection classified as Public, use the optional `-CurrentNetwork` switch on the firewall script. Its rule is limited to the installed Python executable, TCP 8080, the selected interface and its current IPv4 subnet. Re-run when that subnet changes. The default Private rule is retained. `scripts/install-windows-startup.ps1` installs a per-user Startup shortcut so the API and worker return automatically after Windows sign-in, using `-NoBrowser`. The PC must be powered on and signed in; this is a user startup task rather than a system service.

Copy `.env.example` to `.env`; generate a unique setup token locally and set `SETUP_TOKEN`. Configure `POS_BIND_ADDRESS`, `POS_PORT` and exact allowed `CORS_ORIGINS` if cross-origin access is needed. Same-origin Nginx access needs no CORS exception. Run:

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 init backend worker
```

The one-shot init service applies Alembic migrations and an idempotent initial menu/table seed. Backend health checks must pass before frontend and print worker start. The backend is not published on a host port. Persistent `pos_data` contains `/data/pos.db`, WAL files and `/data/tickets`. Never run `docker compose down -v` on production: it removes this volume. Normal `docker compose down` preserves it.

Open `http://SERVER_IP:8080` on Android using the same WiFi. Complete first-admin setup, create staff accounts, and remove the setup token from `.env`; run `docker compose up -d` to recreate environment settings. The application has no external fonts, analytics or normal-operation cloud API. Internet is needed for initial dependency/image builds and updates, not restaurant service. To prepare for an offline host, build on a connected compatible machine, export images with `docker save`, import with `docker load`, and use `docker compose up -d --no-build`. Preserve matching image tags and Compose project naming.

Keep the server on the restaurant LAN, with no router port forwarding. Limit host firewall access to the restaurant subnet. PINs travel over HTTP unless TLS is configured, so use trusted local HTTPS for a protected deployment. Do not expose this service directly to the internet.

## Android PWA

The manifest, icons and service worker are included. Chrome requires a secure context to install a PWA or use service workers; a plain LAN HTTP address does not qualify. For installable mode, terminate HTTPS on the local server using a certificate trusted by the Android phones (an internal CA installed by the operator is an offline option). Forward to the frontend container, keep a stable local hostname/IP matching the certificate, and use that HTTPS URL. Do not bypass certificate errors as the installation strategy.

Without HTTPS the regular mobile browser workflow works; “Add to home screen” may create a shortcut, not a service-worker PWA. No offline order synchronization exists. Losing internet alone is harmless. Losing the POS server displays a connection error; no API mutation is cached or queued. Reconnect and inspect the existing draft/batch and printer status before retrying the same operation.

## Backups

Run `scripts/backup.sh` from the repository root on the deployment host. It invokes SQLite's online backup API inside the backend container, verifies integrity and copies the result into `backups/` on the host. This captures committed WAL data safely; never blindly copy a live `.db`. Store daily copies on a separate local drive and periodically practice restore. Backups contain staff hashes and sales data; restrict access. Ticket PNG/text files are separate artifacts; copy `/data/tickets` if their previews must be retained. The database always retains ticket payloads and print outcomes.

Restore using a relative or absolute backup path:

```bash
scripts/restore.sh backups/pos-YYYYMMDD-HHMMSS.db
```

This stops frontend/backend/worker, stages the backup as the application UID, validates it, saves the current valid database as a before-restore copy, removes stopped WAL/SHM files and atomically replaces the database using a SQLite backup. It then restarts services. No automatic restore happens on startup. Stop other manual init or maintenance processes before restore; `--services-stopped` is an operator assertion, not process detection. If the existing database is corrupt and cannot be backed up, preserve its files offline and obtain maintenance help before replacement.

## Updates and power loss

Back up before every update. Preserve `.env` and the named volume. Rebuild images, run the migration/init service and restart using Compose. Never edit migration 0001 after a deployment; add a new revision. Containers restart after host recovery. A previously SENDING print becomes UNKNOWN after the stale-claim interval; check the kitchen rather than automatically sending another ticket. SQLite transactions preserve committed orders, but no software can replace disk reliability: a small UPS and an off-device backup are recommended.

Before live service run every acceptance scenario with the actual Android phones at 360/390/412px widths, test server restart and backup restore, test concurrent devices, verify the complete RM29/RM50 scenario and perform real printer compatibility tests.
