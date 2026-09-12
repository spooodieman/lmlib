# Calling the itinerary/buffering Timefold solver

The CW ETA Planner service now exposes a second solver alongside the original
trip-based one: the **itinerary model**, which lets cargo buffer through a
marshalling yard (sail early, wait at the yard, then continue) instead of
only shipping direct. It lives at a separate path so the original endpoints
are untouched:

| Method | Path                                  | Description                              |
|--------|----------------------------------------|-------------------------------------------|
| POST   | `/api/v1/itinerary/solver/run`         | Runs the itinerary solver, returns the voyage/cargo schedule |
| GET    | `/api/v1/itinerary/solver/report/pdf`  | Downloads the last result as a styled PDF |

Start the CW ETA Planner Spring Boot service first (`http://localhost:8080`
by default) — this is the same service `CWEtaPlannerClient` already talks to.

## Try it now

**[`anmol_test_itinerary.py`](anmol_test_itinerary.py)** is a runnable script
using this exact pattern — the same way
[`anmol_test.py`](anmol_test.py) already demonstrates the original endpoint:
a hand-built `input_data` dict, POSTed to the running service, with the
schedule and PDF pulled back down. This is genuinely how input reaches the
solver today — there's no automated feed from anywhere else yet, so a script
like this (or your own equivalent, hand-building the dict from whatever data
you have) is the real workflow, not just a doc example.

```bash
python anmol_test_itinerary.py
```

## Key differences from `/api/v1/solver/run`

- **No digital-twin default.** `fabricationYards`, `installationSites`,
  `vessels`, and `monopiles` must all be supplied explicitly in the request
  body — there's no built-in fallback scenario for this model yet.
- **`tripCount` is required**, not optional, and it means something more
  specific here: it must be the number of trips the digital twin's own
  already-solved schedule actually used, fed in as a real count — not a
  search-space size to guess at.
- The response shape is different (voyages and cargo, not trips and
  monopiles) — see `ItineraryOptimizationResponse` in the CW ETA Planner repo
  for the exact fields.

## `lmlib`'s existing client doesn't fully cover this endpoint yet

`CWEtaPlannerClient.run_solver()` passes every input through
`CWEtaPlannerInputPayload`, which only models `vessels`/`monopiles` — it has
no fields for `fabricationYards`, `marshallingYards`, or `installationSites`,
so those keys get silently dropped before the request is ever sent. Until
that schema is extended, call the itinerary endpoint directly with
`requests` instead of going through `run_solver()`. `download_report_pdf()`
has no such issue — it just downloads bytes — so it works as-is.

```python
import requests
from lmlib.eta_calculator import CWEtaPlannerClient

BASE_URL = "http://localhost:8080"

payload = {
    "resetBeforeRun": True,
    "tripCount": 6,  # <- from the digital twin's own solved schedule, not a guess
    "fabricationYards": [
        {"id": "FAB-01", "name": "Rostock", "latitude": 54.14, "longitude": 12.10,
         "operationalCalendar": "24/7", "capacity": 50}
    ],
    "marshallingYards": [
        {"id": "MAR-01", "name": "Eemshaven", "latitude": 53.44, "longitude": 6.83,
         "operationalCalendar": "24/7", "capacity": 20,
         "loadingRate": 2.0, "dischargeRate": 2.0, "holdingTimeDays": 5}
    ],
    "installationSites": [
        {"id": "SITE-01", "name": "Alpha", "latitude": 54.50, "longitude": 6.20,
         "operationalCalendar": "May-Oct", "capacity": 100,
         "operationalFromDay": 1, "operationalUntilDay": 365}
    ],
    "vessels": [
        {"id": "VESSEL-01", "name": "Brave Tern", "capacityWeightTons": 100,
         "maxMonopiles": 4, "speedKnots": 14.0, "availableFromDay": 30,
         "compatibleGrillageTypes": ["Type-A"], "operationalCalendar": "24/7",
         "vesselClass": "TClass"}
    ],
    "monopiles": [
        {"id": "MP-A", "weightTons": 60, "lengthM": 70, "diameterM": 8,
         "grillageType": "Type-A", "fabricationYardId": "FAB-01",
         "installationSiteId": "SITE-01", "fabricationCompletionDay": 20,
         "requiredInstallationSequence": 1, "targetInstallationDay": 90}
    ],
}

response = requests.post(f"{BASE_URL}/api/v1/itinerary/solver/run", json=payload, timeout=60)
response.raise_for_status()
result = response.json()
print(result["hardFeasible"], result["score"])
for vessel in result["vesselItineraries"]:
    print(vessel["vesselId"], vessel["voyages"])

# The PDF download works fine through the existing typed client:
pdf_client = CWEtaPlannerClient(base_url=BASE_URL, base_path="/api/v1/itinerary")
pdf_client.download_report_pdf(output_filename="itinerary_schedule_report.pdf")
```

## Error responses

- `400` with a `violations` list — the same `RequestValidationService` bounds
  checks the original endpoint uses (unique ids, day-of-year ranges,
  positive weights, etc.), plus a check that `tripCount` was supplied.
- `500` with an `error`/`message` body when the solver's own internal
  consistency check rejects a solve — a known, narrow, occasionally-
  reproducible issue in this prototype. Retrying the same request may
  succeed on a different search path.

## Follow-up (not done yet)

Extending `CWEtaPlannerInputPayload` (and adding `CWFabYardInput` /
`CWMarshallingYardInput` / `CWInstallationSiteInput` models alongside the
existing `CWVesselInput`/`CWMonopileInput`) so `run_solver()` can be pointed
at either endpoint through one typed interface is the natural next step,
but is out of scope for this change.
