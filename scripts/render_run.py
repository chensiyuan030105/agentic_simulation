#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agentic_simulation.config import load_yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a simulation run with Blender.")
    parser.add_argument("run_dir", type=Path, help="Run directory containing scene.json and trajectories.npz.")
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
    config_path = args.config.expanduser().resolve()
    config = load_yaml(config_path)
    blender_path = args.blender or Path(str(config.get("blender_executable", "blender")))
    blender_path = blender_path.expanduser()

    if not blender_path.exists() and not _is_path_command(blender_path):
        raise FileNotFoundError(
            f"Blender executable not found: {blender_path}. "
            "Pass --blender /path/to/blender-5.1/blender or update the render config."
        )

    command = [
        str(blender_path),
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(REPO_ROOT / "blender" / "render_scene.py"),
        "--",
        "--config",
        str(config_path),
        "--run",
        str(args.run_dir.expanduser().resolve()),
    ]
    if args.video_out is not None:
        command.extend(["--video-out", str(args.video_out.expanduser().resolve())])
    if args.blend_out is not None:
        command.extend(["--blend-out", str(args.blend_out.expanduser().resolve())])

    print("[run]", " ".join(command))
    subprocess.run(command, check=True)


def _is_path_command(path: Path) -> bool:
    return len(path.parts) == 1


if __name__ == "__main__":
    main()
