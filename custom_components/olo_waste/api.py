"""OLO Bratislava HTTP client: address search (Meilisearch) and pickup rows (GraphQL)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .const import OLO_GRAPHQL_URL, OLO_SEARCH_KEY, OLO_SEARCH_URL, TIMEOUT_SECONDS

if TYPE_CHECKING:
    import aiohttp

SEARCH_LIMIT = 10

PICKUP_DAYS_QUERY = (
    "query PickupDaysByAddress($address: String!) { pickupDays(filters: {address: {eq: $address}}) "
    "{ data { id attributes { registrationNumber address containerVolume frequency wasteType frequencySeason } } } }"
)


class OloApiError(Exception):
    """OLO answered with an error or an unexpected shape."""


@dataclass(frozen=True)
class PickupRow:
    """One pickup rule row as OLO stores it (rows repeat per container)."""

    waste_type: str
    # "[14,14]", "[36,36];[3,3]", "[-,1];[-,1,-,-]" ...
    frequency: str
    # "01/04-31/10, 01/11-31/03"; None = all year.
    frequency_season: str | None


def parse_search(raw: object) -> list[str]:
    """Distinct addresses of a Meilisearch answer, in OLO's order."""
    if not isinstance(raw, dict) or not isinstance(raw.get("hits"), list):
        raise OloApiError("OLO search: unexpected response")
    seen: set[str] = set()
    addresses: list[str] = []
    for hit in raw["hits"]:
        item = hit.get("pickup-day") if isinstance(hit, dict) else None
        address = item.get("address") if isinstance(item, dict) else None
        if not isinstance(address, str) or not address:
            raise OloApiError("OLO search: unexpected response")
        if address in seen:
            continue
        seen.add(address)
        addresses.append(address)
    return addresses


def parse_pickup_rows(raw: object) -> list[PickupRow]:
    """Pickup rows of a GraphQL answer; rows without wasteType or frequency are skipped."""
    if not isinstance(raw, dict):
        raise OloApiError("OLO pickup days: unexpected response")
    errors = raw.get("errors")
    if errors is not None:
        if not isinstance(errors, list):
            raise OloApiError("OLO pickup days: unexpected response")
        if errors:
            messages = [str(e.get("message")) if isinstance(e, dict) else str(e) for e in errors]
            raise OloApiError(f"OLO pickup days: {'; '.join(messages)}")
    data = raw.get("data")
    if data is None:
        raise OloApiError("OLO pickup days: no data")
    pickup_days = data.get("pickupDays") if isinstance(data, dict) else None
    items = pickup_days.get("data") if isinstance(pickup_days, dict) else None
    if not isinstance(items, list):
        raise OloApiError("OLO pickup days: unexpected response")
    rows: list[PickupRow] = []
    for item in items:
        attributes = item.get("attributes") if isinstance(item, dict) else None
        if not isinstance(attributes, dict):
            raise OloApiError("OLO pickup days: unexpected response")
        waste_type = attributes.get("wasteType")
        frequency = attributes.get("frequency")
        season = attributes.get("frequencySeason")
        for value in (waste_type, frequency, season):
            if value is not None and not isinstance(value, str):
                raise OloApiError("OLO pickup days: unexpected response")
        if waste_type is None or frequency is None:
            continue
        rows.append(PickupRow(waste_type=waste_type, frequency=frequency, frequency_season=season))
    return rows


class OloClient:
    """Talks to OLO. Only the address string (search text or chosen address) leaves HA."""

    def __init__(self, session: aiohttp.ClientSession, user_agent: str) -> None:
        self._session = session
        self._user_agent = user_agent

    async def search(self, query: str) -> list[str]:
        """Addresses matching `query` (street + number), distinct, in OLO's order."""
        body = {
            "q": query,
            "limit": SEARCH_LIMIT,
            "offset": 0,
            "filter": ['type = "pickup-day"'],
            "sort": ["pickup-day.address:asc"],
            "distinct": "pickup-day.address",
            "attributesToSearchOn": ["pickup-day.address"],
        }
        raw = await self._post(OLO_SEARCH_URL, body, {"Authorization": f"Bearer {OLO_SEARCH_KEY}"})
        return parse_search(raw)

    async def pickup_rows(self, address: str) -> list[PickupRow]:
        """Pickup rule rows of one exact address ([] = OLO knows no pickups there)."""
        body = {"query": PICKUP_DAYS_QUERY, "variables": {"address": address}}
        raw = await self._post(OLO_GRAPHQL_URL, body, {})
        return parse_pickup_rows(raw)

    async def _post(self, url: str, body: dict[str, Any], headers: dict[str, str]) -> object:
        all_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self._user_agent,
            **headers,
        }
        async with asyncio.timeout(TIMEOUT_SECONDS):
            async with self._session.post(url, json=body, headers=all_headers) as response:
                if response.status != 200:
                    raise OloApiError(f"OLO answered HTTP {response.status}")
                try:
                    return await response.json(content_type=None)
                except ValueError as err:
                    raise OloApiError("OLO answered invalid JSON") from err
