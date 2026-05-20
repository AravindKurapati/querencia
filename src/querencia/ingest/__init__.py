import sqlite3
import zipfile
from pathlib import Path

from . import commutes, labels, photos, questions, reviews
from ._util import iter_zip_jsons, read_zip_json

R_PREFIX = "Takeout/Maps (your places)/Reviews.json"
PHOTO_PREFIX = "Takeout/Maps/Photos and videos/"
Q_PREFIX = "Takeout/Maps/Answers to automated questions/"
LABEL_PREFIX = "Takeout/Maps/My labeled places/"
COMMUTE_PREFIX = "Takeout/Maps/Commute routes/"


def run_all(conn: sqlite3.Connection, zip_path: str | Path) -> dict:
    summary = {"reviews": 0, "photos": 0, "questions": 0, "labels": 0, "commutes": 0}
    with zipfile.ZipFile(zip_path) as z:
        rdata = read_zip_json(z, R_PREFIX)
        if rdata:
            summary["reviews"] = reviews.ingest_reviews(conn, rdata)
        for name, data in iter_zip_jsons(z, PHOTO_PREFIX):
            fname = name.rsplit("/", 1)[-1].removesuffix(".json")
            if photos.ingest_photo_sidecar(conn, data, fname):
                summary["photos"] += 1
        for _, data in iter_zip_jsons(z, Q_PREFIX):
            if questions.ingest_question(conn, data):
                summary["questions"] += 1
        for _, data in iter_zip_jsons(z, LABEL_PREFIX):
            summary["labels"] += labels.ingest_labels(conn, data)
        for _, data in iter_zip_jsons(z, COMMUTE_PREFIX):
            summary["commutes"] += commutes.ingest_commutes(conn, data)
    return summary
