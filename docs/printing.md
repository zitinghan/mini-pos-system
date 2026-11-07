# Kitchen Printing

## Default mock operation

Settings starts in `mock` mode. Every successful worker render creates `/data/tickets/job-ID.png` and a UTF-8 `.txt` equivalent. Authenticated staff can view the PNG from Orders; the directory is not published anonymously. Raster output requires the configured Noto CJK font; it deliberately fails instead of silently substituting unreadable Chinese glyphs. The backend image installs the font. Local developers can set `FONT_PATH` to another CJK font.

Version 1.1 tickets show 可可·南洋咖啡店, without the old Chinese/English shop headings. Table numbers, item quantities/names, and selected options use large 48-pixel text in raster mode, with long lines wrapped to the configured paper width. Text mode uses double-width, double-height printing for these lines. Each ticket has a unique print-job number, batch reference, local date/time, NEW / ADD-ON / REPRINT marker, portions, drink temperature, beer package/bottle count, and optional notes. Reprints retain REPRINT / 重印.

The default single printer receives one job per batch with separate 厨房 (mains/snacks) and 饮料 (drinks/beer) sections. Every item appears once. Settings can enable separate kitchen and beverage IPs/ports; jobs then contain only the matching station's items. Reprints preserve routing and station history. See [v1.1 menu, analytics and migration details](v1.1.md).

Mock simulations:

| Simulation | Result | Meaning |
| --- | --- | --- |
| success | SENT | Preview rendered; simulated send completed |
| connection_failure | FAILED | No bytes sent; order remains saved |
| timeout | UNKNOWN | Simulated timeout after delivery could have started |
| uncertain | UNKNOWN | Delivery cannot be established |

Change simulation back to success, then use the administrator's reprint action to recover. A new job preserves the original failure and records the actor. It always includes **REPRINT / 重印**, including safe retries, to help the kitchen identify duplicates.

## Queue and delivery safety

Submission and outbox insertion share one transaction. The worker claims a PENDING job as SENDING under an immediate SQLite transaction; it commits before rendering, connecting or sending. A partial unique index prevents two queued/sending jobs for the same batch. Multiple workers cannot claim the same row.

Successful socket `sendall` means SENT, **not proof that paper emerged**. Connection/setup failures before any network write are FAILED. Once sending may have begun, any failure is UNKNOWN; a crash/stale claim older than two minutes also becomes UNKNOWN. No automatic resends are performed, even for safe connection failures: an operator controls retries. Manual action is required for UNKNOWN or SENT jobs after checking with the kitchen. Manual reprint requests carry a persistent idempotency key: retrying a lost HTTP response returns the same replacement job even if that job has already finished. Retry is rejected while another attempt is pending/sending. Print history exposes attempt counts and previous outcomes.

## Physical printer setup on the deployment host

1. Reserve a stable private LAN IP for the printer, for example `192.168.1.200`.
2. In Settings choose network mode, enter that IP and TCP port (usually 9100).
3. Start with raster mode, 384 printable dots, `bitImageRaster`, no cutter, three feed lines.
4. Save, queue a test print, and inspect both the status and actual paper.
5. If the printer requires different commands, select its python-escpos profile and `graphics` or `bitImageColumn`. Match printable dot width to the manual; 58mm alone does not establish command compatibility.
6. Enable cutter commands only for a tested compatible cutter. Text mode and encoding (default gb18030) require explicit printer support; encoding alone does not initialize every Chinese firmware mode. Raster is the supported fallback for Chinese.

python-escpos builds commands into a Dummy buffer before a socket is opened. Configuration errors therefore fail before transmission. Network connection timeout is five seconds and send timeout ten seconds. Internal printer hostnames/public/loopback/link-local addresses are rejected; use the printer's reserved private IP. Kitchen tickets contain large table identifiers, prominent quantities, modifiers, batch/time and total portions, without prices. Each additional batch produces only its newly submitted items.

References used during implementation: [python-escpos printer documentation](https://python-escpos.readthedocs.io/en/latest/user/printers.html). No physical printer has been available on this development workstation; Chinese output, feed, raster command, firmware and cutter compatibility require on-site acceptance.
