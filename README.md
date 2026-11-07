# KOKO Mini POS v1.1 — 可可·南洋咖啡店

A local-network point-of-sale system for **可可·南洋咖啡店 (KE KE / KOPITIAM)**. Built for a small Malaysian restaurant using Android phones, 20 dining tables, and a 58mm kitchen receipt printer.

Staff select a table, choose food and options, then submit an order to the kitchen. Cashiers review the combined table bill, record payment, and release the table. Normal restaurant operation requires no external internet connection.

## Features

- **Tables:** T01–T20, availability labels, submitted totals, portion counts, and elapsed time.
- **Ordering:** database-driven menus, required modifiers, quantities, persistent drafts, and additional order batches.
- **Pricing:** integer sen, server-side validation, and submitted price snapshots that preserve historical bills.
- **Kitchen printing:** transactional print queue, mock PNG previews, ESC/POS network output, delivery tracking, and audited manual reprints.
- **Payments:** cash with change calculation, manually confirmed QR payments, and other full-table payments.
- **Reports:** completed transactions and daily cash/QR/other totals in `Asia/Kuala_Lumpur`.
- **Access:** named staff and admin/cashier accounts, hashed PINs, expiring sessions, and initial administrator setup.
- **Mobile interface:** Simplified Chinese labels, large touch controls, responsive layouts, and PWA assets.
- **Recovery:** persistent SQLite storage, database migrations, and SQLite-safe backup/restore scripts.

## Kopi / Teh promotion and sold-out controls

Kopi O, Kopi, Kopi C, Teh O, Teh and Teh C cost **RM1 per cup, Hot or Iced, through 1 December 2026 inclusive** (Asia/Kuala_Lumpur). White coffee and three-layer tea are excluded. A scheduled database promotion leaves regular prices intact and restores them automatically after the period; submitted prices remain historical snapshots.

Administrators can use **Settings → 售罄管理** to mark products **SOLD OUT** and restore supply. Other devices refresh availability every four seconds; the backend also rejects sold-out additions and submissions from stale screens. See [操作说明及规则](docs/stock-promotions.md).

## Version 1.1 and validation

Version 1.1 adds four touch-friendly categories and 29 products: three mains, seven snacks, 15 paid drinks, complimentary plain water, and three beers. Hot/Iced and beer packages have explicit database prices. Per-dish free customizations, dining duration, category sales analytics, and kitchen/beverage routing extend the existing workflows. See the [complete menu, migration, changed files and release notes](docs/v1.1.md).

Validated on Windows on **2026-11-07**:

| Check | Result |
| --- | --- |
| Full backend regression suite | **145 passed**, one dependency deprecation warning |
| Frontend unit tests | **17 passed** |
| Browser acceptance at 360 / 390 / 412 pixels | **9 passed** |
| SQLite, credentials and backup/recovery invariants | **8 passed** |
| TypeScript / production frontend build | Passed |
| Populated v1 migration and repeated menu seeding | Passed |
| Live database upgrade and history comparison | Passed; private backup retained |
| Mixed kitchen/beverage monochrome receipt | Rendered and visually inspected |

The local application now runs v1.1 at `http://127.0.0.1:8080`. Hardware Android/58mm printer/LAN acceptance remains on-site work. Bottled-water and canned-drink Hot/Iced variants are flagged for administrator verification in Settings. Existing dependency audit findings remain maintenance work. See [validation records](docs/validation.md) for historical and current evidence.

## Architecture

The React frontend is served by Nginx, which forwards API requests to FastAPI. SQLAlchemy persists orders and payments in SQLite. A separate worker reads committed print jobs and sends kitchen tickets. Active screens poll authoritative server state every four seconds.

| Component | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS, React Router |
| Client data and UI state | TanStack Query, Zustand |
| Backend | Python 3.12 container, FastAPI, Pydantic 2 |
| Persistence | SQLAlchemy 2, Alembic, SQLite with WAL and busy timeout |
| Printing | python-escpos, Pillow, network TCP/IP, mock adapter |
| Deployment | Docker Compose, Nginx, persistent named volume |
| Testing | pytest, Vitest, React Testing Library, Playwright |

Database constraints enforce one active session per table and one payment per session. Submission saves the order and print job atomically. Printing occurs outside the database transaction. Idempotency keys protect draft additions, submissions, payments, and manual reprint requests.

## Run on Windows

Python 3.12 and Node.js are required for initial installation. From PowerShell in the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
cd frontend
npm ci
npm test
npm run build
cd ..
.\Start-POS.cmd
```

The launcher applies migrations, seeds the menu and 20 tables, then starts the API, built frontend, and print worker in the background. Open `http://127.0.0.1:8080` on this PC. It uses the installed Microsoft YaHei font for CJK ticket rendering and listens on the LAN by default. Docker is not required.

