CREATE TABLE users (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  name VARCHAR(80) NOT NULL UNIQUE,
  pin_hash VARCHAR NOT NULL,
  role VARCHAR NOT NULL,
  failed_attempts INTEGER NOT NULL,
  locked_until VARCHAR,
  CHECK (role IN ('STAFF','ADMIN'))
);

CREATE TABLE auth_sessions (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  token_hash VARCHAR NOT NULL UNIQUE,
  user_id INTEGER NOT NULL REFERENCES users(id),
  expires_at VARCHAR NOT NULL
);

CREATE TABLE login_attempts (
  key VARCHAR NOT NULL,
  count INTEGER NOT NULL,
  expires_at VARCHAR NOT NULL,
  PRIMARY KEY (key)
);

CREATE TABLE restaurant_tables (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  name VARCHAR NOT NULL UNIQUE
);

CREATE TABLE table_sessions (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  table_id INTEGER NOT NULL REFERENCES restaurant_tables(id),
  status VARCHAR NOT NULL,
  closed_at VARCHAR,
  CHECK (status IN ('OCCUPIED','PAYMENT_PENDING','PAID','CANCELLED'))
);

CREATE TABLE menu_categories (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  name VARCHAR NOT NULL,
  display_order INTEGER NOT NULL
);

CREATE TABLE menu_items (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  category_id INTEGER NOT NULL REFERENCES menu_categories(id),
  name VARCHAR NOT NULL,
  base_price INTEGER NOT NULL,
  active BOOLEAN NOT NULL,
  CHECK (base_price >= 0)
);

CREATE TABLE modifier_groups (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  name VARCHAR NOT NULL,
  minimum INTEGER NOT NULL,
  maximum INTEGER NOT NULL,
  display_order INTEGER NOT NULL,
  CHECK (minimum >= 0 AND maximum >= minimum)
);

CREATE TABLE modifier_options (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  group_id INTEGER NOT NULL REFERENCES modifier_groups(id),
  name VARCHAR NOT NULL,
  price INTEGER NOT NULL,
  is_default BOOLEAN NOT NULL,
  display_order INTEGER NOT NULL,
  CHECK (price >= 0)
);

CREATE TABLE menu_item_modifier_groups (
  item_id INTEGER NOT NULL REFERENCES menu_items(id),
  group_id INTEGER NOT NULL REFERENCES modifier_groups(id),
  PRIMARY KEY (item_id, group_id)
);

CREATE TABLE order_batches (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  session_id INTEGER NOT NULL REFERENCES table_sessions(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  status VARCHAR NOT NULL,
  submission_key VARCHAR UNIQUE,
  submitted_at VARCHAR,
  CHECK (status IN ('DRAFT','SUBMITTED','CANCELLED'))
);

CREATE TABLE order_items (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  batch_id INTEGER NOT NULL REFERENCES order_batches(id),
  menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
  name VARCHAR NOT NULL,
  quantity INTEGER NOT NULL,
  base_price INTEGER NOT NULL,
  unit_price INTEGER NOT NULL,
  line_total INTEGER NOT NULL,
  status VARCHAR NOT NULL,
  CHECK (quantity > 0 AND line_total >= 0)
);

CREATE TABLE order_item_modifiers (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  item_id INTEGER NOT NULL REFERENCES order_items(id),
  option_id INTEGER NOT NULL REFERENCES modifier_options(id),
  name VARCHAR NOT NULL,
  price INTEGER NOT NULL
);

CREATE TABLE payments (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  session_id INTEGER NOT NULL UNIQUE REFERENCES table_sessions(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  idempotency_key VARCHAR NOT NULL UNIQUE,
  request_hash VARCHAR NOT NULL,
  method VARCHAR NOT NULL,
  total INTEGER NOT NULL,
  received INTEGER NOT NULL,
  change INTEGER NOT NULL,
  CHECK (method IN ('CASH','QR','OTHER')),
  CHECK (total > 0 AND received >= total AND change = received - total)
);

CREATE TABLE printer_configurations (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  config JSON NOT NULL
);

CREATE TABLE print_jobs (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  batch_id INTEGER REFERENCES order_batches(id),
  status VARCHAR NOT NULL,
  attempts INTEGER NOT NULL,
  reprint BOOLEAN NOT NULL,
  ticket JSON NOT NULL,
  error VARCHAR,
  preview VARCHAR,
  claimed_at VARCHAR,
  CHECK (status IN ('PENDING','SENDING','SENT','FAILED','UNKNOWN'))
);

CREATE TABLE audit_logs (
  id INTEGER NOT NULL PRIMARY KEY,
  created_at VARCHAR NOT NULL,
  updated_at VARCHAR NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(id),
  action VARCHAR NOT NULL,
  request_key VARCHAR UNIQUE,
  details JSON NOT NULL
);

CREATE UNIQUE INDEX uq_active_table ON table_sessions(table_id) WHERE status IN ('OCCUPIED','PAYMENT_PENDING');

CREATE INDEX ix_order_batches_session_id ON order_batches(session_id);

CREATE INDEX ix_order_items_batch_id ON order_items(batch_id);

CREATE INDEX ix_order_item_modifiers_item_id ON order_item_modifiers(item_id);

CREATE INDEX ix_print_jobs_status ON print_jobs(status);

CREATE INDEX ix_print_jobs_batch_id ON print_jobs(batch_id);

CREATE INDEX ix_payments_created ON payments(created_at);

CREATE INDEX ix_table_sessions_table_id ON table_sessions(table_id);

CREATE UNIQUE INDEX uq_user_draft ON order_batches(session_id, user_id) WHERE status = 'DRAFT';
CREATE UNIQUE INDEX uq_active_print_batch ON print_jobs(batch_id) WHERE status IN ('PENDING','SENDING');

CREATE INDEX ix_modifier_options_group_id ON modifier_options(group_id);
