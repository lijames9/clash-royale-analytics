"""Thin client for the official Clash Royale API (https://developer.clashroyale.com)."""
from __future__ import annotations

import time
from urllib.parse import quote

import requests

from . import config


def normalize_tag(tag: str) -> str:
    """'#abc123', 'ABC123' -> '#ABC123' (the form the API returns)."""
    return "#" + tag.strip().lstrip("#").upper()


def encode_tag(tag: str) -> str:
    """Tags go in URLs with the '#' percent-encoded as %23."""
    return quote(normalize_tag(tag), safe="")


class ApiError(RuntimeError):
    pass


class ClashClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        min_interval: float = 0.05,
        max_retries: int = 5,
        timeout: float = 15.0,
    ):
        self.base_url = (base_url or config.API_BASE).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {token or config.api_token()}", "Accept": "application/json"}
        )
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_call = 0.0

    def get(self, path: str, params: dict | None = None):
        """GET a path like '/cards'. Returns parsed JSON, or None on 404."""
        url = f"{self.base_url}{path}"
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as e:
                time.sleep(2**attempt)
                last_err = e
                continue

            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
            if r.status_code == 403:
                raise ApiError(
                    "403 Forbidden: the token is invalid or not allowed from this IP address. "
                    "Supercell keys are locked to the IP you registered; check your current IP "
                    "and create a new key if it changed (or use the RoyaleAPI proxy, see .env.example)."
                )
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2**attempt)
                last_err = ApiError(f"{r.status_code}: {r.text[:200]}")
                continue
            raise ApiError(f"{r.status_code} for {path}: {r.text[:300]}")
        raise ApiError(f"Giving up on {path} after {self.max_retries} tries: {last_err}")

    # Endpoints -------------------------------------------------------------

    def player(self, tag: str):
        return self.get(f"/players/{encode_tag(tag)}")

    def battlelog(self, tag: str) -> list[dict]:
        """A player's most recent battles (the API only keeps roughly the last 25-30)."""
        return self.get(f"/players/{encode_tag(tag)}/battlelog") or []

    def cards(self) -> list[dict]:
        return (self.get("/cards") or {}).get("items", [])

    def locations(self) -> list[dict]:
        return (self.get("/locations", {"limit": 300}) or {}).get("items", [])

    def path_of_legend_players(self, location_id: int, limit: int = 200) -> list[dict]:
        """Current Path of Legends leaderboard for one country."""
        data = self.get(f"/locations/{location_id}/pathoflegend/players", {"limit": limit})
        return (data or {}).get("items", [])
