"""Constants of the OLO Bratislava waste integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "olo_waste"

# Filled with the integration version from manifest.json.
USER_AGENT_FORMAT = "ha-olo-waste/{version} (+https://github.com/MarekZ98/ha-olo-waste)"

OLO_SEARCH_URL = "https://olo-strapi-meilisearch.bratislava.sk/indexes/pickup-day/search"
# Public, search-only key shipped in the olo.sk web app.
OLO_SEARCH_KEY = "ae84ae0982c2162a81eb253765ceaa8593abd9105c71954cf5c9620b0178cbb6"
OLO_GRAPHQL_URL = "https://olo-strapi.bratislava.sk/graphql"
TIMEOUT_SECONDS = 10

CONF_ADDRESS = "address"
UPDATE_INTERVAL = timedelta(hours=24)
HORIZON_DAYS = 90

# OLO wasteType -> waste kind. The order is the display order of the kinds.
WASTE_TYPES: dict[str, str] = {
    "Zmiešaný odpad": "mixed",
    "Plast": "plastic",
    "Papier": "paper",
    "Sklo": "glass",
    "BRO": "bio",
    "KBRO": "kitchen_bio",
}

KIND_NAMES_SK: dict[str, str] = {
    "mixed": "Zmiešaný odpad",
    "plastic": "Plast",
    "paper": "Papier",
    "glass": "Sklo",
    "bio": "Bioodpad zo záhrad",
    "kitchen_bio": "Kuchynský bioodpad",
}

KIND_ICONS: dict[str, str] = {
    "mixed": "mdi:trash-can",
    "plastic": "mdi:bottle-soda-classic",
    "paper": "mdi:newspaper-variant",
    "glass": "mdi:glass-fragile",
    "bio": "mdi:leaf",
    "kitchen_bio": "mdi:food-apple",
}
