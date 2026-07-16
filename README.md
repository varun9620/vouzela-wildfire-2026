# Vouzela Wildfire (Portugal, 2–3 July 2026) — Satellite Monitoring Project

This repository tracks and analyzes the **Vouzela wildfire**, which broke out in the early hours of **2 July 2026** in Tourelhe (Cambra parish, Vouzela municipality, Viseu district), and spread to Oliveira de Frades, Tondela, and Águeda. It is scoped tightly to the **2–3 July 2026 window**: ignition day through the day the smoke plume was captured from orbit.

## Event summary

- **Ignition:** early hours of 2 July 2026, Tourelhe, Vouzela (Viseu district), Portugal
- **Response:** more than 1,100 firefighters deployed at Vouzela; other fires reported the same period in Barcelos, Cinfães, and Castelo de Paiva
- **Satellite observation:** a Copernicus **Sentinel-3** satellite imaged the fire on **3 July 2026 at 10:38 UTC**, capturing a smoke plume drifting westward over the Atlantic Ocean, extending approximately **620 km**
- **Source:** [Copernicus / EU Space Support Office — "Portugal wildfires send smoke over the Atlantic Ocean"](https://eu-space.europa.eu/components/earth-observation-copernicus/image-of-the-day/portugal-wildfires-send-smoke-over-atlantic-ocean); [Euronews coverage](https://www.euronews.com/2026/07/03/portugal-over-1000-firefighters-battle-wildfires-on-the-ground)

## What's in this repo

```
vouzela-wildfire-2026/
├── README.md
├── requirements.txt
├── .env.example              # template for CDSE credentials (never commit real ones)
├── .gitignore
├── LICENSE
├── scripts/
│   └── download_tropomi.py   # pulls Sentinel-5P TROPOMI trace-gas data for 2–3 July 2026
├── notebooks/
│   └── analysis.ipynb        # prints + plots for all 6 species, 2 July vs 3 July
├── data/                     # downloaded .nc files land here (git-ignored)
├── .github/workflows/
│   └── download-tropomi.yml  # run the download as a GitHub Action
└── docs/
    └── event_notes.md        # timeline & source notes
```

## Data sources

| Layer | Instrument | Purpose |
|---|---|---|
| True-colour / smoke plume imagery | Sentinel-3 OLCI/SLSTR | Visual confirmation of plume extent (620 km, 3 July 10:38 UTC) |
| Trace-gas columns (CO, NO₂, SO₂, HCHO, CH₄, O₃) | Sentinel-5P TROPOMI | Quantify combustion products in the plume |
| Active fire hotspots | NASA FIRMS (VIIRS/MODIS) | Ground-truth fire locations for source attribution |

This repo's script pulls the TROPOMI layer via the [Copernicus Data Space Ecosystem (CDSE)](https://dataspace.copernicus.eu) OData API.

## Setup

```bash
git clone <your-repo-url>
cd vouzela-wildfire-2026
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your own CDSE credentials
```

Register a free CDSE account at https://dataspace.copernicus.eu if you don't have one.

**Never commit `.env` or real credentials.** `.gitignore` already excludes it.

## Downloading the data

### Option A — locally
```bash
python scripts/download_tropomi.py
```

This fetches all Sentinel-5P L2 products (CO, NO₂, SO₂, HCHO, CH₄, O₃) over the Iberian Peninsula bounding box, restricted to **2–3 July 2026** — the ignition day and the day the plume image was acquired. Files land in `data/<SPECIES>/`, with a `manifest.json` per species. Already-downloaded files are skipped automatically on rerun; failed downloads retry with backoff on 429/5xx.

### Option B — GitHub Actions (runs in the cloud, no local setup)

This repo includes `.github/workflows/download-tropomi.yml`, which runs the same script on GitHub's servers and saves the results as a downloadable **workflow artifact**.

**One-time setup:**
1. In your repo on GitHub, go to **Settings → Secrets and variables → Actions → New repository secret**.
2. Add two secrets:
   - `CDSE_EMAIL` — your Copernicus Data Space Ecosystem email
   - `CDSE_PASSWORD` — your Copernicus Data Space Ecosystem password
   (These are encrypted by GitHub and never appear in logs or code.)

**To run it:**
1. Go to the **Actions** tab in your repo.
2. Select **"Download TROPOMI Data (Vouzela Wildfire, 2-3 July 2026)"** in the left sidebar.
3. Click **Run workflow** → **Run workflow** (green button).
4. Wait for it to finish (progress shown live in the run log).
5. Once it's done, open the completed run and download the **`tropomi-data-2026-07-02-03`** artifact (zip) from the bottom of the run summary page — that's your `data/` folder.

Artifacts are kept for 14 days by default (configurable in the workflow file) and don't get committed to the repo, so your git history stays clean of large binary `.nc` files.

## Analysis notebook

`notebooks/analysis.ipynb` covers all six species (CO, NO₂, SO₂, HCHO, CH₄, O₃) for **2 July** (ignition) and **3 July** (plume-image day):

- Prints per-species, per-day summary stats (valid pixel count, mean, max, min after QA filtering)
- Plots a side-by-side map for each species (2 July vs 3 July), with Vouzela marked
- Builds a combined summary table (`pandas.DataFrame`) showing % change in mean column between the two days
- One combined 2×3 overview figure of all species on 3 July
- Optional overlay of NASA FIRMS active-fire hotspots, if you supply `data/firms_hotspots.csv` (download from https://firms.modaps.eosdis.nasa.gov/download/)

Run it after populating `data/` (via the script or the GitHub Action artifact):

```bash
jupyter notebook notebooks/analysis.ipynb
# or, to regenerate outputs from the command line:
jupyter nbconvert --to notebook --execute --inplace notebooks/analysis.ipynb
```

If `data/` is empty, the notebook still runs end-to-end and prints `no data yet` for anything missing, instead of erroring — so you can commit/preview it before the download finishes.

### Further ideas
- Reproject onto a westward transect over the Atlantic to trace the full 620 km plume documented by Sentinel-3
- Animate the plume's westward drift across successive orbit passes

## License

Code in this repository is MIT licensed (see `LICENSE`). Satellite imagery and data remain subject to the [Copernicus data licence](https://dataspace.copernicus.eu/terms-and-conditions).
