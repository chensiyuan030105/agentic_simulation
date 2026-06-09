#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect an SPH run bundle.")
    parser.add_argument("run_dir", type=Path, help="SPH run directory under outputs/runs/.")
    return parser.parse_args()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    manifest = _read_json(run_dir / "manifest.json")
    metrics = _read_json(run_dir / "metrics.json")
    with np.load(run_dir / "particles.npz") as bundle:
        shapes = {name: tuple(bundle[name].shape) for name in bundle.files}

    print(f"run_dir       : {run_dir}")
    print(f"run_name      : {manifest.get('run_name')}")
    print(f"created       : {manifest.get('created_at')}")
    print(f"frames        : {manifest.get('frames')}")
    print(f"fps           : {manifest.get('fps')}")
    print(f"particles     : {metrics.get('particle_count')}")
    print(f"max speed     : {metrics.get('max_speed'):.6f}")
    print(f"mean density  : {metrics.get('mean_density'):.6f}")
    print(f"outside bounds: {metrics.get('outside_bounds_count')}")
    print(f"com start     : {metrics.get('center_of_mass_start')}")
    print(f"com final     : {metrics.get('center_of_mass_final')}")
    print("arrays:")
    for name, shape in shapes.items():
        print(f"  {name:12s} {shape}")


if __name__ == "__main__":
    main()
