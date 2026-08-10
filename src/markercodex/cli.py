"""MarkerCodex command-line interface."""

from __future__ import annotations

import argparse

from markercodex.db import DEFAULT_DB, initialize
from markercodex.export import build_site, export_all
from markercodex.importer import import_csv


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="markercodex")
    root.add_argument("--db", default=str(DEFAULT_DB), help="DuckDB database path")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Initialize or migrate the database")
    export = commands.add_parser("export", help="Write Parquet and CSV snapshots")
    export.add_argument("--output", default="data/exports")
    site = commands.add_parser("build-site", help="Generate the static atlas")
    site.add_argument("--output", default="site")
    bulk = commands.add_parser("import", help="Bulk import marker assertions from CSV")
    bulk.add_argument("csv")
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "init":
        initialize(args.db)
        print(f"Initialized {args.db}")
    elif args.command == "export":
        paths = export_all(args.db, args.output)
        print("\n".join(str(path) for path in paths.values()))
    elif args.command == "build-site":
        print(build_site(args.db, args.output))
    elif args.command == "import":
        print(f"Imported {import_csv(args.csv, args.db)} rows")


if __name__ == "__main__":
    main()
