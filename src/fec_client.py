"""
Thin wrapper around the openFEC API (https://api.open.fec.gov/developers/).

Get a free API key at https://api.data.gov/signup/ and set it as the
FEC_API_KEY environment variable. The shared "DEMO_KEY" works too but is
throttled hard (30 req/hour) and unsuitable for anything beyond a quick test.
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


@dataclass
class FECClient:
    api_key: str | None = None
    max_retries: int = 5
    request_pause_sec: float = 1.0  # be polite to the public API, especially after repeated runs

    def __post_init__(self):
        self.api_key = self.api_key or os.environ.get("FEC_API_KEY")
        if not self.api_key:
            raise FECAPIError(
                "No FEC API key found. Set FEC_API_KEY env var or pass api_key= "
                "explicitly. Get a free key at https://api.data.gov/signup/"
            )
        self._session = requests.Session()

    def _get(self, path: str, params: dict[str, Any]) -> dict:
        params = {**params, "api_key": self.api_key}
        url = f"{BASE_URL}{path}"
        last_err = None
        for attempt in range(self.max_retries):
            try:
                resp = self._session.get(url, params=params, timeout=60)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # Network hiccup or slow response from a large committee's data -
                # back off and retry rather than crashing the whole run.
                last_err = FECAPIError(f"Network error fetching {url}: {e}")
                time.sleep(2 ** attempt * 2)
                continue
            if resp.status_code == 429:
                # Rate limited - back off and retry
                time.sleep(2 ** attempt * 2)
                continue
            if resp.status_code != 200:
                last_err = FECAPIError(
                    f"FEC API error {resp.status_code} for {url}: {resp.text[:500]}"
                )
                time.sleep(1)
                continue
            time.sleep(self.request_pause_sec)
            return resp.json()
        raise last_err or FECAPIError(f"Failed to fetch {url} after {self.max_retries} attempts")

    def _paginate(self, path: str, params: dict[str, Any], max_pages: int = 200) -> Iterator[dict]:
        page = 1
        params = dict(params)
        while page <= max_pages:
            params["page"] = page
            data = self._get(path, params)
            results = data.get("results", [])
            if not results:
                return
            yield from results
            pagination = data.get("pagination", {})
            if page >= pagination.get("pages", page):
                return
            page += 1

    # ---- Candidates ----

    def get_candidates(
        self,
        cycle: int,
        office: str | None = None,  # 'H', 'S', 'P'
        state: str | None = None,
        party: str | None = None,
        incumbent_challenge: str | None = None,  # 'I','C','O'
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
        max_pages: int = 500,
    ) -> list[dict]:
        params = {
            "committee_id": committee_id,
            "two_year_transaction_period": two_year_transaction_period,
            "per_page": per_page,
            "sort": "-disbursement_date",
        }
        return list(self._paginate("/schedules/schedule_b/", params, max_pages=max_pages))

    # ---- Committee financial totals (for normalizing spend as a share) ----

    def get_committee_totals(self, committee_id: str, cycle: int) -> list[dict]:
        params = {"cycle": cycle, "per_page": 10}
        return list(self._paginate(f"/committee/{committee_id}/totals/", params, max_pages=1))