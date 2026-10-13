"""Turn the raw battle logs into one tidy table: data/processed/battles.parquet.

One row per battle (deduplicated across days). "team" is the player whose log we
crawled and "opp" is their opponent. Card columns hold lists sorted by card name, so the
same deck always looks the same.

Usage:
    python -m clashlab.flatten
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd

from . import config


def _side(p: dict, prefix: str) -> dict:
    cards = sorted(p.get("cards", []), key=lambda c: c.get("name", ""))
    support = p.get("supportCards") or []
    return {
        f"{prefix}_tag": p.get("tag"),
        f"{prefix}_name": p.get("name"),
        f"{prefix}_starting_trophies": p.get("startingTrophies"),
        f"{prefix}_trophy_change": p.get("trophyChange"),
        f"{prefix}_crowns": p.get("crowns", 0),
        f"{prefix}_king_hp": p.get("kingTowerHitPoints"),
        f"{prefix}_elixir_leaked": p.get("elixirLeaked"),
        f"{prefix}_cards": [c.get("name") for c in cards],
        f"{prefix}_card_ids": [c.get("id") for c in cards],
        # API levels are per rarity; level - maxLevel puts every card on one scale (0 = maxed)
        f"{prefix}_levels_vs_max": [
            (c["level"] - c["maxLevel"]) if c.get("level") is not None and c.get("maxLevel") else None
            for c in cards
        ],
        f"{prefix}_evo_levels": [c.get("evolutionLevel", 0) for c in cards],
        f"{prefix}_elixir_costs": [c.get("elixirCost") for c in cards],
        f"{prefix}_tower_troop": support[0].get("name") if support else None,
    }


def flatten_battle(b: dict) -> dict:
    team, opp = b["team"][0], b["opponent"][0]
    row = {
        "battle_id": b.get("_battle_id"),
        "battle_time": b.get("battleTime"),
        "type": b.get("type"),
        "game_mode": (b.get("gameMode") or {}).get("name"),
        "arena": (b.get("arena") or {}).get("name"),
        "league_number": b.get("leagueNumber"),
        "is_ladder_tournament": b.get("isLadderTournament"),
        "collected_at": b.get("_collected_at"),
    }
    row.update(_side(team, "team"))
    row.update(_side(opp, "opp"))
    tc, oc = row["team_crowns"], row["opp_crowns"]
    row["team_won"] = None if tc == oc else int(tc > oc)  # crowns tie -> draw
    return row


def iter_raw(raw_dir: Path = config.RAW_DIR):
    for path in sorted(raw_dir.glob("battles_*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)


def build(raw_dir: Path = config.RAW_DIR) -> pd.DataFrame:
    rows = [flatten_battle(b) for b in iter_raw(raw_dir)]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["battle_time"] = pd.to_datetime(df["battle_time"], format="%Y%m%dT%H%M%S.%fZ", utc=True)
    df = df.drop_duplicates("battle_id").sort_values("battle_time").reset_index(drop=True)
    return df


def main() -> None:
    df = build()
    if df.empty:
        print("No raw battles yet. Run `python -m clashlab.collect` first.")
        return
    out = config.PROCESSED_DIR / "battles.parquet"
    df.to_parquet(out, index=False)
    span = f"{df.battle_time.min():%Y-%m-%d} to {df.battle_time.max():%Y-%m-%d}"
    print(f"Wrote {len(df):,} battles ({span}) -> {out}")
    print(df["type"].value_counts().to_string())


if __name__ == "__main__":
    main()
