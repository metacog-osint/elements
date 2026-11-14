"""Elements' history: every item it has published, kept after it leaves the feed.

The code is the doctrine kit's history log (doctrine/kit/python/tic_doctrine/history.py, format tic-history/1,
doctrine/kit/docs/history-log.md). It was first written here (13 Nov 2026) and moved into the kit unchanged in format
(kit 0.5.0, 14 Nov 2026), so every program keeps the same log. This module keeps Elements' names for it and the wording
of Elements' ended list, which names the NWS catch-up.

history/log/YYYY/MM/DD.jsonl (closed days gzipped once), history/state.json (the items open now) and
site/data/ended.geojson (the items that ended in the last ENDED_DAYS days) are as before."""
from .common import ROOT  # noqa: F401  first: puts the doctrine kit on sys.path
from tic_doctrine import history as _kit  # noqa: E402
from tic_doctrine.history import (  # noqa: E402,F401
    ENDED_DAYS, FORMAT, RECENT_DAYS, STATUS_KEYS, TIER_RANK, VOLATILE, _line, _stamp, _t, append_log, close_days,
    end_time, ended_ids_in, fingerprint, lane, lanes_ok, load_state, log_path, read_days, save_state, update)


def ended_collection(root, state, now, days: int = ENDED_DAYS) -> dict:
    """Items that ended in the last `days` days and are not open again, newest end first (the kit's list, with
    Elements' wording)."""
    coll = _kit.ended_collection(root, state, now, days, program="elements", name="Elements")
    coll["what"] = ("Elements items that ended in the last %d days: they left the feed while their source was read "
                    "successfully, or were NWS alerts issued and ended between two runs. Not active: not drawn on the "
                    "map and not in the feed. Each keeps its last version; `history` gives first_seen, last_seen, "
                    "ended_at (the first run without it, or the alert's own end) and end_reason. The full record is "
                    "history/log/ in the Elements repository." % days)
    return coll
