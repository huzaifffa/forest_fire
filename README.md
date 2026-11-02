# Forest Fire Burn Severity (dNBR)

Maps burn severity and burned area from pre-fire and post-fire Sentinel-2 L2A imagery.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install rasterio numpy matplotlib
```

Install `geopandas` as well if you want to clip to a study area.

## Use it on your own fire

1. Download the B8A, B12 and SCL bands (20 m) for one date before the fire and one after it.
2. Put them in `data/` with these names. To use other names or `.jp2` files, change the paths in `run.py`.

   ```
   B8Apre.tif   B12pre.tif   SCLpre.tif
   B8Apost.tif  B12post.tif  SCLpost.tif
   ```

3. Update the dates in the map titles in `f_fire.py` (search for `NBR pre-fire` and `NBR post-fire`).
4. Run the tool:

   ```bash
   python run.py
   ```

Results are saved in `dnbr_output/`:

- `NBR_pre.tif`, `NBR_post.tif`, `dNBR.tif`: index rasters
- `dNBR_severity.tif`: severity classes
- `severity_stats.csv`: area per class
- `burn_severity_map.png`: map

## Options

- **Study area:** add `f_fire.AOI = "path/to/perimeter.geojson"` to `run.py`, before the `if __name__` line. Without a perimeter, the whole image is processed, and non-fire vegetation change such as crop harvest can count as burned.
- **Older imagery:** set `OFFSET = 0` in `f_fire.py` for data processed before January 2022.
- **Masking and classes:** change `VALID_SCL`, `BINS` and `CLASSES` in `f_fire.py`.
