# Vouzela Wildfire (Portugal, 2–3 July 2026) — Satellite Monitoring Project

This repository tracks and analyzes the **Vouzela wildfire**, which broke out in the early hours of **2 July 2026** in Tourelhe (Cambra parish, Vouzela municipality, Viseu district), and spread to Oliveira de Frades, Tondela, and Águeda. It is scoped tightly to the **2–3 July 2026 window**: ignition day through the day the smoke plume was captured from orbit.

## Event summary

- **Ignition:** early hours of 2 July 2026, Tourelhe, Vouzela (Viseu district), Portugal
- **Response:** more than 1,100 firefighters deployed at Vouzela; other fires reported the same period in Barcelos, Cinfães, and Castelo de Paiva
- **Satellite observation:** a Copernicus **Sentinel-3** satellite imaged the fire on **3 July 2026 at 10:38 UTC**, capturing a smoke plume drifting westward over the Atlantic Ocean, extending approximately **620 km**
- **Source:** [Copernicus / EU Space Support Office — "Portugal wildfires send smoke over the Atlantic Ocean"](https://eu-space.europa.eu/components/earth-observation-copernicus/image-of-the-day/portugal-wildfires-send-smoke-over-atlantic-ocean); [Euronews coverage](https://www.euronews.com/2026/07/03/portugal-over-1000-firefighters-battle-wildfires-on-the-ground)

---

## ⚠️ Data status — check before interpreting any output

**The notebook config is correct. The data files on disk may not be yet.**

`notebooks/analysis.ipynb` has been corrected: `EVENT_DATES` in the config cell is now
`2026-07-02` / `2026-07-03`, matching the actual event. The notebook is date-agnostic
downstream of that cell — everything follows from `EVENT_DATES`/`DATE_KEYS` — so no other
code changes are needed.

**What still needs checking is `data/` itself.** An earlier working set had every granule
carrying a **June** sensing date, one month before the fire:

```
S5P_OFFL_L2__CO_____20260602T121538_...     <- 2 Jun (wrong window)
IASI_METOPB_L2_CO_20260603_ULB-LATMOS...    <- 3 Jun (wrong window)
OMI-Aura_L3-OMNO2d_2026m0602_v004-...       <- 2 Jun (wrong window)
```

That mismatch is why an earlier run of the CO analysis showed **no plume**: the
95th-percentile CO column *fell* slightly between the two days, and the single hottest CO
pixel was on the first day rather than the second — a quiet pre-event baseline, not a
620 km smoke plume.

**Before drawing conclusions from a fresh run, confirm all four inputs actually cover
2026-07-02 / 2026-07-03:**

| Input | Where it lands | How to check |
|---|---|---|
| TROPOMI CO | `data/CO/` | filenames should contain `20260702...` / `20260703...` at the *sensing-start* field (see § 2 of the notebook — it's not a straight substring match, the processing timestamp at the end of the filename is a different date) |
| IASI CO | `data/CO/` | filenames should contain `_20260702_` / `_20260703_` |
| OMI NO₂ | `data/NO2/` | filenames should contain `2026m0702` / `2026m0703` |
| VIIRS fire (FIRMS) | `data/fire_nrt_SV-C2_*.csv` | re-download must span 2 July onward — a nearby-but-wrong window (e.g. 1–3 July when you need 2–3 July, or June data) will silently filter to zero |

The fastest single check is **§ 13, VIIRS fire counts**: if the fire is genuinely in your
data, the detection count near Vouzela jumps sharply on the ignition day (2 July). That
section also prints an explicit warning if `EVENT_DATES` isn't found in the loaded FIRMS
data at all, so it's the first thing to look at after any re-download.

---

## What's in this repo

```
vouzela-wildfire-2026/
├── README.md
├── requirements.txt
├── .env.example              # template for CDSE credentials (never commit real ones)
├── .gitignore
├── LICENSE
├── scripts/
│   └── download_tropomi.py   # pulls Sentinel-5P TROPOMI trace-gas data
├── notebooks/
│   └── analysis.ipynb        # CO + NO2 + VIIRS fire counts, day 1 vs day 2
├── data/                     # downloaded files land here (git-ignored)
│   ├── CO/                   # S5P TROPOMI .nc  +  Metop IASI .nc (not in the folder)
│   ├── NO2/                  # OMI/Aura OMNO2d .he5 (not in the folder)
│   └── fire_nrt_SV-C2_*.csv  # NASA FIRMS VIIRS active-fire export (not in the folder)
├── .github/workflows/
│   └── download-tropomi.yml  # run the download as a GitHub Action
└── docs/
    └── event_notes.md        # timeline & source notes
```

## Data sources

| Layer | Instrument / product | Level | Format | What I use it for |
|---|---|---|---|---|
| Smoke plume imagery | Sentinel-3 OLCI/SLSTR | L1/L2 | — | Visual confirmation of plume extent (620 km, 3 July 10:38 UTC) |
| CO total column | Sentinel-5P TROPOMI (`S5P_OFFL_L2__CO____`) | L2 swath | netCDF (`PRODUCT` group) | Primary combustion tracer at ~5.5 × 3.5 km |
| CO total column | Metop-B & Metop-C IASI (ULB-LATMOS FORLI) | L2 along-track | netCDF (flat) | Independent thermal-IR CO, sensitive to lofted plumes, works at night |
| NO₂ tropospheric column | OMI/Aura `OMNO2d` | L3 gridded 0.25° | HDF-EOS5 (`.he5`) | Short-lived combustion indicator, near-source |
| Active fire detections | NASA FIRMS VIIRS S-NPP + NOAA-20 (375 m) | — | CSV | Fire counts, FRP, and source attribution |

**Scope change from the first version of this project.** The original notebook tried all six
TROPOMI species (CO, NO₂, SO₂, HCHO, CH₄, O₃). I cut it back to **CO and NO₂ plus fire
counts**, because those are the three layers that actually carry signal for a single
mid-latitude wildfire. SO₂ is diagnostic for volcanic and industrial sources rather than
biomass burning, CH₄ enhancement from one fire is lost in the background column, and O₃ can
move in either direction near fresh smoke. Carrying them added noise and no evidence.

**The NO₂ files are not TROPOMI.** They are OMI Level 3 daily 0.25° grids in HDF-EOS5. The
swath/QA loading path used for TROPOMI does not apply to them, so the notebook has a
separate loader built on `h5py`.

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

### Dependencies worth calling out

- `h5netcdf` — the notebook opens the TROPOMI `PRODUCT` group with this engine. The default
  `netCDF4` engine has a bug that raises a spurious `KeyError` when opening many group
  datasets in a loop.
- `h5py` — required for the OMI `.he5` files.
- `cartopy` — maps. It needs GEOS/PROJ system libraries; conda is the least painful route.
- `scipy` — 2-D binning for the gridding step.

## Downloading the data

### Option A — locally
```bash
python scripts/download_tropomi.py
```

Fetches Sentinel-5P L2 products over the Iberian Peninsula bounding box for the configured
date window. Files land in `data/<SPECIES>/` with a `manifest.json` per species.
Already-downloaded files are skipped on rerun; failed downloads retry with backoff on
429/5xx.

**Check the dates in the returned filenames**, not just that files arrived. See the data
status section at the top of this README.

### Option B — GitHub Actions (runs in the cloud, no local setup)

`.github/workflows/download-tropomi.yml` runs the same script on GitHub's servers and saves
the results as a downloadable **workflow artifact**.

**One-time setup:**
1. In your repo on GitHub, go to **Settings → Secrets and variables → Actions → New repository secret**.
2. Add two secrets:
   - `CDSE_EMAIL` — your Copernicus Data Space Ecosystem email
   - `CDSE_PASSWORD` — your Copernicus Data Space Ecosystem password
   (These are encrypted by GitHub and never appear in logs or code.)

### The other three layers are manual

`download_tropomi.py` only covers Sentinel-5P. The rest I download by hand:

- **IASI CO** — [IASI portal / AERIS](https://iasi.aeris-data.fr/), product
  `IASI_METOP{B,C}_L2_CO_<YYYYMMDD>_ULB-LATMOS_*.nc`. Drop into `data/CO/` alongside the
  S5P files; the notebook separates the two by filename.
- **OMI NO₂** — [GES DISC `OMNO2d`](https://disc.gsfc.nasa.gov/datasets/OMNO2d_003/summary),
  daily `.he5`. Needs a free Earthdata login. Drop into `data/NO2/`.
- **VIIRS fire** — [FIRMS download](https://firms.modaps.eosdis.nasa.gov/download/), choose
  **VIIRS S-NPP + NOAA-20 375 m**, area Portugal, and a date range a few days wider than the
  event (e.g. 2026-06-29 to 2026-07-06) so there's a before/after baseline. Drop the CSV
  into `data/`.

## Analysis notebook

`notebooks/analysis.ipynb`, 16 sections:

The first cell holds the config: paths, event dates, region box, and per-product metadata.
`EVENT_DATES` is currently set to `2026-07-02` (ignition) and `2026-07-03` (plume day).
Everything else is numbered:

| § | What it does |
|---|---|
| 1 | Helper functions adapted from the EUMETSAT FANGS training material |
| 2 | **File inventory** — parses the *sensing* date out of each filename by regex |
| 3 | TROPOMI CO loader (QA filter, geographic subset, unit conversion) |
| 4 | IASI CO loader (quality-flag filter, Metop-B + Metop-C combined) |
| 5 | OMI NO₂ loader (HDF-EOS5, calibration attributes, coordinate reconstruction) |
| 6 | VIIRS FIRMS loader (confidence filter, region clip, per-day totals) |
| 7 | Loads everything into a `results[product][date]` structure |
| 8 | Summary statistics table, day 1 vs day 2 |
| 9 | **Gridding** — bins each day onto one regular grid, resolution chosen from the data |
| 10 | Maps of all three products, no-data cells drawn in grey |
| 11 | **Day-over-day difference maps** — the figure that actually shows a plume |
| 12 | **Like-for-like statistics** — change over cells observed on *both* days |
| 13 | **VIIRS fire counts** — daily detections, FRP time series, detection maps. Also the
  fastest way to confirm you have the right data window — see the data status warning above |
| 14 | Cross-check: do the fire counts line up with the gas columns? |
| 15 | CO vs NO₂ binned onto a common 0.25° grid, with correlation |
| 16 | Interpretation notes and caveats |

### Methodology choices 

**QA threshold.** I filter TROPOMI CO at `qa_value > 0.5`, which is what the CO product
documentation recommends. The stricter 0.75 that gets used for NO₂ throws away usable plume
pixels. If a thick plume seems to be missing entirely, try dropping to 0.3 — heavy smoke can
fail QA.

**Grid resolution is chosen from the data, not hard-coded.** With ~10,000 QA-passing CO
pixels over a 12° × 9° box, a 0.05° grid has 43,200 cells and comes out ~80% empty and
speckled. The notebook coarsens the grid until most cells are populated and prints the
trade-off so you can override it. If nothing reaches the target, the honest conclusion is
that the region box is too large for the amount of data — shrink the box.

**No interpolation, anywhere.** Gridding takes the mean of observations that fall in a cell.
Cells with no observations stay `NaN` and render grey. A map should not invent data.

**Fire counts are pixel counts, not fire counts.** One large fire produces many 375 m
detections. VIIRS also only sees the fire on overpass and through clear sky, so a low count
can mean "cloudy", not "out". I report summed FRP alongside the counts because they answer
different questions: count is roughly area, FRP is roughly intensity.

### Known limitations

- **Two days is not a baseline.** To claim an anomaly, pull the same fields for the
  preceding week and compare against that, not against a single prior day.
- **TROPOMI and IASI will not agree pixel-for-pixel**, and shouldn't. TROPOMI is shortwave-IR
  and most sensitive near the surface; IASI is thermal-IR with weak near-surface sensitivity
  but good free-tropospheric sensitivity. For a lofted plume IASI can show enhancement that
  TROPOMI underplays.
- **NO₂ has an hours-long lifetime** against CO's weeks, and OMNO2d dilutes a fire across
  ~625 km² cells. A weak NO₂ signal does not contradict a clear CO plume. Lisbon and Porto
  will dominate the NO₂ field regardless of the fire.
- **OMI row anomaly.** Some cross-track positions have been unusable since 2007. The L3
  product screens them out, so cells go missing for reasons unrelated to cloud.
- **Cloud drives everything.** "Fewer valid pixels" usually means "cloudier", not "less
  pollution".

## Code provenance

The loading, masking, and plotting helpers are adapted from published training material.
I've kept the original function names so they're easy to cross-reference:

- EUMETSAT FANGS — [Metop-B IASI Total Column CO L2](https://fire.trainhub.eumetsat.int/docs/figure3_Metop-B_IASI_L2_CO.html)
- EUMETSAT FANGS — [Sentinel-5P TROPOMI CO L2](https://fire.trainhub.eumetsat.int/docs/figure5_Sentinel-5P_TROPOMI_CO.html)
- EUMETSAT FANGS — [shared `functions.ipynb`](https://fire.trainhub.eumetsat.int/docs/functions.html) (© 2022 EUMETSAT, MIT licence)
- DrivenData — [How to Estimate Surface-level NO2 using OMI Column NO2 Data](https://drivendata.co/blog/predict-no2-benchmark)

Two modernisations vs. the originals: `plt.cm.get_cmap` → `plt.get_cmap` (removed in
Matplotlib ≥ 3.9), and the visualisation helpers accept an existing `ax` so days can be
drawn side by side.

IASI is a joint EUMETSAT/CNES mission; CO data production by EUMETSAT under AC SAF, retrieval
algorithm by ULB-LATMOS (FORLI), data access via AERIS. OMI data courtesy NASA GES DISC.
FIRMS data courtesy NASA Earthdata.

## License

Code in this repository is MIT licensed (see `LICENSE`). Satellite imagery and data remain subject to the [Copernicus data licence](https://dataspace.copernicus.eu/terms-and-conditions), and to the respective NASA and EUMETSAT/AERIS data policies for the OMI, VIIRS, and IASI products.
