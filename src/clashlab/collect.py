"""Crawl battle logs and append new 1v1 battles to data/raw/battles_YYYY-MM-DD.jsonl.gz.

The API only keeps each player's last ~25 battles, so history has to be built up by
crawling repeatedly (ideally daily). Each run:
  1. Builds a queue of players: your seed tags, Path of Legends leaderboard players
     (optional), and opponents discovered on earlier runs (the "frontier").
  2. Fetches each player's battle log, keeps 1v1 battles not already saved.
  3. Adds every new opponent to the frontier so the crawl snowballs.

Usage (from the project root, with the clash env active):
    python -m clashlab.collect --max-players 300
    python -m clashlab.collect --max-players 2000 --leaderboards 10
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
from datetime import datetime, timezone

from tqdm import tqdm

from . import config
from .api import ApiError, ClashClient, normalize_tag

SEEN_FILE = config.STATE_DIR / "seen_battle_ids.txt"
FRONTIER_FILE = config.STATE_DIR / "frontier.txt"


def battle_id(b: dict) -> str:
    """Stable id for a battle: its timestamp plus every participant's tag.

    The same battle shows up in both players' logs, so this is what deduplicates it.
    """
    tags = sorted(p["tag"] for side in ("team", "opponent") for p in b.get(side, []))
    return f"{b.get('battleTime', '')}_{'_'.join(tags)}"


def is_1v1(b: dict) -> bool:
    return len(b.get("team", [])) == 1 and len(b.get("opponent", [])) == 1


def _read_lines(path) -> list[str]:
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def load_state() -> tuple[set[str], list[str]]:
    return set(_read_lines(SEEN_FILE)), _read_lines(FRONTIER_FILE)


def save_state(new_ids: list[str], frontier: list[str], frontier_cap: int) -> None:
    with SEEN_FILE.open("a", encoding="utf-8") as f:
        f.writelines(i + "\n" for i in new_ids)
    # keep the most recently discovered players, bounded so the file stays small
    FRONTIER_FILE.write_text("\n".join(frontier[-frontier_cap:]) + "\n", encoding="utf-8")


def leaderboard_tags(client: ClashClient, n_countries: int, per_country: int) -> list[str]:
    """Top Path of Legends players from the first `n_countries` countries the API lists."""
    tags: list[str] = []
    countries = [loc for loc in client.locations() if loc.get("isCountry")]
    for loc in countries[:n_countries]:
        try:
            tags += [p["tag"] for p in client.path_of_legend_players(loc["id"], per_country)]
        except ApiError as e:
            print(f"  skipping leaderboard for {loc.get('name')}: {e}")
    return tags


def run(max_players: int, leaderboards: int, per_country: int, frontier_cap: int, seed: int) -> None:
    client = ClashClient()
    seen, frontier = load_state()
    rng = random.Random(seed)

    seeds = [normalize_tag(t) for t in config.seed_tags()]
    board = [normalize_tag(t) for t in leaderboard_tags(client, leaderboards, per_country)] if leaderboards else []
    explore = frontier[:]
    rng.shuffle(explore)

    queue = list(dict.fromkeys(seeds + board + explore))[:max_players]  # dedupe, keep order
    if not queue:
        raise SystemExit("Nothing to crawl: set CR_SEED_TAGS in .env or pass --leaderboards N.")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = config.RAW_DIR / f"battles_{today}.jsonl.gz"
    new_ids: list[str] = []
    discovered: list[str] = []
    collected_at = datetime.now(timezone.utc).isoformat()

    with gzip.open(out_path, "at", encoding="utf-8") as out:
        for tag in tqdm(queue, desc="players"):
            try:
                battles = client.battlelog(tag)
            except ApiError as e:
                if "403" in str(e):
                    raise
                continue
            for b in battles:
                if not is_1v1(b):
                    continue
                bid = battle_id(b)
                if bid in seen:
                    continue
                seen.add(bid)
                new_ids.append(bid)
                b["_battle_id"] = bid
                b["_collected_at"] = collected_at
                b["_crawled_tag"] = tag
                out.write(json.dumps(b, separators=(",", ":")) + "\n")
                discovered.append(b["opponent"][0]["tag"])

    crawled = set(queue)
    frontier = [t for t in frontier if t not in crawled] + [t for t in dict.fromkeys(discovered) if t not in crawled]
    save_state(new_ids, frontier, frontier_cap)
    print(f"Saved {len(new_ids)} new battles from {len(queue)} players -> {out_path.name}")
    print(f"Frontier now holds {min(len(frontier), frontier_cap)} players for the next run")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-players", type=int, default=300, help="battle logs to fetch this run")
    ap.add_argument("--leaderboards", type=int, default=0,
                    help="also seed from the Path of Legends leaderboards of this many countries")
    ap.add_argument("--per-country", type=int, default=100)
    ap.add_argument("--frontier-cap", type=int, default=50_000)
    ap.add_argument("--seed", type=int, default=0, help="random seed for frontier sampling")
    a = ap.parse_args()
    run(a.max_players, a.leaderboards, a.per_country, a.frontier_cap, a.seed)


if __name__ == "__main__":
    main()
