"""Regenerate a smooth illustrative reference; this is not a physical prediction."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d, median_filter

SOURCE_SHA256 = "7325935683d8380681a804c338b8fe8ebbe1539d5dc3211cc55743303c038e8f"
ESTIMATED_N_PER_RAW = 0.49
SYNTHETIC_CLOCK_SHIFT_S = 2.0


def main() -> None:
    folder = Path(__file__).resolve().parent
    source = folder / "TEST_SD(1).TXT"
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("The original record does not match the documented SHA-256")
    data = np.loadtxt(source, delimiter=",")
    if data.shape != (18180, 2) or not np.all(np.isfinite(data)):
        raise ValueError("Expected the original finite two-column record")
    if not np.all(np.diff(data[:, 0]) > 0):
        raise ValueError("Expected increasing original timestamps")
    # Filter only a new synthetic array. The original file and samples are never rewritten.
    smooth_raw = gaussian_filter1d(
        median_filter(data[:, 1], size=31, mode="nearest"), sigma=20, mode="nearest"
    )
    reference = np.column_stack(
        (data[:, 0] + SYNTHETIC_CLOCK_SHIFT_S, smooth_raw * ESTIMATED_N_PER_RAW)
    )
    # Fix CRLF explicitly so the published SHA-256 is reproducible across operating systems.
    with (folder / "synthetic_smooth_reference.csv").open(
        "w", encoding="utf-8", newline=""
    ) as output:
        np.savetxt(
            output,
            reference,
            delimiter=",",
            header="Time (s),Synthetic reference estimate (N)",
            comments="",
            fmt="%.6f",
            newline="\r\n",
        )


if __name__ == "__main__":
    main()
