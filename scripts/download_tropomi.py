"""
TROPOMI Download Script — Vouzela Wildfire (Portugal), 2-3 July 2026
======================================================================
Scoped to the event day only:
  - 2 July 2026: fire ignition near Vouzela
  - 3 July 2026: Sentinel-3 image of the ~620 km smoke plume (10:38 UTC)

PARALLEL, with auto-retry on rate limiting (429 errors).

Credentials are read from environment variables (or a local .env file via
python-dotenv) — NEVER hardcode credentials in this file or commit them.

Setup:
  1. cp .env.example .env
  2. edit .env with your own CDSE username/password
  3. pip install -r requirements.txt
  4. python scripts/download_tropomi.py

Register a CDSE account at: https://dataspace.copernicus.eu
"""

import requests
import os
import json
import sys
import time
from tqdm import tqdm
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional; env vars can be set directly instead

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
EMAIL    = os.environ.get("CDSE_EMAIL")
PASSWORD = os.environ.get("CDSE_PASSWORD")

if not EMAIL or not PASSWORD:
    sys.exit(
        "Missing credentials. Set CDSE_EMAIL and CDSE_PASSWORD as environment "
        "variables (or copy .env.example to .env and fill it in).\n"
        "Register a free account at https://dataspace.copernicus.eu"
    )

# Event window: ignition (2 July) through plume-image acquisition (3 July) 2026.
START_DATE = "2026-07-02"
END_DATE   = "2026-07-04"  # exclusive upper bound catches all of 3 July UTC

# Bounding box around Iberia / eastern Atlantic, wide enough to capture the
# ~620 km westward plume documented by Sentinel-3 on 3 July.
REGION = "-20,35,-5,45"

N_WORKERS   = 6    # safe for CDSE — do not exceed 8
MAX_RETRIES = 5    # retry up to 5 times on 429/5xx
RETRY_WAIT  = 30   # seconds, before each retry

PRODUCTS = {
    "CO"   : ("L2__CO____",  "Carbon Monoxide — primary wildfire tracer"),
    "NO2"  : ("L2__NO2___",  "Nitrogen Dioxide — combustion indicator"),
    "SO2"  : ("L2__SO2___",  "Sulphur Dioxide — fire/industrial marker"),
    "HCHO" : ("L2__HCHO__",  "Formaldehyde — VOC biomass burning product"),
    "CH4"  : ("L2__CH4___",  "Methane — greenhouse gas, elevated in fire plumes"),
    "O3"   : ("L2__O3____",  "Ozone — secondary pollutant, enhanced downwind"),
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
TOKEN_URL  = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

# ── TOKEN MANAGER (thread-safe) ───────────────────────────────────────────────
class TokenManager:
    def __init__(self, email, password):
        self.email         = email
        self.password      = password
        self.access_token  = None
        self.refresh_token = None
        self.expires_at    = datetime.min
        self._lock         = Lock()
        self._fetch_new_token()

    def _fetch_new_token(self):
        resp = requests.post(TOKEN_URL, data={
            "client_id" : "cdse-public",
            "grant_type": "password",
            "username"  : self.email,
            "password"  : self.password,
        })
        resp.raise_for_status()
        data = resp.json()
        self.access_token  = data["access_token"]
        self.refresh_token = data.get("refresh_token")
        self.expires_at    = datetime.now() + timedelta(seconds=data.get("expires_in", 600) - 60)
        print(f"  Token obtained (valid until {self.expires_at.strftime('%H:%M:%S')})")

    def _refresh(self):
        try:
            resp = requests.post(TOKEN_URL, data={
                "client_id"    : "cdse-public",
                "grant_type"   : "refresh_token",
                "refresh_token": self.refresh_token,
            })
            resp.raise_for_status()
            data = resp.json()
            self.access_token  = data["access_token"]
            self.refresh_token = data.get("refresh_token", self.refresh_token)
            self.expires_at    = datetime.now() + timedelta(seconds=data.get("expires_in", 600) - 60)
            print(f"\n  Token refreshed (valid until {self.expires_at.strftime('%H:%M:%S')})")
        except Exception:
            print("\n  Refresh failed — re-authenticating...")
            self._fetch_new_token()

    @property
    def token(self):
        with self._lock:
            if datetime.now() >= self.expires_at:
                self._refresh()
            return self.access_token

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}