For phone access, connect the phone to the same Wi-Fi and use the `http://PC_WIFI_IP:8080` address printed by the launcher. Run `scripts/enable-lan-access.ps1` once in an administrator PowerShell to allow inbound TCP 8080 for the installed Python runtime on Private networks from the local subnet. Keep this PC running and the app started. The Wi-Fi must permit devices to communicate; guest/client-isolated networks cannot reach the PC. The launcher prints the current address each time, since DHCP addresses can change. Set `POS_BIND_ADDRESS=127.0.0.1` in the launch environment if PC-only access is desired.

If the current Wi-Fi is classified as Public, run `scripts/enable-lan-access.ps1 -CurrentNetwork` in administrator PowerShell. This creates a Python-specific TCP 8080 rule for the current profile, Wi-Fi interface and IPv4 subnet; it leaves the network category unchanged. Re-run it after moving to a different subnet. Old IP bookmarks must be updated when the PC's Wi-Fi address changes.

To start the POS automatically when this user signs in to Windows, run `scripts/install-windows-startup.ps1` once. It installs a Startup-folder shortcut that launches the existing start script in the background without opening a browser. It reuses an already-running POS. Remove `KOKO Mini POS (Auto Start).lnk` from the user's Startup folder to disable automatic startup.

On first launch, Notepad opens `backend/data/FIRST-RUN.txt` with a generated setup token. Enter your preferred administrator name, a new 6-12 digit PIN, and this token in the app. No administrator PIN is predefined. The private token configuration, database, and ticket previews stay in the ignored `backend/data/` directory. Keep these files private and preserve them when updating the app.

Double-click `Start-POS.cmd` to reopen the app, and `Stop-POS.cmd` to stop its background processes. Windows desktop shortcuts may point to these commands. Closing the browser leaves the app running; after restarting Windows, launch it again. Startup does not require internet after installation. Logs are in `artifacts/windows/`.

To run backend checks on Windows:

```powershell
$env:PYTHONUTF8 = '1'
$env:FONT_PATH = "$env:WINDIR\Fonts\msyh.ttc"
cd backend
..\.venv\Scripts\python.exe -m pytest
```

## Quick start with Docker

Run the following from the repository root on the intended host. A development PC and the restaurant deployment server can use separate installations and data volumes.

**Requirements:** Docker Engine, Docker Compose v2, and internet access for the initial image/dependency build. Python 3 can be used to generate the setup token below. Reserve stable local IP addresses for the restaurant server and printer.

### 1. Configure the installation

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put the generated value in `SETUP_TOKEN` inside `.env`. Set the deployment host address and port as needed. Keep `.env` private; it is excluded from Git.

### 2. Build and start

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 init backend worker
```

The initialization service applies migrations and seeds the initial tables/menu. The backend health check must pass before the frontend and worker start.

Open:

- On the server: `http://localhost:8080`
- On an Android phone using the same WiFi: `http://192.168.1.100:8080`

Replace the example IP with the **deployment server's** actual reserved address. Port `8080` is configurable.

### 3. Create the first administrator

On the setup screen, enter the setup token, an administrator name, and a new **6–12 digit PIN**. There is no default production PIN. Sign in and create staff accounts in Settings.

After setup, remove the setup token value from `.env`, then run `docker compose up -d` to recreate affected services. Existing administrator accounts remain stored in SQLite.

### 4. Verify the restaurant workflow

The default printer is **mock mode**. Submit two extra-noodle Wantan Mee portions at T05, add one Mee Hoon Kueh with egg, then collect RM50 cash against the RM29 bill. Expected change is RM21. Check the separate kitchen previews, released table, and transaction history.

## Configuration

Docker Compose reads `.env` from the checkout root. Native development processes use exported environment variables; they do not automatically load `.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SETUP_TOKEN` | Empty | Required only for first-admin setup |
| `POS_BIND_ADDRESS` | `0.0.0.0` | Frontend host interface |
| `POS_PORT` | `8080` | Frontend host port |
| `CORS_ORIGINS` | See `.env.example` | Exact allowed cross-origin browser origins |
| `SESSION_HOURS` | `12` | Authentication session lifetime |

Additional backend environment variables are `DATABASE_URL`, `PRINT_OUTPUT_DIR`, and `FONT_PATH`. Compose sets the database to `/data/pos.db` and ticket output to `/data/tickets`. The image includes the Noto CJK font. Custom backend paths require corresponding Compose environment/volume changes.

Use the same Compose project and persistent volume when updating or restoring an installation. Never use `docker compose down -v` on restaurant data.

## Kitchen printing

In **Settings**, choose mock or network mode. For a physical printer, configure its private LAN IP, TCP port (default `9100`), printable dot width, text/raster mode, encoding, command profile, feed, and optional cutter.

Start with raster output for Chinese, 384 dots, and the cutter disabled. Save the configuration, queue a test print, inspect its status, and verify the actual paper. Hardware compatibility must be established on the restaurant network.

