"""SQLite helpers + demo seed for Aftercall.

Frozen schema (docs/REQUIREMENTS.md §5):
  people(id, name, phone, lang, lat, lng, age, medical_notes,
         emergency_contact_phone, opted_in)
  events(id, playbook_id, polygon, started_at, status)
  call_results(id, event_id, person_id, status, attempt,
               transcript_summary, updated_at)

Plus call_map(call_id -> person_id, event_id): the Dial webhook carries no
metadata, so we persist this at call-placement time to correlate results back to
a person (docs/DIAL.md).
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Iterable, Optional

DB_PATH = os.environ.get("AFTERCALL_DB", os.path.join(os.path.dirname(__file__), "aftercall.db"))
FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures", "people.json")

# Valid statuses (PENDING = call placed, no result yet).
STATUSES = ("PENDING", "OK", "NEEDS_HELP", "DISTRESS", "UNREACHED")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            lang TEXT NOT NULL DEFAULT 'he-IL',
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            age INTEGER,
            medical_notes TEXT DEFAULT '',
            emergency_contact_phone TEXT,
            opted_in INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playbook_id TEXT NOT NULL,
            polygon TEXT NOT NULL,            -- JSON [[lat,lng], ...]
            started_at REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'running'
        );

        CREATE TABLE IF NOT EXISTS call_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            attempt INTEGER NOT NULL DEFAULT 1,
            transcript_summary TEXT DEFAULT '',
            transcript TEXT DEFAULT '',
            updated_at REAL NOT NULL,
            UNIQUE(event_id, person_id),
            FOREIGN KEY(event_id) REFERENCES events(id),
            FOREIGN KEY(person_id) REFERENCES people(id)
        );

        -- explicit per-event target list (ad-hoc campaigns or polygon snapshot)
        CREATE TABLE IF NOT EXISTS event_targets (
            event_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            PRIMARY KEY(event_id, person_id)
        );

        -- callId -> person correlation (no webhook metadata; see docs/DIAL.md)
        CREATE TABLE IF NOT EXISTS call_map (
            call_id TEXT PRIMARY KEY,
            person_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            kind TEXT NOT NULL DEFAULT 'triage',   -- triage | escalation
            created_at REAL NOT NULL
        );

        -- audited relief disbursements (Stripe test mode); see docs/TOS.md §4
        CREATE TABLE IF NOT EXISTS disbursements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            person_id INTEGER NOT NULL,
            amount_cents INTEGER NOT NULL,
            state TEXT NOT NULL,               -- offered | confirmed | disbursed | denied
            stripe_ref TEXT,
            updated_at REAL NOT NULL
        );
        """
    )
    conn.commit()
    # Migration for DBs created before the transcript column existed.
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(call_results)")}
    if "transcript" not in cols:
        conn.execute("ALTER TABLE call_results ADD COLUMN transcript TEXT DEFAULT ''")
        conn.commit()
    conn.close()


