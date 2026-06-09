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
    parser = argparse.ArgumentParser(description="Render a fluid simulation run with Blender.")
    parser.add_argument("run_dir", type=Path, help="Fluid run directory containing fluid_scene.json and fields.npz.")
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "configs" / "render" / "blender_5_1.yaml",
        help="Render YAML config.",
    )
    parser.add_argument("--blender", type=Path, default=None, help="Override Blender executable path.")
    parser.add_argument("--video-out", type=Path, default=None, help="Optional explicit MP4 path.")
    parser.add_argument("--blend-out", type=Path, default=None, help="Optional explicit .blend path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    config_path = args.config.expanduser().resolve()
    config = load_yaml(config_path)
    blender_path = args.blender or Path(str(config.get("blender_executable", "blender")))
    blender_path = blender_path.expanduser()
    if not blender_path.exists() and len(blender_path.parts) != 1:
        raise FileNotFoundError(f"Blender executable not found: {blender_path}")

    runtime_config_path = run_dir / "render_fluid_config.runtime.json"
    runtime_config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    command = [
        str(blender_path),
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(REPO_ROOT / "blender" / "render_fluid.py"),
        "--",
        "--config",
        str(runtime_config_path),
        "--run",
        str(run_dir),
    ]
    if args.video_out is not None:
        command.extend(["--video-out", str(args.video_out.expanduser().resolve())])
    if args.blend_out is not None:
        command.extend(["--blend-out", str(args.blend_out.expanduser().resolve())])

    env = os.environ.copy()
    library_paths = config.get("library_paths", [])
    if isinstance(library_paths, list) and library_paths:
        existing = env.get("LD_LIBRARY_PATH", "")
        resolved_paths = [str(Path(str(path)).expanduser().resolve()) for path in library_paths]
        env["LD_LIBRARY_PATH"] = ":".join([*resolved_paths, existing] if existing else resolved_paths)

    print("[run]", " ".join(command))
    subprocess.run(command, check=True, env=env)


if __name__ == "__main__":
    main()
