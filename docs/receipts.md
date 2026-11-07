# Customer receipts and split preparation tickets

Successful payment saves an immutable receipt snapshot and one original cashier print job in the same SQLite transaction as the payment and table release. If saving that queue fails, payment rolls back. If physical printing later fails, payment remains completed and the table remains released; retry is an explicit audited operation. Retrying a payment or reloading its receipt page never creates a second payment or original print.

Checkout defaults to QR and uses one final **确认收款并清台** action. The QR verification checkbox and extra confirmation dialog are removed. The button records the operator's payment confirmation; there is no bank integration. Cash still validates the received amount, and stale totals/idempotency checks remain on the server. Draft discard remains explicit.

The receipt page opens after checkout and is also available from transaction history. It shows table/receipt number, timestamp, cashier, frozen item names/modifiers/portions and prices, total, method, received amount and change. It supports browser printing/Save PDF with 58/80mm print styling, preview, initial printing of legacy transactions, and safe reprints. Cashier/admin permission is required; receipt previews are not exposed to staff.

Preparation creates separate KITCHEN (noodles/existing snacks), RICE (rice dishes and 卤肉/咖喱鸡 sides) and BEVERAGE (drinks/beer) jobs for the nonempty groups in each submitted batch. They share table/batch references and contain no duplicated items. The jobs can use one printer, or Settings can route them to independent stall IPs. Only new items in an add-on batch print. Customer receipts are an independent financial document for the full paid table; payment remains full-table. See [the rice menu and three-stall update](stalls-and-rice.md).

The cashier destination is independent: mock/preview, private LAN TCP, or a locally installed Windows ESC/POS queue. The current receipt printer uses Windows USB RAW spooling, queue name `POS-80C`, and the operator-specified **55mm paper / 384-dot** raster layout; the kitchen printer uses 80mm/576 dots. Settings supports 55mm, 58mm and 80mm receipt paper and the browser print page follows the selected paper width. Chinese glyphs come from the configured CJK font. Windows mode needs the installed driver/queue on the host; it does not use a phone's USB connection. Acceptance by Windows or the TCP socket is not proof of physical output.

Migration `0004_receipts` adds the receipts table and nullable payment/transport metadata to print jobs, with unique original/active payment-print indexes. Existing financial and print history remains unchanged. Old paid transactions can be viewed without auto-printing; their first explicit print saves a snapshot. Tables T16–T20 are added idempotently without changing existing table identities or sessions.

Moving hosts, including database restore, drivers, printer selection, phone firewall access and startup: [manual Windows setup and PC transfer guide](windows-pc-move.md).

## Verification — 2026-11-07

- Full backend regression suite: **160 passed** (one dependency deprecation warning).
- Frontend unit suite: **22 passed**, including independent 55mm receipt styling; production TypeScript/Vite build passed.
- Browser acceptance: **12 passed**, covering 360/390/412-pixel screens, split preparation tickets, cash receipts/history, and one-click default QR checkout.
- Backup/auth/database invariant checks: **8 passed**.
- Migration and idempotent seed ran twice on a backup of the existing restaurant database. Historical users, sessions, items/modifiers, payments, print jobs and audit logs matched the originals.
- Live upgrade preserved all existing records, existing table identities, menu/option prices and promotions. It added T16–T20 and configured the independently installed `POS-80C` cashier queue for the operator's 55mm receipt paper / 384 dots. The queue could be opened and closed without sending a print job.
- Kitchen/drinks configuration changed from 384 dots/text mode to **576 dots/raster mode** for the actual 80mm kitchen printer. The rendered preview confirms long notes use the wider line width while item/options remain large. Settings now exposes 58mm/80mm presets instead of a fixed 58mm heading.
- Customer receipt raster and browser print layouts were inspected. No live sample sales were inserted and no hardware print was sent. Paper width, Chinese glyphs, feed/cutter and actual delivery to each stall still require physical checks; separate stall IPs must be supplied in Settings.

Main implementation files: `backend/alembic/versions/0004_receipts.py`, `backend/app/services/receipts.py`, `backend/app/services/orders.py`, `backend/app/printing/{jobs,tickets,worker,windows}.py`, API/models/schemas and table seed; frontend Receipt, Checkout, Settings, History, Orders, Session and table count; receipt, regression and browser tests. Database backups, tickets, local configuration and test artifacts remain outside source control.
