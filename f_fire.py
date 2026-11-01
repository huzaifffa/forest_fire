"""
Burn severity mapping (dNBR) from Sentinel-2 L2A
------------------------------------------------
Inputs : pre-fire and post-fire B8A, B12, SCL (20 m) - .jp2 or .tif
Outputs: NBR_pre.tif, NBR_post.tif, dNBR.tif, dNBR_severity.tif,
         severity_stats.csv, burn_severity_map.png

Install:  pip install rasterio numpy matplotlib
          pip install geopandas        (only if you use an AOI file)
"""

import os
import csv
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.mask import mask as rio_mask
from rasterio.features import geometry_mask
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch

# =====================================================================
# 1. INPUTS - change these paths to your files
# =====================================================================
PRE = {   # 7 July 2026
    "B8A": r"C:\data\pre\T10TxX_20260707_B8A_20m.jp2",
    "B12": r"C:\data\pre\T10TxX_20260707_B12_20m.jp2",
    "SCL": r"C:\data\pre\T10TxX_20260707_SCL_20m.jp2",
}
POST = {  # 3 August 2026
    "B8A": r"C:\data\post\T10TxX_20260803_B8A_20m.jp2",
    "B12": r"C:\data\post\T10TxX_20260803_B12_20m.jp2",
    "SCL": r"C:\data\post\T10TxX_20260803_SCL_20m.jp2",
}

# Optional: fire perimeter / study area (.shp, .geojson, .gpkg).
# Set to None to process the whole tile.
AOI = None

OUT_DIR = "dnbr_output"

# L2A offset: data processed since Jan 2022 has +1000 added to every value
OFFSET = 1000

# SCL classes kept as valid: 2 = dark area (fresh burn scars often land here),
# 4 = vegetation, 5 = not vegetated. Clouds, shadows, water, snow are dropped.
VALID_SCL = [2, 4, 5]

# USGS (Key & Benson) dNBR severity classes
BINS = [-0.25, -0.10, 0.10, 0.27, 0.44, 0.66]
CLASSES = {
    1: ("High post-fire regrowth",   "#7a8737"),
    2: ("Low post-fire regrowth",    "#acbe4d"),
    3: ("Unburned",                  "#0ae042"),
    4: ("Low severity",              "#fff70b"),
    5: ("Moderate-low severity",     "#ffaf38"),
    6: ("Moderate-high severity",    "#ff641b"),
    7: ("High severity",             "#a41fd6"),
}


# =====================================================================
# 2. FUNCTIONS
# =====================================================================
def reference_grid(path, aoi=None):
    """Grid of the pre-fire B8A (cropped to the AOI if given). All bands are aligned to it."""
    with rasterio.open(path) as src:
        crs = src.crs
        aoi_shapes = None
        if aoi:
            import geopandas as gpd
            aoi_shapes = list(gpd.read_file(aoi).to_crs(crs).geometry)
            data, transform = rio_mask(src, aoi_shapes, crop=True)
            height, width = data.shape[1:]
        else:
            transform, height, width = src.transform, src.height, src.width

    profile = {
        "driver": "GTiff", "dtype": "float32", "count": 1,
        "height": height, "width": width, "transform": transform,
        "crs": crs, "nodata": np.nan, "compress": "deflate",
    }
    inside = np.ones((height, width), dtype=bool)
    if aoi_shapes:
        inside = geometry_mask(aoi_shapes, out_shape=(height, width),
                               transform=transform, invert=True)
    return profile, inside


def load(path, ref):
    """Read a band onto the reference grid (exact copy when it's the same tile)."""
    out = np.zeros((ref["height"], ref["width"]), dtype=np.float32)
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1), destination=out,
            src_transform=src.transform, src_crs=src.crs,
            dst_transform=ref["transform"], dst_crs=ref["crs"],
            src_nodata=0, dst_nodata=0, resampling=Resampling.nearest,
        )
    return out


def calc_nbr(bands, ref, inside):
    b8a = load(bands["B8A"], ref)
    b12 = load(bands["B12"], ref)
    scl = load(bands["SCL"], ref)

    nir = b8a - OFFSET
    swir = b12 - OFFSET
    with np.errstate(divide="ignore", invalid="ignore"):
        nbr = (nir - swir) / (nir + swir)

    valid = (np.isin(scl, VALID_SCL) & (b8a > 0) & (b12 > 0)
             & ((nir + swir) != 0) & inside)
    nbr[~valid] = np.nan
    return nbr.astype(np.float32)


