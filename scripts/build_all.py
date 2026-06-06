"""Orchestrator: run the full IMS Games data pipeline in order."""

import argparse
import subprocess
import sys
import time
from pathlib import Path

# All pipeline step scripts (module name without .py).
PIPELINE_STEPS = [
    "init_db",
    "import_metacritic_kaggle",
    "import_opencritic",
    "match_games",
    "normalize_scores",
    "compute_source_metrics",
    "compute_weights",
    "compute_game_scores",
    "export_static_json",
]

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent


def _find_python() -> str:
    """Return the best Python executable for running pipeline scripts.

    Preference order:
    1. Project-local .venv Python (most reliable on Windows).
    2. ``uv run`` wrapper if uv is on PATH.
    3. The currently running interpreter (``sys.executable``).
    """
    # 1. Check for a project-local venv.
    venv_candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",   # Windows
        PROJECT_ROOT / ".venv" / "bin" / "python",            # macOS / Linux
    ]
    for candidate in venv_candidates:
        if candidate.exists():
            return str(candidate)

    # 2. Check if uv is available (uv run resolves the venv automatically).
    import shutil
    if shutil.which("uv"):
        return "uv"  # handled specially in run_step

    # 3. Fall back to the current interpreter.
    return sys.executable


_PYTHON = _find_python()


def run_step(name: str, extra_args: list[str] | None = None) -> float:
    """Run a single pipeline step and return elapsed seconds."""
    script = SCRIPT_DIR / f"{name}.py"

    if _PYTHON == "uv":
        cmd = ["uv", "run", "python", str(script)]
    else:
        cmd = [_PYTHON, str(script)]
    if extra_args:
        cmd.extend(extra_args)

    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    elapsed = time.time() - t0

    if result.returncode != 0:
        raise RuntimeError(
            f"Step '{name}' failed with exit code {result.returncode}"
        )
    return elapsed


def main():
    parser = argparse.ArgumentParser(
        description="Run the full IMS Games data pipeline.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Drop and recreate the database before importing.",
    )
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip the final export_static_json step (data pipeline only).",
    )
    args = parser.parse_args()

    steps = list(PIPELINE_STEPS)
    if args.skip_frontend:
        steps.remove("export_static_json")

    print("=" * 60)
    print("  IMS Games  -  Full Pipeline Build")
    print("=" * 60)
    print(f"  Python       : {_PYTHON}")
    print(f"  Steps to run : {len(steps)}")
    print(f"  --rebuild    : {args.rebuild}")
    print(f"  --skip-front : {args.skip_frontend}")
    print()

    timings: list[tuple[str, float]] = []
    total_t0 = time.time()

    for i, step_name in enumerate(steps, start=1):
        label = f"[{i}/{len(steps)}] {step_name}"
        print("-" * 60)
        print(f"  {label}")
        print("-" * 60)

        script = SCRIPT_DIR / f"{step_name}.py"
        if not script.exists():
            print(f"  [SKIP] {step_name}.py not found -- script not yet implemented.")
            timings.append((step_name, 0.0))
            continue

        extra = None
        if step_name == "init_db" and args.rebuild:
            extra = ["--rebuild"]

        try:
            elapsed = run_step(step_name, extra_args=extra)
        except RuntimeError as exc:
            print(f"\n  [FAIL] {exc}")
            print(f"\n  Pipeline stopped at step {i}/{len(steps)}: {step_name}")
            sys.exit(1)

        timings.append((step_name, elapsed))
        print(f"  -> {step_name} completed in {elapsed:.2f}s\n")

    total_elapsed = time.time() - total_t0

    # Summary table.
    print("=" * 60)
    print("  Pipeline Summary")
    print("=" * 60)
    print(f"  {'Step':<30} {'Time':>10}")
    print(f"  {'-' * 30} {'-' * 10}")
    for name, secs in timings:
        status = f"{secs:.2f}s" if secs > 0 else "skipped"
        print(f"  {name:<30} {status:>10}")
    print(f"  {'-' * 30} {'-' * 10}")
    print(f"  {'TOTAL':<30} {total_elapsed:>9.2f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
