# B1 customer amount display

The locally verified B1 display uses COM2, 2400 baud, 8 data bits, no parity,
one stop bit, and no flow control. Its numeric command is `ESC @ ESC Q A`,
followed by an ASCII amount with two decimal places and carriage return.

Create the ignored local file `backend/data/customer-display.json`:

```json
{"enabled": true, "port": "COM2", "baudrate": 2400}
```

Set `enabled` to false to disable it. No server restart is needed after changing
this file. Install backend dependencies with `pip install -r backend/requirements.txt`.

Pressing **查看账单 / 收款** displays the amount due immediately, before navigating
to checkout. Opening checkout also refreshes it. Editing the final discounted price
updates the display after a short pause. Successful cash payment displays change;
QR/other payments leave the paid total visible. Amounts are MYR, stored as integer
sen. The numeric display does not show labels or Chinese text.

Authenticated cashier/admin requests validate the current bill and checkout state.
Late updates for paid tables are rejected. Serial writes run outside database
transactions, with bounded write timeouts. Display disconnection never rolls back
a committed payment. The checkout page warns about failed amount updates; serial
errors are also logged in the server log. Reconnecting does not replay payments.

Focused checks: from `backend`, run
`../.venv/Scripts/python.exe -m pytest tests/test_customer_display.py -q`.

`CUSTOMER_DISPLAY_CONFIG` can override the configuration path. Browser acceptance tests point it at their isolated temporary directory, so simulated checkouts never write to the restaurant's physical serial display. Normal Windows startup keeps the existing local configuration path.
