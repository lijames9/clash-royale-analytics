# Clash Royale: win probability and balance patches

Two questions, answered with battle data from the official Clash Royale API:

1. **Win probability:** how well can a match outcome be predicted from the two decks,
   card levels and trophies? Can deck strength be separated from player skill?
2. **Balance patches:** when Supercell buffs or nerfs a card, what actually happens to its
   win rate? (Event study / difference-in-differences against unchanged cards.)

## Setup (once)

From an Anaconda Prompt in this folder:

```bat
conda env create -f environment.yml
conda activate clash
pip install -e .
python -m ipykernel install --user --name clash --display-name "Python (clash)"
copy .env.example .env
```

Then open `.env` and fill in:

- `CR_API_TOKEN`: create a key at <https://developer.clashroyale.com> (My Account → Create New Key).
  Keys are locked to an IP address, so enter your current public IP (search "what is my IP").
  If your IP changes, make a new key, or use the RoyaleAPI proxy option in `.env.example`.
- `CR_SEED_TAGS`: your own player tag (and any others), comma-separated.

Check everything works:

```bat
pytest
```

## Collecting data

The API only returns each player's last ~25 battles, so history builds up by crawling
regularly. Each run follows opponents found on the previous run, so coverage snowballs.

```bat
python -m clashlab.collect --max-players 300                 :: quick run
python -m clashlab.collect --max-players 3000 --leaderboards 15  :: bigger run, seeded from top players
python -m clashlab.flatten                                   :: rebuild data/processed/battles.parquet
```

Run the collector at least daily. The balance-patch analysis needs data from before
*and* after a patch, so start early. (Windows Task Scheduler can run it automatically.)

## Layout

```
src/clashlab/   api.py (API client) · collect.py (crawler) · flatten.py (raw -> table) · config.py
notebooks/      analysis, starting with 01_first_look.ipynb
data/raw/       daily battles_YYYY-MM-DD.jsonl.gz (git-ignored)
data/processed/ battles.parquet (git-ignored)
data/state/     crawl state: seen battle ids, player frontier (git-ignored)
tests/          offline tests using a fake API
```

## Notes

- `team` is always the player whose log was crawled and `opp` their opponent.
- Card levels are stored as `level - maxLevel` (0 = max level), which puts all rarities on one scale.
- Data use follows Supercell's Fan Content Policy. This project only reads public battle logs.
