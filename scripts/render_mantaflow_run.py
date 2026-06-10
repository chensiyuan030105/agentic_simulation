#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agentic_simulation.config import load_yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bake and render a Blender Mantaflow dam-break scene.")
    parser.add_argument(
        "--sim-config",
        type=Path,
        default=REPO_ROOT / "configs" / "sim" / "mantaflow_dambreak.yaml",
        help="Mantaflow scene YAML config.",
    )
    parser.add_argument(
        "--render-config",
        type=Path,
        default=REPO_ROOT / "configs" / "render" / "blender_5_1.yaml",
        help="Blender render YAML config.",
    )
    parser.add_argument("--out", type=Path, default=None, help="Output run directory.")
    parser.add_argument("--blender", type=Path, default=None, help="Override Blender executable path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sim_config_path = args.sim_config.expanduser().resolve()
    render_config_path = args.render_config.expanduser().resolve()
    sim_config = load_yaml(sim_config_path)
    render_config = load_yaml(render_config_path)
    run_name = str(sim_config.get("run_name", "mantaflow_dambreak_001"))
    out_dir = args.out or (REPO_ROOT / "outputs" / "runs" / run_name)
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    runtime_config = {
        "sim": sim_config,
        "render": render_config,
        "sim_config_path": str(sim_config_path),
        "render_config_path": str(render_config_path),
    }
    runtime_config_path = out_dir / "mantaflow_config.runtime.json"
    runtime_config_path.write_text(json.dumps(runtime_config, indent=2), encoding="utf-8")

    blender_path = args.blender or Path(str(render_config.get("blender_executable", "blender")))
    blender_path = blender_path.expanduser()
    if not blender_path.exists() and len(blender_path.parts) != 1:
        raise FileNotFoundError(f"Blender executable not found: {blender_path}")

    command = [
        str(blender_path),
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(REPO_ROOT / "blender" / "render_mantaflow_dambreak.py"),
        "--",
        "--config",
        str(runtime_config_path),
        "--out",
        str(out_dir),
    ]

    env = os.environ.copy()
    library_paths = render_config.get("library_paths", [])
    if isinstance(library_paths, list) and library_paths:
        existing = env.get("LD_LIBRARY_PATH", "")
        resolved_paths = [str(Path(str(path)).expanduser().resolve()) for path in library_paths]
        env["LD_LIBRARY_PATH"] = ":".join([*resolved_paths, existing] if existing else resolved_paths)

    print("[run]", " ".join(command))
    subprocess.run(command, check=True, env=env)


if __name__ == "__main__":
    main()
