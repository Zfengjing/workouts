import argparse
import json
import os
import sys
import time

from geopy.geocoders import Nominatim

from config import JSON_FILE, SQL_FILE
from generator import Generator


def fix_location_country():
    geolocator = Nominatim(user_agent="workout_dashboard")
    file_path = JSON_FILE

    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found, skip fix.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        activities = json.load(f)

    fixed = 0
    for act in activities:
        if act.get("location_country"):
            continue
        latlng = act.get("start_latlng")
        if not latlng or len(latlng) != 2 or latlng[0] is None:
            continue

        try:
            location = geolocator.reverse(f"{latlng[0]}, {latlng[1]}", language="zh")
            address = location.raw.get("address", {})
            province = (
                address.get("province")
                or address.get("state")
                or address.get("city")
                or ""
            )
            if province:
                act["location_country"] = province
                fixed += 1
                time.sleep(0.1)
        except Exception as e:
            print(f"Failed to reverse geocode {latlng}: {e}")
            continue

    if fixed > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(activities, f, ensure_ascii=False, indent=0)
        print(f"Fixed location_country for {fixed} activities.")
    else:
        print("No missing location_country to fix.")


def run_strava_sync_recent(
    client_id, client_secret, refresh_token, days=7, only_run=False
):
    generator = Generator(SQL_FILE)
    generator.set_strava_config(client_id, client_secret, refresh_token)
    generator.only_run = only_run
    generator.sync_recent(days=days)

    activities_list = generator.loadForMapping()
    with open(JSON_FILE, "w") as f:
        json.dump(activities_list, f, indent=0)

    print("Fixing location_country for activities with missing province...")
    fix_location_country()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sync recent Strava activities (default: last 7 days). "
        "Credentials can be provided via env vars: "
        "STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN."
    )
    parser.add_argument(
        "client_id", nargs="?", help="Strava client ID (or set STRAVA_CLIENT_ID)"
    )
    parser.add_argument(
        "client_secret",
        nargs="?",
        help="Strava client secret (or set STRAVA_CLIENT_SECRET)",
    )
    parser.add_argument(
        "refresh_token",
        nargs="?",
        help="Strava refresh token (or set STRAVA_REFRESH_TOKEN)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.getenv("STRAVA_SYNC_DAYS", "7")),
        help="number of days to look back (default: 7, or set STRAVA_SYNC_DAYS)",
    )
    parser.add_argument(
        "--only-run",
        dest="only_run",
        action="store_true",
        default=os.getenv("STRAVA_ONLY_RUN", "").lower() in ("1", "true", "yes"),
        help="only sync running activities (or set STRAVA_ONLY_RUN=true)",
    )
    options = parser.parse_args()

    client_id = options.client_id or os.getenv("STRAVA_CLIENT_ID")
    client_secret = options.client_secret or os.getenv("STRAVA_CLIENT_SECRET")
    refresh_token = options.refresh_token or os.getenv("STRAVA_REFRESH_TOKEN")

    missing = [
        name
        for name, val in [
            ("client_id / STRAVA_CLIENT_ID", client_id),
            ("client_secret / STRAVA_CLIENT_SECRET", client_secret),
            ("refresh_token / STRAVA_REFRESH_TOKEN", refresh_token),
        ]
        if not val
    ]

    if missing:
        parser.error("Missing required credentials: " + ", ".join(missing))
        sys.exit(1)

    run_strava_sync_recent(
        client_id,
        client_secret,
        refresh_token,
        days=options.days,
        only_run=options.only_run,
    )
