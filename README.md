# OLO Bratislava Waste

Home Assistant custom integration for waste pickup days of [OLO Bratislava](https://olo.sk).
You type a street, pick the exact OLO address, and get a calendar plus a "next pickup" sensor per waste type.
Data is refreshed once a day.

## Install

- **HACS:** HACS → Integrations → ⋮ → Custom repositories → add `https://github.com/MarekZ98/ha-olo-waste`
  (category *Integration*), install **OLO Bratislava Waste**, restart Home Assistant.
- **Manual:** copy `custom_components/olo_waste` into your `config/custom_components/` folder and restart.

## Configure

1. Settings → Devices & services → Add integration → **OLO Bratislava Waste**.
2. Type the street and house number (for example `Primaciálne námestie 1`).
3. Pick the exact address from the OLO list.

Add the integration once per address.

## Entities

- `calendar.*_waste_collection` — all-day event per pickup (summary = Slovak waste type name).
- One date sensor per waste type the address has: mixed waste, plastic, paper, glass, garden bio waste,
  kitchen bio waste. Attribute `days_until`.
- `sensor.*_next_pickup` — next pickup of any type. Attributes `kinds` (waste types on that day) and `days_until`.

OLO publishes the schedule per calendar year, so no dates are shown after 31 December until OLO publishes the new year.
