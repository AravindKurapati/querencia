import re
import sqlite3

from ._util import upsert_place

_CID = re.compile(r"cid=0x[0-9a-fA-F]+:0x([0-9a-fA-F]+)")


def ingest_question(conn: sqlite3.Connection, data: dict) -> bool:
    m = _CID.search(data.get("placeUrl", ""))
    if not m:
        return False
    key = f"cid:{m.group(1)}"
    upsert_place(conn, key, source="question")
    conn.execute(
        "INSERT INTO visits(place_key, occurred_at, source) VALUES (?,?,?)",
        (key, None, "question"),
    )
    conn.commit()
    return True
