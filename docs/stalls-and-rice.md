# Rice menu and three-stall printing

The menu contains 33 active products after this update. 海南咖喱饭、卤肉饭 and 咖喱饭 are mains, each RM8 regular / RM10 large. Large portions use an explicit RM2 surcharge. 卤肉 and 咖喱鸡 are independent RM8 sides with quantity and notes, no mandatory modifiers; they appear first in 小吃. Existing stock controls, backend totals and historical price snapshots apply to the new items.

| Preparation ticket | Items |
| --- | --- |
| 面档 / KITCHEN | 云吞面、面粉粿 and existing snacks |
| 饭档 / RICE | 海南咖喱饭、卤肉饭、咖喱饭、卤肉、咖喱鸡 |
| 饮料档 / BEVERAGE | Drinks, plain water and beer |

A submitted batch creates one ticket per nonempty stall, sharing table/batch reference. Items never appear in two stalls. Add-on batches print only new items. A single 80mm printer prints the separate tickets in queue order; independent stations can have separate network IPs/ports in Settings. With independent stations enabled, a blank rice IP uses the noodle printer and its port. Cashier receipts keep their independent 55mm configuration and full-table payment.

Migration `0005_rice_stall` adds nullable `menu_items.printer_group` and `display_order` (default 0). It assigns the existing `CURRY_RICE` menu item to RICE without duplicating it. New products use stable SKUs `BRAISED_PORK_RICE`, `PLAIN_CURRY_RICE`, `BRAISED_PORK_SIDE` and `CURRY_CHICKEN_SIDE`. Seeding is idempotent and preserves subsequent administrator price/stock edits. Routing defaults to the category when no item override exists; side priority is stored in the database.

Submitted item and print-job snapshots are not rewritten. Old tickets reprint with their original item routing; the new routing applies to new submissions. Order history, payments, receipts, promotions and table-session timestamps remain intact. No database reset or sample live orders are required.

Implementation: menu model/migration/seed, backend menu ordering and snapshots, shared stall definitions, order outbox, ticket rendering, print-worker routing, printer schema/validation and Settings fields; Orders station labels; backend pricing/routing/migration tests and mobile browser acceptance. Physical output and any new stall IPs require on-site checking; mocked transports and rendered previews do not establish successful paper delivery.

## Verification — 2026-11-07

- All 175 backend cases verified: full regression run had 174 passes and one legacy concurrency assertion still expecting two test tickets. Updated it to verify all three stalls are claimed exactly once; its targeted rerun passed. The only warning is an existing Starlette/AnyIO deprecation.
- Frontend: 23 unit tests passed; TypeScript/Vite production build passed.
- Browser: all 15 acceptance cases passed at 360/390/412 pixels, including priority sides, regular/large rice pricing, three disjoint stall tickets, cash/QR receipts, completed-order collapse, outside-click modal dismissal, RM1 promotion and sold-out synchronization.
- Migration/seed ran twice on a database backup and twice on the stopped live database. Original users, sessions, item/modifier snapshots, payments, print jobs, receipts, audit logs, old menu prices/options, promotions, table identities and printer configuration were preserved. New products total 33, with one active entry per stable SKU. No sample orders or test jobs were inserted into the live system.
- Rice-ticket raster preview and phone ordering screenshots inspected. The current printer destination and 80mm preparation / 55mm cashier widths were preserved; physical three-stall paper delivery remains an on-site check.