def seed_demo_people(path: str = FIXTURES) -> int:
    with open(path, encoding="utf-8") as fh:
        people = json.load(fh)
    conn = connect()
    for p in people:
        conn.execute(
            """INSERT OR REPLACE INTO people
               (id, name, phone, lang, lat, lng, age, medical_notes,
                emergency_contact_phone, opted_in)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (p["id"], p["name"], p["phone"], p.get("lang", "he-IL"),
             p["lat"], p["lng"], p.get("age"), p.get("medical_notes", ""),
             p.get("emergency_contact_phone"), int(p.get("opted_in", 0))),
        )
    conn.commit()
    conn.close()
    return len(people)


# ---------------------------------------------------------------------------
# Point-in-polygon (ray casting). polygon = [[lat, lng], ...]
# ---------------------------------------------------------------------------
def point_in_polygon(lat: float, lng: float, polygon: list[list[float]]) -> bool:
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i][0], polygon[i][1]   # lat, lng
        yj, xj = polygon[j][0], polygon[j][1]
        intersect = ((xi > lng) != (xj > lng)) and (
            lat < (yj - yi) * (lng - xi) / ((xj - xi) or 1e-12) + yi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def find_opted_in_in_polygon(polygon: list[list[float]]) -> list[dict[str, Any]]:
    conn = connect()
    rows = conn.execute("SELECT * FROM people WHERE opted_in = 1").fetchall()
    conn.close()
    out = []
    for r in rows:
        if point_in_polygon(r["lat"], r["lng"], polygon):
            out.append(dict(r))
    return out


def add_person(name: str, phone: str, lat: float, lng: float,
               lang: str = "he-IL", emergency_contact_phone: Optional[str] = None) -> int:
    """Insert an ad-hoc opted-in person (dashboard campaign) and return its id."""
    conn = connect()
    row = conn.execute("SELECT COALESCE(MAX(id),0)+1 AS nid FROM people").fetchone()
    nid = row["nid"]
    conn.execute(
        """INSERT INTO people
           (id, name, phone, lang, lat, lng, age, medical_notes,
            emergency_contact_phone, opted_in)
           VALUES (?,?,?,?,?,?,?,?,?,1)""",
        (nid, name, phone, lang, lat, lng, None, "", emergency_contact_phone),
    )
    conn.commit()
    conn.close()
    return nid


def update_person_location(person_id: int, lat: float, lng: float) -> None:
    conn = connect()
    conn.execute("UPDATE people SET lat=?, lng=? WHERE id=?", (lat, lng, person_id))
    conn.commit()
    conn.close()


def get_person(person_id: int) -> Optional[dict[str, Any]]:
    conn = connect()
    row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_person_by_phone(phone: str) -> Optional[dict[str, Any]]:
    conn = connect()
    row = conn.execute("SELECT * FROM people WHERE phone = ?", (phone,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
def create_event(playbook_id: str, polygon: list[list[float]]) -> int:
    conn = connect()
    cur = conn.execute(
        "INSERT INTO events (playbook_id, polygon, started_at, status) VALUES (?,?,?,?)",
        (playbook_id, json.dumps(polygon), time.time(), "running"),
    )
    conn.commit()
    event_id = cur.lastrowid
    conn.close()
    return event_id


def add_targets(event_id: int, person_ids: Iterable[int]) -> None:
    conn = connect()
    conn.executemany(
        "INSERT OR IGNORE INTO event_targets (event_id, person_id) VALUES (?,?)",
        [(event_id, pid) for pid in person_ids],
    )
    conn.commit()
    conn.close()


def get_targets(event_id: int) -> list[int]:
    conn = connect()
    rows = conn.execute(
        "SELECT person_id FROM event_targets WHERE event_id=?", (event_id,)
    ).fetchall()
    conn.close()
    return [r["person_id"] for r in rows]


def get_event(event_id: int) -> Optional[dict[str, Any]]:
    conn = connect()
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["polygon"] = json.loads(d["polygon"])
    return d


# ---------------------------------------------------------------------------
# Call results
# ---------------------------------------------------------------------------
def upsert_result(event_id: int, person_id: int, status: str,
                  attempt: int = 1, summary: str = "", transcript: str = "") -> None:
    conn = connect()
    conn.execute(
        """INSERT INTO call_results
             (event_id, person_id, status, attempt, transcript_summary, transcript, updated_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(event_id, person_id) DO UPDATE SET
             status=excluded.status,
             attempt=excluded.attempt,
             transcript_summary=excluded.transcript_summary,
             -- keep the last real transcript when a later update carries none
             transcript=CASE WHEN excluded.transcript != ''
                             THEN excluded.transcript ELSE call_results.transcript END,
             updated_at=excluded.updated_at""",
        (event_id, person_id, status, attempt, summary, transcript, time.time()),
    )
    conn.commit()
    conn.close()


def get_result(event_id: int, person_id: int) -> Optional[dict[str, Any]]:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM call_results WHERE event_id=? AND person_id=?",
        (event_id, person_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def event_status(event_id: int) -> dict[str, Any]:
    """Frozen contract: counters + per-person dots."""
    event = get_event(event_id)
    if not event:
        return {"event_id": event_id, "counters": {}, "people": []}
    # Prefer the explicit target snapshot (ad-hoc campaigns + recorded polygon
    # runs); fall back to a live point-in-polygon query for older events.
    target_ids = get_targets(event_id)
    if target_ids:
        targets = [p for p in (get_person(pid) for pid in target_ids) if p]
    else:
        targets = find_opted_in_in_polygon(event["polygon"])

    conn = connect()
    res_rows = conn.execute(
        "SELECT person_id, status, attempt, transcript_summary, transcript, updated_at"
        " FROM call_results WHERE event_id=?",
        (event_id,),
    ).fetchall()
    conn.close()
    by_person = {r["person_id"]: r for r in res_rows}

    counters = {s: 0 for s in STATUSES}
    people = []
    for p in targets:
        r = by_person.get(p["id"])
        status = r["status"] if r else "PENDING"
        counters[status] = counters.get(status, 0) + 1
        people.append({
            "person_id": p["id"],
            "name": p["name"],
            "phone": p["phone"],
            "lat": p["lat"],
            "lng": p["lng"],
            "status": status,
            "attempt": (r["attempt"] if r else 1),
            "summary": (r["transcript_summary"] if r else ""),
            "transcript": (r["transcript"] if r else ""),
            "updated_at": (r["updated_at"] if r else None),
        })
    counters["total"] = len(targets)
    return {
        "event_id": event_id,
        "playbook_id": event["playbook_id"],
        "counters": counters,
        "people": people,
    }


# ---------------------------------------------------------------------------
# call_id -> person correlation
# ---------------------------------------------------------------------------
def map_call(call_id: str, person_id: int, event_id: int, kind: str = "triage") -> None:
    conn = connect()
    conn.execute(
        "INSERT OR REPLACE INTO call_map (call_id, person_id, event_id, kind, created_at) VALUES (?,?,?,?,?)",
        (call_id, person_id, event_id, kind, time.time()),
    )
    conn.commit()
    conn.close()


def lookup_call(call_id: str) -> Optional[dict[str, Any]]:
    conn = connect()
    row = conn.execute("SELECT * FROM call_map WHERE call_id=?", (call_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Disbursements (audit log)
# ---------------------------------------------------------------------------
def record_disbursement(event_id: Optional[int], person_id: int, amount_cents: int,
                        state: str, stripe_ref: str = "") -> int:
    conn = connect()
    cur = conn.execute(
        "INSERT INTO disbursements (event_id, person_id, amount_cents, state, stripe_ref, updated_at) VALUES (?,?,?,?,?,?)",
        (event_id, person_id, amount_cents, state, stripe_ref, time.time()),
    )
    conn.commit()
    did = cur.lastrowid
    conn.close()
    return did


def disbursed_total_cents() -> int:
    conn = connect()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_cents),0) AS t FROM disbursements WHERE state='disbursed'"
    ).fetchone()
    conn.close()
    return int(row["t"])


if __name__ == "__main__":
    init_db()
    n = seed_demo_people()
    print(f"init_db OK; seeded {n} people into {DB_PATH}")
