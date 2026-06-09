#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agentic_simulation.config import load_yaml
from agentic_simulation.sph import parse_sph_scene_config, run_sph_simulation
from agentic_simulation.sph_io import write_sph_run_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a 3D SPH dam-break simulation.")
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "configs" / "sim" / "sph_dambreak.yaml",
        help="SPH simulation YAML config.",
    )
    parser.add_argument("--out", type=Path, default=None, help="Output run directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config.expanduser().resolve()
    scene = parse_sph_scene_config(load_yaml(config_path))
    result = run_sph_simulation(scene)

    output_dir = args.out or (REPO_ROOT / "outputs" / "runs" / scene.run_name)
    output_dir = output_dir.expanduser().resolve()
    paths = write_sph_run_outputs(output_dir=output_dir, scene=scene, result=result, config_path=config_path)

    print("sph simulation complete")
    print(f"run_name : {scene.run_name}")
    print(f"frames   : {scene.world.frames}")
    print(f"particles: {result.positions.shape[1]}")
    print(f"output   : {output_dir}")
    for key, path in paths.items():
        print(f"{key:12s}: {path}")


if __name__ == "__main__":
    main()
