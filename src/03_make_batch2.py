""" Create the second input batch used to demonstrate SCD Type 2.
Run from root:  python src/03_make_batch2.py

It reads the ORIGINAL data/Sales.Customers.csv (never modified) and writes a changed copy to
data/batch2/Sales.Customers.csv. Business keys (CustomerID) are never changed.
Only customers that have orders both before and after the cutoff date are picked, so the
facts of both periods show the before/after versions.

  6 customers  -> new CustomerCategoryID       (SCD Type 2: new version)
  3 customers  -> new BuyingGroupID            (SCD Type 2: new version)
  3 customers  -> new DeliveryCityID           (SCD Type 2: new version)
  2 customers  -> new PhoneNumber only         (SCD Type 1: overwritten, no new version)
"""
import argparse
import csv
from datetime import datetime
from pathlib import Path


def find(data_dir: Path, name: str) -> Path:
    """Always return the ORIGINAL file (never anything inside data/batch2)."""
    direct = data_dir / name
    if direct.exists():
        return direct
    matches = [p for p in sorted(data_dir.rglob(name)) if "batch2" not in [x.lower() for x in p.parts]]
    if not matches:
        raise SystemExit(f"{name} not found under {data_dir}")
    return matches[0]


def read_rows(path: Path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, delimiter=";", quotechar='"')
        header = next(reader)
        return header, list(reader)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--cutoff", default="2016-01-01", help="date the changes take effect")
    args = ap.parse_args()
    data_dir = Path(args.data_dir)
    cutoff = datetime.strptime(args.cutoff, "%Y-%m-%d").date()

    source = find(data_dir, "Sales.Customers.csv")
    print(f"Reading the original customers from {source}")
    h, customers = read_rows(source)
    ix = {c: i for i, c in enumerate(h)}
    oh, orders = read_rows(find(data_dir, "Sales.Orders.csv"))
    oi = {c: i for i, c in enumerate(oh)}
    _, cats = read_rows(find(data_dir, "Sales.CustomerCategories.csv"))
    _, cities = read_rows(find(data_dir, "Application.Cities.csv"))

    before, after = set(), set()
    for r in orders:
        d = datetime.strptime(r[oi["OrderDate"]], "%d/%m/%Y").date()
        (before if d < cutoff else after).add(r[oi["CustomerID"]])
    candidates = sorted(before & after, key=int)[:14]
    if len(candidates) < 14:
        raise SystemExit("not enough customers with orders before and after the cutoff")

    cat_ids = sorted({r[0] for r in cats}, key=int)
    city_ids = sorted({r[0] for r in cities}, key=int)
    by_id = {r[ix["CustomerID"]]: r for r in customers}
    changes = []   # (customer_id, column, old, new, scd_type)

    def change(cid, col, new, scd):
        row = by_id[cid]
        old = row[ix[col]]
        row[ix[col]] = new
        changes.append((cid, col, old, new, scd))

    for cid in candidates[0:6]:        # category -> next category id
        old = by_id[cid][ix["CustomerCategoryID"]]
        change(cid, "CustomerCategoryID", cat_ids[(cat_ids.index(old) + 1) % len(cat_ids)], "Type 2")
    for cid in candidates[6:9]:        # buying group -> other group (1 <-> 2, NULL -> 1)
        old = by_id[cid][ix["BuyingGroupID"]]
        change(cid, "BuyingGroupID", {"1": "2", "2": "1"}.get(old, "1"), "Type 2")
    for cid in candidates[9:12]:       # delivery city -> next city id
        old = by_id[cid][ix["DeliveryCityID"]]
        change(cid, "DeliveryCityID", city_ids[(city_ids.index(old) + 1) % len(city_ids)], "Type 2")
    for cid in candidates[12:14]:      # phone only (Type 1)
        change(cid, "PhoneNumber", "(415) 555-0100", "Type 1")

    out = data_dir / "batch2"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "Sales.Customers.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";", quotechar='"', lineterminator="\r\n")
        w.writerow(h)
        w.writerows(customers)
    with open(out / "batch2_changes.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["CustomerID", "Column", "OldValue", "NewValue", "ScdType"])
        w.writerows(changes)
    print(f"Wrote {out / 'Sales.Customers.csv'} ({len(customers)} customers, {len(changes)} changes)")
    print(f"Change log: {out / 'batch2_changes.csv'}")
    print(f"Run with:   python run_pipe.py --load 2 --effective-date {args.cutoff}")


if __name__ == "__main__":
    main()
