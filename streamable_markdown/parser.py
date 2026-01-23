import pandas as pd
from io import StringIO

def parse_text_to_dataframe(text: str) -> pd.DataFrame:
    lines = text.strip().splitlines()

    # ---- Parse metadata ----
    meta = {}
    data_start = 0

    for i, line in enumerate(lines):
        if line.strip() == "":
            data_start = i + 1
            break
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()

    # ---- Extract CSV payload ----
    csv_payload = "\n".join(lines[data_start:])

    # ---- Load DataFrame ----
    df = pd.read_csv(StringIO(csv_payload))

    # ---- Apply dtypes if provided ----
    if "dtypes" in meta:
        dtype_map = {}
        for part in meta["dtypes"].split(","):
            col, typ = part.split("=")
            dtype_map[col.strip()] = typ.strip()

        df = df.astype(dtype_map)

    return df
