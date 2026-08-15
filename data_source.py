"""
Fetches SportyBet Nigeria data.

SportyBet has no official public API and no dedicated "results" endpoint —
only upcoming (pre-match) and live events. This module therefore:
  1. searches upcoming events to let you /track a match before kickoff
  2. polls live events afterwards
  3. treats "was live, now no longer in the live list" as the finish signal

IMPORTANT: The exact JSON field names for live scores are not officially
documented anywhere (SportyBet doesn't publish a spec). The functions below
try several common key spellings defensively. The first time you run this
for real, call debug_dump_live_event() once and check your terminal output —
if score fields come back as None, open the printed raw JSON, find the real
key names, and add them to the SCORE_KEYS lists below.
"""
import os
import requests

API_BASE = os.getenv("SPORTY_API_BASE", "")
API_KEY = os.getenv("SPORTY_API_KEY", "")

HEADERS = {"X-API-Key": API_KEY}

# Defensive key lists — order = priority. Extend these if your test call
# shows different field names in the raw JSON.
HOME_SCORE_KEYS = ["home_score", "homeScore", "score_home", "home"]
AWAY_SCORE_KEYS = ["away_score", "awayScore", "score_away", "away"]
STATUS_KEYS = ["match_status", "status_text", "status"]


def _get(url, params=None):
    resp = requests.get(url, headers=HEADERS, params=params or {}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _extract(d, keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def search_upcoming_events(team_query, sport="football", page_size=50):
    """
    Search upcoming events by a loose team-name match, e.g. "arsenal".
    Returns a list of simplified dicts: event_id, home_team, away_team,
    start_time, tournament_name.
    """
    data = _get(
        f"{API_BASE}/get_upcoming_events",
        params={"sport": sport, "page": 1, "page_size": page_size, "today_only": False},
    )
    tournaments = data.get("data", {}).get("tournaments", [])
    query = team_query.lower()
    matches = []
    for t in tournaments:
        for ev in t.get("events", []):
            home = ev.get("home_team", "")
            away = ev.get("away_team", "")
            if query in home.lower() or query in away.lower():
                matches.append(
                    {
                        "event_id": ev.get("event_id"),
                        "home_team": home,
                        "away_team": away,
                        "start_time": ev.get("start_time"),
                        "tournament_name": t.get("tournament_name"),
                    }
                )
    return matches


def get_live_events(sport="football"):
    """Returns a dict {event_id: raw_event_json} for all currently live events."""
    data = _get(f"{API_BASE}/get_live_events", params={"sport": sport})
    tournaments = data.get("data", {}).get("tournaments", [])
    live = {}
    for t in tournaments:
        for ev in t.get("events", []):
            eid = ev.get("event_id")
            if eid:
                live[eid] = ev
    return live


def extract_score(raw_event):
    """Best-effort (home_score, away_score, status_text) from a raw live event."""
    home = _extract(raw_event, HOME_SCORE_KEYS)
    away = _extract(raw_event, AWAY_SCORE_KEYS)
    status = _extract(raw_event, STATUS_KEYS)
    return home, away, status


def debug_dump_live_event(sport="football"):
    """Run this once manually to inspect real field names, e.g.:
       python -c "from data_source import debug_dump_live_event; debug_dump_live_event()"
    """
    import json

    live = get_live_events(sport)
    if not live:
        print("No live events right now — try again during a live match.")
        return
    first = next(iter(live.values()))
    print(json.dumps(first, indent=2))