def save(array, name, profile, dtype="float32", nodata=np.nan):
    p = profile.copy()
    p.update(dtype=dtype, nodata=nodata)
    path = os.path.join(OUT_DIR, name)
    with rasterio.open(path, "w", **p) as dst:
        dst.write(array.astype(dtype), 1)
    print(f"  saved {path}")


# =====================================================================
# 3. RUN
# =====================================================================
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Preparing grid...")
    ref, inside = reference_grid(PRE["B8A"], AOI)

    print("Calculating NBR...")
    nbr_pre = calc_nbr(PRE, ref, inside)
    nbr_post = calc_nbr(POST, ref, inside)

    dnbr = nbr_pre - nbr_post            # NaN wherever either date is cloudy/invalid

    severity = (np.digitize(dnbr, BINS) + 1).astype(np.uint8)
    severity[np.isnan(dnbr)] = 0         # 0 = no data

    print("Saving rasters...")
    save(nbr_pre, "NBR_pre.tif", ref)
    save(nbr_post, "NBR_post.tif", ref)
    save(dnbr, "dNBR.tif", ref)
    save(severity, "dNBR_severity.tif", ref, dtype="uint8", nodata=0)

    # ---- area statistics ----
    pixel_ha = abs(ref["transform"].a * ref["transform"].e) / 10_000
    valid_px = int((severity > 0).sum())
    rows = []
    print("\nBurn severity summary")
    print(f"{'Class':<26}{'Hectares':>12}{'Acres':>12}{'%':>8}")
    for code, (label, _) in CLASSES.items():
        n = int((severity == code).sum())
        ha = n * pixel_ha
        pct = 100 * n / valid_px if valid_px else 0
        rows.append([code, label, n, round(ha, 2), round(ha * 2.47105, 2), round(pct, 2)])
        print(f"{label:<26}{ha:>12,.1f}{ha * 2.47105:>12,.1f}{pct:>8.2f}")

    burned_ha = sum(r[3] for r in rows if r[0] >= 4)
    print(f"\nTotal burned (low to high severity): {burned_ha:,.1f} ha "
          f"= {burned_ha * 2.47105:,.0f} acres")
    cloudy_pct = 100 * (1 - valid_px / max(int(inside.sum()), 1))
    print(f"Pixels masked (cloud/shadow/water/no data): {cloudy_pct:.1f}%")

    with open(os.path.join(OUT_DIR, "severity_stats.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "class", "pixels", "hectares", "acres", "percent"])
        w.writerows(rows)
        w.writerow([])
        w.writerow(["", "Total burned (classes 4-7)", "", round(burned_ha, 2),
                    round(burned_ha * 2.47105, 2), ""])

    # ---- map ----
    fig, ax = plt.subplots(1, 3, figsize=(18, 6))
    for a, arr, title in [(ax[0], nbr_pre, "NBR pre-fire (7 Jul 2026)"),
                          (ax[1], nbr_post, "NBR post-fire (3 Aug 2026)")]:
        im = a.imshow(arr, cmap="RdYlGn", vmin=-0.5, vmax=0.8)
        a.set_title(title)
        a.axis("off")
        fig.colorbar(im, ax=a, fraction=0.046)

    cmap = ListedColormap([c for _, c in CLASSES.values()])
    norm = BoundaryNorm(np.arange(0.5, 8.5), cmap.N)
    sev_plot = np.ma.masked_equal(severity, 0)
    ax[2].imshow(sev_plot, cmap=cmap, norm=norm, interpolation="nearest")
    ax[2].set_title("dNBR burn severity")
    ax[2].axis("off")
    ax[2].legend(handles=[Patch(color=c, label=l) for l, c in CLASSES.values()],
                 loc="lower left", fontsize=8, framealpha=0.9)

    plt.tight_layout()
    png = os.path.join(OUT_DIR, "burn_severity_map.png")
    plt.savefig(png, dpi=200)
    print(f"  saved {png}\nDone.")


if __name__ == "__main__":
    main()