"""Run the dNBR burn severity workflow on the files in the data folder."""

import os

import f_fire

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

f_fire.PRE = {   # 7 July 2026
    "B8A": os.path.join(DATA_DIR, "B8Apre.tif"),
    "B12": os.path.join(DATA_DIR, "B12pre.tif"),
    "SCL": os.path.join(DATA_DIR, "SCLpre.tif"),
}
f_fire.POST = {  # 3 August 2026
    "B8A": os.path.join(DATA_DIR, "B8Apost.tif"),
    "B12": os.path.join(DATA_DIR, "B12post.tif"),
    "SCL": os.path.join(DATA_DIR, "SCLpost.tif"),
}
f_fire.OUT_DIR = os.path.join(BASE_DIR, "dnbr_output")

if __name__ == "__main__":
    f_fire.main()
