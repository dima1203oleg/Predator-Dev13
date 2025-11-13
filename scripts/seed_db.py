import argparse

import sqlalchemy as sa

DDL = """
create table if not exists datasets(
  id serial primary key,
  name text,
  checksum text,
  schema_json jsonb,
  created_at timestamptz default now()
);
create table if not exists records(
  pk text primary key,
  op_hash text unique,
  payload jsonb,
  created_at timestamptz default now()
);
create index if not exists idx_records_op_hash on records(op_hash);
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    args = p.parse_args()
    engine = sa.create_engine(args.db, pool_pre_ping=True)
    with engine.begin() as cx:
        for stmt in DDL.split(";"):
            if stmt.strip():
                cx.exec_driver_sql(stmt + ";")
    print("OK: schema created")


if __name__ == "__main__":
    main()
