# Takeaway and drink preparation options

Every menu product, including noodles, rice, sides, water and beer, has a 用餐方式 choice: 堂食 (default) or 打包. It appears first in the item picker, applies to that item/quantity and costs RM0. Mixed dine-in/takeaway items can share a table and order batch. To order different preparation for the same product, add it as separate lines.

Prepared drinks (all 15 paid-drink SKUs except MINERAL_WATER and CANNED) additionally have:

| Group | Choices | Rule |
| --- | --- | --- |
| 甜度 | Kosong（不加糖）, Siu Dai（少甜） | At most one; tap again to return to normal |
| 浓度 | Kao（加浓） | Optional, compatible with either sweetness |
| 冰量 | 少冰 Less Ice, 去冰 No Ice | At most one; only shown for iced drinks |

All options are free. Kosong means no added sugar. Bottled water, canned drinks, complimentary plain water and beer have the takeaway choice but no sweetness, strength or ice customization. Administrators can disable individual modifier options in existing menu configuration.

Selecting hot clears any selected ice adjustment and hides the ice group, keeping takeaway/sweetness/strength. The backend rejects hot+ice conflicts, simultaneous sweetness choices, simultaneous ice choices, dine-in+takeaway and options borrowed from another product. No Ice retains the explicitly selected ICED price; it does not silently switch to the hot price. The existing RM1 Kopi/Teh promotion and zero-priced plain water remain unchanged.

Selections use the existing item-modifier snapshots and appear in drafts, cart/bill, history, large-text preparation tickets for the correct stall and the separate cashier receipt. Old item, receipt and print snapshots are never backfilled or rewritten. Printing/retry routing and payment idempotency are unchanged.

Takeaway/drink configuration is an idempotent menu-data upgrade; the separately added order-editing workflow uses migration `0006_order_editing`. Startup seeding adds missing per-item groups/options to existing products without resetting base/variant prices, stock flags, enabled states or conflicts on existing options. The packaging group permits omission at the API level for existing phones/drafts; omission has the legacy dine-in meaning. Current UI defaults to an explicit dine-in choice and always keeps one packing choice selected.
