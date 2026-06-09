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
from agentic_simulation.io import write_run_outputs
from agentic_simulation.scene import parse_scene_config
from agentic_simulation.simulation import run_simulation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an agentic arena simulation.")
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "configs" / "sim" / "basic_scene.yaml",
        help="Simulation YAML config.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output run directory. Defaults to outputs/runs/<run_name>.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config.expanduser().resolve()
    scene = parse_scene_config(load_yaml(config_path))
    result = run_simulation(scene)

    output_dir = args.out
    if output_dir is None:
        output_dir = REPO_ROOT / "outputs" / "runs" / scene.run_name
    output_dir = output_dir.expanduser().resolve()

    paths = write_run_outputs(
        output_dir=output_dir,
        scene=scene,
        result=result,
        config_path=config_path,
    )

    print("agentic simulation complete")
    print(f"run_name : {scene.run_name}")
    print(f"frames   : {scene.world.frames}")
    print(f"agents   : {len(scene.agents)}")
    print(f"output   : {output_dir}")
    for key, path in paths.items():
        print(f"{key:12s}: {path}")


if __name__ == "__main__":
    main()
