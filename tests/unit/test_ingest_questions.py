from querencia.db import connect, init_schema
from querencia.ingest.questions import ingest_question

QA = {"placeUrl": "https://google.com/maps/?cid=0x3bae16a82da08f99:0x3ce7be42251d9745",
      "selectedChoice": "Yes", "question": "Is this dish shown? Sujuk"}


def test_question_creates_cid_place_and_visit(tmp_path):
    conn = connect(tmp_path / "t.db"); init_schema(conn)
    ingest_question(conn, QA)
    place = conn.execute("SELECT place_key FROM places").fetchone()
    assert place[0].startswith("cid:")
    visit = conn.execute("SELECT source, occurred_at FROM visits").fetchone()
    assert visit[0] == "question"
    assert visit[1] is None
