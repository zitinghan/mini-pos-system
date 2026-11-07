# Set up Mini POS manually on another Windows PC

This guide covers the existing system: 20 tables, separate kitchen/drinks tickets, customer receipts, QR-first checkout, stock availability and scheduled prices. The new PC becomes the POS host; phones connect to its Wi-Fi/LAN IP on port 8080.

## 1. Prepare the new PC

Install **64-bit Python 3.12** and **Node.js 22.22 or newer supported Node 22/24**, and the manufacturer's Windows driver for your cashier printer. This checkout was tested with Python 3.12.10 and Node 22.22.2 / 24.21.0. Select the Python installer's PATH option. Download runtimes from their official sites: [Python 3.12.10](https://www.python.org/downloads/release/python-31210/) and [Node.js](https://nodejs.org/en/download).

Connect the POS-80C by USB and confirm Windows lists the queue as `POS-80C` (or note its actual name). Use a printer/driver supporting ESC/POS RAW output for automatic thermal receipts. A normal Windows test page verifies the driver/connection; the POS receipt itself also needs a paper test.

Windows must have a CJK font for Chinese printing. Check:

```powershell
Test-Path "$env:WINDIR\Fonts\msyh.ttc"
```

The result should be `True`. If missing, install the Windows Simplified Chinese font support before starting this application. The launcher uses Microsoft YaHei for ticket rendering.

Copy/download the application source into a folder such as `C:\POS\mini-pos-system`. Use the latest `main` from GitHub, or copy the current project source. Do not copy the old PC's `.venv`, `node_modules`, process-ID file or Startup shortcuts; these depend on the original machine and installation path.

## 2. Install application dependencies

Open PowerShell in the new source folder:

```powershell
Set-Location C:\POS\mini-pos-system
python --version
node --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Set-Location frontend
npm.cmd ci
npm.cmd run build
Set-Location ..
```

Confirm `python --version` is Python 3.12. If another version is the default but the Python launcher is installed, replace the environment-creation command with `py -3.12 -m venv .venv`.

Internet is needed for this initial dependency installation. Normal POS operation uses the local host and local printer connections.

## 3. Move existing sales, accounts and settings

Skip this step only for a completely new, empty installation. When moving the existing restaurant, transfer the database before launching on the new PC. Existing PINs, history, menus, stock flags, promotions, printer settings and receipt snapshots live in the database.

On the **old PC**, finish or verify pending printing, stop accepting new orders and run from the project root:

```powershell
.\Stop-POS.cmd
.\.venv\Scripts\python.exe scripts\backup.py backup backend\data\pos.db backups\move-to-new-pc.db
```

Copy to a private USB drive or other private transfer folder:

- `backups\move-to-new-pc.db`
- `backend\data\tickets\` (kitchen/drinks and receipt preview files, if present)
- `backend\data\windows-config.json` (private setup configuration)

Do not copy a live `pos.db` file by itself: SQLite may still have committed changes in its WAL. The backup command captures a consistent database. Do not run both old and new database copies for live orders after the move. Remove the old PC's `KOKO Mini POS (Auto Start).lnk` from its user Startup folder if that PC will remain in use.

On the **new PC**, keep the app stopped. Assuming the transfer files are in `D:\POS-transfer`:

```powershell
Set-Location C:\POS\mini-pos-system
New-Item -ItemType Directory -Path backend\data -Force
.\.venv\Scripts\python.exe scripts\backup.py restore D:\POS-transfer\move-to-new-pc.db backend\data\pos.db --services-stopped
Copy-Item D:\POS-transfer\windows-config.json backend\data\windows-config.json
Copy-Item D:\POS-transfer\tickets backend\data\tickets -Recurse
```

Only run the two `Copy-Item` commands for files/folders you actually transferred. `restore` validates the backup and preserves a safety copy if a database already exists on the new PC. Keep the original backup until the new host has been checked.

## 4. Start and verify the new host

```powershell
.\Start-POS.cmd
```

The launcher applies migrations and adds missing tables/menu entries without resetting existing records. Open `http://127.0.0.1:8080` on the PC.

For a restored database, log in with the existing administrator name and PIN. Do not create a new administrator or replace the database. For a new installation, Notepad opens `backend\data\FIRST-RUN.txt`; use its setup token to create the first administrator.

Check all 20 tables, a historical paid transaction/receipt, menu prices and the sale/stock settings before taking live orders.

## 5. Configure the three printing destinations

In **设置 (Settings)**:

- **Kitchen:** mains and snacks. Enter the kitchen printer's private LAN IP and port.
- **Kitchen paper:** choose **80mm / 576 dots** for the current 80mm kitchen printer. This selects raster printing so Chinese text and notes wrap to the configured width. Use 58mm only for a 58mm replacement printer.
- **Drinks:** drinks and beer. Enable independent kitchen/drinks printers and enter the drinks station's private LAN IP/port.
- **Cashier receipts:** choose **Windows USB 热敏打印机**, select the installed cashier queue (currently named `POS-80C`), and select **55mm / 384 dots** for the receipt printer specified by the operator. The Windows queue name does not establish paper width. Keep cutter off until verified. Alternatively, choose the independent receipt network mode and configure that printer's IP/port.

If kitchen and drinks share one physical printer, leave independent-printer mode off: the app still creates **two separate preparation tickets**, both using that printer. A mixed order never duplicates an item between tickets. Customer receipts always use their own cashier configuration.

The receipt queue is created once with a successful payment. Checkout defaults to QR: verify QR funds, then press the single **确认收款并清台** button. The table is released and the receipt page opens. Cash remains available by selecting **现金** and entering the amount received. Receipts show frozen line prices, total, payment method, received amount and change.

Use **浏览器打印 / 保存 PDF** for a normal browser print dialog, or open a past transaction's **查看 / 打印收据** link. Browser printing is a manual alternative; avoid printing it again if the automatic cashier job already produced paper.

`SENT` means the network/spooler accepted data, not proof of paper output. If a print is FAILED/UNKNOWN, verify the printer/queue and actual paper before using the audited reprint action. Windows USB RAW output follows the [Microsoft print spooler sequence](https://learn.microsoft.com/en-us/windows/win32/printdocs/sending-data-directly-to-a-printer); printer firmware compatibility still requires a real receipt check.

## 6. Allow phone access

Keep the new PC on the same Wi-Fi/LAN as the phones. In an **administrator PowerShell** in the new project folder:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\enable-lan-access.ps1 -CurrentNetwork
```

For an Ethernet host, add `-InterfaceAlias "Ethernet"`, using the actual adapter name from `Get-NetIPConfiguration`.

On each phone, open the **new PC's current IP** printed by the launcher, e.g. `http://192.168.0.6:8080`. The old PC's bookmark will not point at the new host if its IP differs. The firewall script restricts access to this POS program, port and local subnet; re-run it when moving to a different subnet. Guest Wi-Fi/client isolation can prevent phones reaching the host.

## 7. Optional automatic startup after sign-in

Run as the normal Windows user who operates this POS:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-windows-startup.ps1
```

This installs a new Startup shortcut with the new folder path. The host must be powered on and signed in. Closing a browser does not stop the POS; `Stop-POS.cmd` stops the API and worker. Logs are under `artifacts\windows\`.

## Minimum checks before switching restaurant service

Confirm a phone can sign in, the 20-table list and historical data are present, one mixed order creates separate kitchen/drinks tickets, QR is the default and one payment generates one receipt on POS-80C, and cash change is correct. Recheck the actual receipt paper width, Chinese characters, feed/cutter and printer names/IPs. Keep a fresh off-device database backup.