# ── SEARCH ────────────────────────────────────────────────────────────────────
def search_products(tm, product_type, start_date, end_date, region):
    base_url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    w, s, e, n = region.split(",")
    polygon = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"

    filter_str = (
        f"Collection/Name eq 'SENTINEL-5P' and "
        f"Attributes/OData.CSC.StringAttribute/any("
        f"att:att/Name eq 'productType' and "
        f"att/OData.CSC.StringAttribute/Value eq '{product_type}') and "
        f"ContentDate/Start gt {start_date}T00:00:00.000Z and "
        f"ContentDate/Start lt {end_date}T00:00:00.000Z and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}')"
    )

    all_products = []
    url  = f"{base_url}?$filter={filter_str}&$orderby=ContentDate/Start&$top=100&$skip=0"
    page = 1

    while url:
        resp = requests.get(url, headers=tm.headers)
        resp.raise_for_status()
        data  = resp.json()
        batch = data.get("value", [])
        all_products.extend(batch)
        print(f"    Page {page}: {len(batch)} products (total: {len(all_products)})")
        url  = data.get("@odata.nextLink")
        page += 1

    return all_products


# ── SINGLE FILE DOWNLOAD WITH RETRY ──────────────────────────────────────────
def download_one(args):
    """
    Download one file with automatic retry on 429 (rate limit) or 5xx errors.
    Uses manual redirect handling to avoid token-stripping 401 bug.
    """
    tm, pid, pname, fpath = args

    if os.path.exists(fpath):
        return (pname, "skipped")

    catalogue_url = (
        f"https://catalogue.dataspace.copernicus.eu"
        f"/odata/v1/Products({pid})/$value"
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            session = requests.Session()
            session.headers.update(tm.headers)

            resp = session.get(catalogue_url, allow_redirects=False)
            redirect_url = None
            while resp.status_code in (301, 302, 303, 307, 308):
                redirect_url = resp.headers["Location"]
                resp = session.get(redirect_url, headers=tm.headers, allow_redirects=False)

            final_url = resp.url if resp.status_code == 200 else redirect_url
            resp = session.get(final_url, headers=tm.headers, stream=True)

            if resp.status_code == 429:
                wait = RETRY_WAIT * attempt
                tqdm.write(f"\n  429 rate limit — waiting {wait}s before retry "
                           f"(attempt {attempt}/{MAX_RETRIES}): {pname[-40:]}")
                time.sleep(wait)
                continue

            resp.raise_for_status()

            tmp_path = fpath + ".part"
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
            os.rename(tmp_path, fpath)
            return (pname, "ok")

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code in (500, 502, 503, 504):
                wait = RETRY_WAIT * attempt
                tqdm.write(f"\n  Server error {e.response.status_code} — "
                           f"waiting {wait}s (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            else:
                if os.path.exists(fpath + ".part"):
                    os.remove(fpath + ".part")
                return (pname, f"error: {e}")

        except Exception as e:
            if os.path.exists(fpath + ".part"):
                os.remove(fpath + ".part")
            if attempt < MAX_RETRIES:
                tqdm.write(f"\n  Error (attempt {attempt}/{MAX_RETRIES}): {e} — retrying...")
                time.sleep(RETRY_WAIT)
                continue
            return (pname, f"error: max retries exceeded ({e})")

    return (pname, f"error: max retries ({MAX_RETRIES}) exceeded")


# ── PARALLEL DOWNLOAD ─────────────────────────────────────────────────────────
def download_all_parallel(tm, products, species_dir, n_workers):
    args_list = [
        (tm, p["Id"], p["Name"], os.path.join(species_dir, p["Name"] + ".nc"))
        for p in products
    ]

    downloaded = skipped = errors = 0
    error_list = []

    with tqdm(total=len(args_list), unit="file", ncols=80, desc="  Progress") as pbar:
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(download_one, a): a for a in args_list}
            for future in as_completed(futures):
                pname, status = future.result()
                if status == "ok":
                    downloaded += 1
                    pbar.set_postfix_str(f"OK {pname[-30:]}")
                elif status == "skipped":
                    skipped += 1
                else:
                    errors += 1
                    error_list.append((pname, status))
                    pbar.set_postfix_str(f"ERR {pname[-30:]}")
                pbar.update(1)

    if error_list:
        print(f"\n  Still failed after {MAX_RETRIES} retries ({len(error_list)} files):")
        for name, err in error_list:
            print(f"    {name[-55:]}: {err}")

    return downloaded, skipped, errors


# ── SAVE MANIFEST ─────────────────────────────────────────────────────────────
def save_manifest(species_dir, products):
    manifest = [{
        "id"        : p["Id"],
        "name"      : p["Name"],
        "date"      : p.get("ContentDate", {}).get("Start", ""),
        "size_bytes": p.get("ContentLength", 0),
    } for p in products]
    path = os.path.join(species_dir, "manifest.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  TROPOMI Download — Vouzela Wildfire (Portugal), 2-3 July 2026")
    print(f"  Workers: {N_WORKERS}  |  Max retries: {MAX_RETRIES}  |  Retry wait: {RETRY_WAIT}s")
    print("=" * 65)
    print(f"  Period  : {START_DATE} to {END_DATE} (exclusive)")
    print(f"  Region  : {REGION}  (Iberia + eastern Atlantic, for plume tracking)")
    print(f"  Species : {', '.join(PRODUCTS.keys())}")
    print(f"  Output  : {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 65)

    print("\nAuthenticating...")
    tm = TokenManager(EMAIL, PASSWORD)

    summary   = {}
    run_start = time.time()

    for species, (product_type, description) in PRODUCTS.items():
        print(f"\n{'-'*65}")
        print(f"  {species}  —  {description}")
        print(f"{'-'*65}")

        species_dir = os.path.join(OUTPUT_DIR, species)
        os.makedirs(species_dir, exist_ok=True)

        print("  Searching catalogue...")
        products = search_products(tm, product_type, START_DATE, END_DATE, REGION)
        print(f"  -> Found {len(products)} orbit files")
        save_manifest(species_dir, products)

        already = sum(
            1 for p in products
            if os.path.exists(os.path.join(species_dir, p["Name"] + ".nc"))
        )
        if already:
            print(f"  -> {already} already downloaded, will skip")

        t0 = time.time()
        downloaded, skipped, errors = download_all_parallel(tm, products, species_dir, N_WORKERS)
        elapsed = time.time() - t0

        summary[species] = {
            "total"     : len(products),
            "downloaded": downloaded,
            "skipped"   : skipped,
            "errors"    : errors,
            "time_min"  : elapsed / 60,
        }
        print(f"\n  {species} done in {elapsed/60:.1f} min: "
              f"{downloaded} downloaded, {skipped} skipped, {errors} errors")

    total_elapsed = time.time() - run_start
    print(f"\n{'='*65}")
    print("  DOWNLOAD SUMMARY")
    print(f"{'='*65}")
    total_files = 0
    for sp, s in summary.items():
        print(f"  {sp:5s}: {s['total']:4d} found | {s['downloaded']:4d} dl | "
              f"{s['skipped']:4d} skip | {s['errors']:2d} err | {s['time_min']:.1f} min")
        total_files += s["downloaded"]
    print(f"{'-'*65}")
    print(f"  Total downloaded : {total_files} files")
    print(f"  Total time       : {total_elapsed/60:.1f} minutes")
    print(f"  Output directory : {os.path.abspath(OUTPUT_DIR)}")
    print(f"{'='*65}")
    print("\n  Next steps:")
    print("  1. import xarray as xr; ds = xr.open_dataset('file.nc', group='PRODUCT')")
    print("  2. CO variable  : 'carbonmonoxide_total_column'")
    print("  3. NO2 variable : 'nitrogendioxide_tropospheric_column'")
    print("  4. Always filter: ds.where(ds.qa_value >= 0.75)")
    print("  5. Overlay NASA FIRMS VIIRS fire hotspots for source attribution")


if __name__ == "__main__":
    main()