| Status | Meaning |
| --- | --- |
| `PENDING` | Order saved; job waiting for the worker |
| `SENDING` | Worker has claimed the job |
| `SENT` | Network write or mock send completed; physical printing is not confirmed |
| `FAILED` | Failure before transmission started |
| `UNKNOWN` | Delivery may have occurred; check with the kitchen |

Additional orders print only their new batch. Manual retries create history and display **REPRINT / 重印**. The worker does not automatically resend uncertain jobs. Mock mode supports success, connection failure, timeout, and uncertain delivery. See [printing details](docs/printing.md).

## Local development

Use Python **3.12** to match the container and Node **22**. Install a CJK font such as Noto Sans CJK for local ticket rendering. The optional Ubuntu helper `bash scripts/install-dev-tools.sh` installs system tools and pulls runtime images; it does not install native Python 3.12 or launch the POS.

From the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
(cd frontend && npm install)
```

In a backend terminal, activate the environment and initialize the development database:

```bash
. .venv/bin/activate
cd backend
export SETUP_TOKEN='replace-with-your-generated-local-setup-token'
python -m app.database.initialize
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, from the repository root:

```bash
. .venv/bin/activate
cd backend
python -m app.printing.worker
```

In a third terminal, from the repository root:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`; Vite proxies `/api` to the backend. With the default backend paths, development data is stored in `backend/data/`. Keep it separate from deployment data.

## Tests and builds

### Container verification

From a normal host terminal with Docker access:

```bash
sudo bash scripts/verify-in-docker.sh
```

Omit `sudo` if your account already has Docker access. The script builds isolated test targets, runs backend/frontend unit tests, and builds production images. It does not start the POS or mount restaurant data. Logs and dependency snapshots are saved under `artifacts/checks/`. It stops at the first failure.

### Native checks

Run each command from the repository root:

```bash
(cd backend && ../.venv/bin/python -m pytest)
(cd frontend && npm test && npm run build)
python3 scripts/check_invariants.py
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -p test_pricing.py -v
```

For browser acceptance, stop manually running servers on ports 8000 and 5173 first:

```bash
(cd frontend && npx playwright install chromium && npm run test:e2e)
```

Playwright starts an isolated temporary API/worker and Vite instance, tests widths of 360, 390, and 412 pixels, and retains failure traces/screenshots. It expects the root `.venv` above. CI configuration is in [.github/workflows/ci.yml](.github/workflows/ci.yml); its presence alone does not mean a run passed.

Direct dependency versions are pinned. Verified release lockfiles and dependency auditing remain part of the release checklist. Formatting configuration is provided for Ruff and Prettier.

## Backup and restore

Run from the deployment checkout root with Docker access:

```bash
scripts/backup.sh
```

This uses SQLite's online backup API, checks integrity, and copies the backup into `backups/`. Keep an additional copy on separate local storage. Ticket preview PNG/text files are stored separately; retain `/data/tickets` too if those artifacts are needed.

To restore:

```bash
scripts/restore.sh backups/pos-YYYYMMDD-HHMMSS.db
```

The script stops application services, validates the backup, preserves a unique safety copy of the current database, replaces the stopped database, and restarts services. Ensure other maintenance processes are stopped first. See [deployment and recovery](docs/deployment.md) for details.

## Repository layout

```text
backend/
  app/             API, authentication, models, pricing, orders, and printing
  alembic/         Versioned database schema
  tests/           Backend workflow, migration, and pricing tests
frontend/
  src/             Pages, shared components, API client, stores, and unit tests
  public/          PWA manifest, icon, and service worker
  e2e/             Browser acceptance tests
scripts/           Setup, verification, safe backup, and restore helpers
docs/              Architecture, API, operations, and validation records
```

## Operational scope

Currency is MYR, with money stored in integer sen and reports using `Asia/Kuala_Lumpur`. Base menu prices must be positive; modifier surcharges can be zero. Checkout defaults to QR: after checking funds, the cashier completes payment and clears the table with one button. Each successful payment queues one customer receipt to the independent cashier printer and opens its receipt page. The MVP supports one full payment per table session.

Refunds, submitted-item voids, split/partial payments, taxes, discounts, and offline order synchronization are outside this MVP. If the server becomes unavailable, submission is not assumed successful; reconnect and inspect the existing order before retrying.

The mobile browser workflow supports LAN HTTP. Android PWA installation and service workers require trusted HTTPS. Use a trusted local HTTPS setup for installable PWA operation and keep the server on the restaurant LAN without public port forwarding.

## Documentation

- [Architecture and database schema](docs/architecture.md)
- [API reference](docs/api.md) — interactive documentation at `/api/docs`
- [Printer configuration and delivery behavior](docs/printing.md)
- [Customer receipts, QR checkout and separate preparation tickets](docs/receipts.md)
- [Manual installation and data transfer to another Windows PC](docs/windows-pc-move.md)
- [Deployment and recovery](docs/deployment.md)
- [Staff and cashier guide](docs/user-guide.md)
- [Implementation plan](docs/implementation-plan.md)
- [Validation evidence and remaining acceptance checks](docs/validation.md)
