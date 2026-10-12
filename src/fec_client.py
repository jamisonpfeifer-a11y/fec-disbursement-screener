"""Thin client for the openFEC API (https://api.open.fec.gov/developers/).

Get a free API key at https://api.data.gov/signup/ and set it as the
FEC_API_KEY environment variable. The shared DEMO_KEY also works but allows
only about 30 requests an hour, which is enough for a quick test and no more.

Two pagination styles are used. Candidate and committee endpoints take a
`page` number. The Schedule B (disbursements) endpoint ignores `page` and
returns the same first records every time; it must be walked with the cursor
values the API returns in `pagination.last_indexes`.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Iterator

import requests

BASE_URL = "https://api.open.fec.gov/v1"


class FECAPIError(RuntimeError):
    pass


class FECRateLimitError(FECAPIError):
    """The hourly request quota is used up (HTTP 429 after all retries)."""


@dataclass
class FECClient:
    api_key: str | None = None
    max_retries: int = 5
    request_pause_sec: float = 1.0  # pause between requests, to be polite to the API

    def __post_init__(self):
        self.api_key = self.api_key or os.environ.get("FEC_API_KEY")
        if not self.api_key:
            raise FECAPIError(
                "No FEC API key found. Set the FEC_API_KEY environment variable "
                "or pass api_key=. Get a free key at https://api.data.gov/signup/"
            )
        self._session = requests.Session()

    def _get(self, path: str, params: dict[str, Any]) -> dict:
        params = {**params, "api_key": self.api_key}
        url = f"{BASE_URL}{path}"
        last_err: FECAPIError | None = None
        rate_limited = False

        for attempt in range(self.max_retries):
            try:
                resp = self._session.get(url, params=params, timeout=60)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_err = FECAPIError(f"Network error fetching {url}: {e}")
                time.sleep(2 ** attempt * 2)
                continue

            if resp.status_code == 429:
                rate_limited = True
                time.sleep(2 ** attempt * 2)
                continue
            if 400 <= resp.status_code < 500:
                # Bad key, bad parameters, unknown ID: retrying will not help.
                raise FECAPIError(f"FEC API error {resp.status_code} for {url}: {resp.text[:300]}")
            if resp.status_code != 200:
                last_err = FECAPIError(f"FEC API error {resp.status_code} for {url}: {resp.text[:300]}")
                time.sleep(1)
                continue

            time.sleep(self.request_pause_sec)
            return resp.json()

        if rate_limited:
            raise FECRateLimitError(f"Rate limited (HTTP 429) fetching {url}; hourly quota is likely used up")
        raise last_err or FECAPIError(f"Failed to fetch {url} after {self.max_retries} attempts")

    def _paginate(self, path: str, params: dict[str, Any], max_pages: int = 200) -> Iterator[dict]:
        """Page-number pagination (candidates, committees, totals)."""
        page = 1
        params = dict(params)
        while page <= max_pages:
            params["page"] = page
            data = self._get(path, params)
            results = data.get("results", [])
            if not results:
                return
            yield from results
            if page >= data.get("pagination", {}).get("pages", page):
                return
            page += 1

    def _paginate_keyset(self, path: str, params: dict[str, Any], max_pages: int = 1000) -> Iterator[dict]:
        """Cursor pagination for Schedule B.

        Each response carries `pagination.last_indexes`; sending those values
        with the next request returns the following page. Stops when the API
        returns no cursor or no results, or when a page brings nothing new
        (which guards against an endless loop if the cursor is ignored).
        """
        params = dict(params)
        seen: set = set()
        for _ in range(max_pages):
            data = self._get(path, params)
            results = data.get("results", [])
            fresh = [r for r in results if r.get("sub_id") is None or r["sub_id"] not in seen]
            if not fresh:
                return
            seen.update(r["sub_id"] for r in fresh if r.get("sub_id") is not None)
            yield from fresh
            cursor = (data.get("pagination") or {}).get("last_indexes")
            if not cursor:
                return
            params = {**params, **cursor}

    # ---- Candidates ----

    def get_candidates(
        self,
        cycle: int,
        office: str | None = None,  # 'H', 'S', 'P'
        state: str | None = None,
        party: str | None = None,
        incumbent_challenge: str | None = None,  # 'I', 'C', 'O'
        per_page: int = 100,
    ) -> list[dict]:
        params = {"cycle": cycle, "per_page": per_page, "sort": "name"}
        if office:
            params["office"] = office
        if state:
            params["state"] = state
        if party:
            params["party"] = party
        if incumbent_challenge:
            params["incumbent_challenge"] = incumbent_challenge
        return list(self._paginate("/candidates/", params))

    def get_candidate_committees(self, candidate_id: str, cycle: int) -> list[dict]:
        params = {"cycle": cycle, "per_page": 100}
        return list(self._paginate(f"/candidate/{candidate_id}/committees/", params))

    # ---- Disbursements (Schedule B) ----

    def get_disbursements(
        self,
        committee_id: str,
        two_year_transaction_period: int,
        per_page: int = 100,
        max_pages: int = 1000,
    ) -> list[dict]:
        params = {
            "committee_id": committee_id,
            "two_year_transaction_period": two_year_transaction_period,
            "per_page": per_page,
            "sort": "-disbursement_date",
        }
        return list(self._paginate_keyset("/schedules/schedule_b/", params, max_pages=max_pages))

    # ---- Committee financial totals ----

    def get_committee_totals(self, committee_id: str, cycle: int) -> list[dict]:
        params = {"cycle": cycle, "per_page": 10}
        return list(self._paginate(f"/committee/{committee_id}/totals/", params, max_pages=1))
