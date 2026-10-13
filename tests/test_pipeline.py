"""Offline tests: a fake API stands in for Supercell's, so no token or network is needed."""
from __future__ import annotations

import pytest

from clashlab import api, collect, config, flatten


def make_player(tag, crowns, cards=("Hog Rider", "Fireball", "The Log", "Musketeer",
                                     "Ice Spirit", "Skeletons", "Cannon", "Ice Golem")):
    return {
        "tag": tag, "name": tag.strip("#"), "startingTrophies": 7000, "trophyChange": 30 if crowns else -30,
        "crowns": crowns, "kingTowerHitPoints": 4000,
        "cards": [{"name": n, "id": i, "level": 14, "maxLevel": 14 if i % 2 else 11,
                   "elixirCost": 3, "evolutionLevel": 0} for i, n in enumerate(cards)],
        "supportCards": [{"name": "Tower Princess"}],
    }


def make_battle(time, a, b, a_crowns, b_crowns):
    return {"type": "pathOfLegend", "battleTime": time, "gameMode": {"name": "Ranked1v1"},
            "arena": {"name": "Legendary Arena"},
            "team": [make_player(a, a_crowns)], "opponent": [make_player(b, b_crowns)]}


class FakeClient:
    """Two players who fought each other once, plus a 2v2 that should be ignored."""

    def __init__(self, *_, **__):
        shared = ("20261013T120000.000Z", "#AAA", "#BBB")
        self.logs = {
            "#AAA": [make_battle(*shared, 2, 1),
                     make_battle("20261013T110000.000Z", "#AAA", "#CCC", 0, 1),
                     {"type": "2v2", "battleTime": "20261013T100000.000Z",
                      "team": [make_player("#AAA", 1), make_player("#X", 1)],
                      "opponent": [make_player("#Y", 0), make_player("#Z", 0)]}],
            "#BBB": [make_battle(shared[0], "#BBB", "#AAA", 1, 2)],  # same battle, other side
        }

    def battlelog(self, tag):
        return self.logs.get(tag, [])

    def locations(self):
        return []


@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    for name in ("RAW_DIR", "PROCESSED_DIR", "STATE_DIR"):
        d = tmp_path / name
        d.mkdir()
        monkeypatch.setattr(config, name, d)
    monkeypatch.setattr(collect, "SEEN_FILE", tmp_path / "STATE_DIR" / "seen.txt")
    monkeypatch.setattr(collect, "FRONTIER_FILE", tmp_path / "STATE_DIR" / "frontier.txt")
    monkeypatch.setattr(collect, "ClashClient", FakeClient)
    monkeypatch.setattr(config, "seed_tags", lambda: ["aaa", "#bbb"])
    return tmp_path


def test_tag_helpers():
    assert api.normalize_tag(" abc12 ") == "#ABC12"
    assert api.encode_tag("#abc12") == "%23ABC12"


def test_battle_id_is_side_independent():
    a = make_battle("20261013T120000.000Z", "#AAA", "#BBB", 1, 0)
    b = make_battle("20261013T120000.000Z", "#BBB", "#AAA", 0, 1)
    assert collect.battle_id(a) == collect.battle_id(b)


def test_collect_dedupes_and_snowballs(tmp_data):
    collect.run(max_players=10, leaderboards=0, per_country=0, frontier_cap=100, seed=0)
    df = flatten.build(config.RAW_DIR)
    assert len(df) == 2                      # shared battle counted once, 2v2 dropped
    assert "#CCC" in collect.FRONTIER_FILE.read_text()

    # second run finds nothing new
    collect.run(max_players=10, leaderboards=0, per_country=0, frontier_cap=100, seed=0)
    assert len(flatten.build(config.RAW_DIR)) == 2


def test_flatten_columns(tmp_data):
    collect.run(max_players=10, leaderboards=0, per_country=0, frontier_cap=100, seed=0)
    df = flatten.build(config.RAW_DIR)
    row = df[df.opp_tag == "#CCC"].iloc[0]
    assert row.team_won == 0
    assert len(row.team_cards) == 8 and list(row.team_cards) == sorted(row.team_cards)
    assert set(row.team_levels_vs_max) == {0, 3}
    assert str(df.battle_time.dt.tz) == "UTC"
