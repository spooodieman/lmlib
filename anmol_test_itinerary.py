"""
Minimalist script to test lmlib against the itinerary/buffering solver endpoint, the same way
anmol_test.py does for the original /api/v1/solver/run endpoint. Same running Spring Boot server,
different path (/api/v1/itinerary/...).

Uses raw `requests` for the solve call instead of CWEtaPlannerClient.run_solver(): that method
routes input through CWEtaPlannerInputPayload, which only models vessels/monopiles and would
silently drop fabricationYards/marshallingYards/installationSites before the request is ever sent.
download_report_pdf() has no such issue, so it's reused as-is.
"""

import requests

from lmlib.eta_calculator import CWEtaPlannerClient

BASE_URL = "http://localhost:8080"


def main():
    print("=== 1. Checking CW ETA Planner Service Health ===")
    client = CWEtaPlannerClient(base_url=BASE_URL)

    try:
        status = client.check_status()
        print(f"Status response     : {status.get('status')}")
        print(f"Service API Version : {status.get('apiVersion')}\n")
    except Exception as e:
        print(f"Failed to connect to API: {e}")
        return

    print("=== 2. Defining Itinerary Input Parameters ===")
    input_data = {
        "resetBeforeRun": True,
        # How many trips the digital twin's own solved schedule actually used -- required for this
        # endpoint, and not a search-space guess the way tripCount is for /api/v1/solver/run.
        "tripCount": 6,
        "fabricationYards": [
            {
                "id": "FAB-01",
                "name": "Rostock",
                "latitude": 54.14,
                "longitude": 12.10,
                "operationalCalendar": "24/7",
                "capacity": 50
            }
        ],
        "marshallingYards": [
            {
                "id": "MAR-01",
                "name": "Eemshaven",
                "latitude": 53.44,
                "longitude": 6.83,
                "operationalCalendar": "24/7",
                "capacity": 20,
                "loadingRate": 2.0,
                "dischargeRate": 2.0,
                "holdingTimeDays": 5
            }
        ],
        "installationSites": [
            {
                "id": "SITE-01",
                "name": "Alpha",
                "latitude": 54.50,
                "longitude": 6.20,
                "operationalCalendar": "May-Oct",
                "capacity": 100,
                "operationalFromDay": 1,
                "operationalUntilDay": 365
            }
        ],
        "vessels": [
            {
                "id": "VESSEL-ANMOL-01",
                "name": "Anmol Express",
                "capacityWeightTons": 5500.0,
                "maxMonopiles": 4,
                "speedKnots": 14.5,
                "availableFromDay": 30,
                "compatibleGrillageTypes": ["Type-A", "Type-B"],
                "operationalCalendar": "24/7",
                "vesselClass": "TClass"
            }
        ],
        "monopiles": [
            {
                "id": "MP-ANMOL-01",
                "weightTons": 1300.0,
                "lengthM": 82.0,
                "diameterM": 8.5,
                "grillageType": "Type-A",
                "fabricationYardId": "FAB-01",
                "installationSiteId": "SITE-01",
                "fabricationCompletionDay": 20,
                "requiredInstallationSequence": 1,
                "targetInstallationDay": 90
            }
        ]
    }

    print("=== 3. Calling CW ETA Planner Itinerary Solver API ===")
    response = requests.post(f"{BASE_URL}/api/v1/itinerary/solver/run", json=input_data, timeout=60)

    if not response.ok:
        print(f"Solver call failed: {response.status_code} {response.text}")
        return

    results = response.json()

    print("\n=== 4. Solver Execution Results ===")
    print(f"Hard Feasible : {results.get('hardFeasible')}")
    print(f"Score         : {results.get('score')}")

    vessel_itineraries = results.get("vesselItineraries", [])
    print(f"Vessels: {len(vessel_itineraries)}")
    for vessel in vessel_itineraries:
        print(f"  {vessel['vesselId']} ({vessel['vesselName']}): {vessel['voyages']}")

    cargo_schedule = results.get("cargoSchedule", [])
    print(f"Cargo: {len(cargo_schedule)}")
    for cargo in cargo_schedule:
        print(f"  {cargo}")

    print("\n=== 5. Downloading PDF Schedule Report ===")
    try:
        itinerary_client = CWEtaPlannerClient(base_url=BASE_URL, base_path="/api/v1/itinerary")
        pdf_bytes = itinerary_client.download_report_pdf(output_filename="anmol_test_itinerary_report.pdf")
        if pdf_bytes:
            print("Successfully downloaded report as anmol_test_itinerary_report.pdf")
        else:
            print("PDF report not available (404).")
    except Exception as e:
        print(f"Could not download PDF report: {e}")


if __name__ == "__main__":
    main()
