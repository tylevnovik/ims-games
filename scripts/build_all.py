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
    "canonicalize_entities",
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
        cmd = ["uv", "run", "python", "-u", str(script)]
    else:
        cmd = [_PYTHON, "-u", str(script)]
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
    parser.add_argument(
        "--include-opencritic-web",
        action="store_true",
        help="Backfill OpenCritic public web snapshot data before recomputing scores.",
    )
    parser.add_argument(
        "--include-opencritic-legacy",
        action="store_true",
        help=(
            "Backfill every existing game that still has no OpenCritic reviews, then "
            "recompute scores and merge cross-source duplicates."
        ),
    )
    parser.add_argument(
        "--include-metacritic-web-repair",
        action="store_true",
        help=(
            "Repair capped Metacritic Kaggle samples by replacing targeted 50/100-row "
            "games with fuller public Metacritic critic-review JSON snapshots."
        ),
    )
    parser.add_argument(
        "--include-metacritic-metadata-repair",
        action="store_true",
        help=(
            "Fill missing release years for high-confidence games from Metacritic "
            "public product JSON before exporting static site data."
        ),
    )
    parser.add_argument(
        "--opencritic-years",
        nargs="+",
        default=["2024", "2025", "2026"],
        help="Years to fetch when --include-opencritic-web is set.",
    )
    parser.add_argument(
        "--opencritic-max-games",
        default=None,
        help="Limit games per year for OpenCritic web backfill smoke tests.",
    )
    parser.add_argument(
        "--opencritic-legacy-years",
        nargs="+",
        default=[str(year) for year in range(1980, 2024)],
        help="Years to scan when --include-opencritic-legacy is set.",
    )
    parser.add_argument(
        "--opencritic-legacy-max-games",
        default=None,
        help="Limit games per year for legacy OpenCritic smoke tests.",
    )
    parser.add_argument(
        "--opencritic-legacy-max-existing-reviews",
        default="50",
        help="Legacy mode targets existing games with at most this many non-OpenCritic reviews.",
    )
    parser.add_argument(
        "--opencritic-legacy-min-reviews",
        default="1",
        help="Legacy mode targets only OpenCritic games with at least this many listed reviews.",
    )
    parser.add_argument(
        "--opencritic-legacy-target-sample-counts",
        nargs="*",
        default=["50", "100"],
        help=(
            "Additional legacy repair pass for games whose current score snapshot sample_count "
            "is exactly one of these values. Pass the flag with no values to disable."
        ),
    )
    parser.add_argument(
        "--opencritic-workers",
        default="6",
        help="Concurrent OpenCritic review-page fetch workers.",
    )
    parser.add_argument(
        "--opencritic-sleep",
        default="0.05",
        help="Delay after each live OpenCritic fetch, in seconds.",
    )
    parser.add_argument(
        "--refresh-opencritic-cache",
        action="store_true",
        help="Refetch OpenCritic pages instead of using the local HTML cache.",
    )
    parser.add_argument(
        "--metacritic-web-repair-target-sample-counts",
        nargs="*",
        default=["50"],
        help="score_snapshots.sample_count values targeted by --include-metacritic-web-repair.",
    )
    parser.add_argument(
        "--metacritic-web-repair-min-reviews",
        default="51",
        help="Minimum public Metacritic critic-review count required for repair.",
    )
    parser.add_argument(
        "--metacritic-web-repair-limit",
        default=None,
        help="Limit Metacritic web repair targets for smoke tests.",
    )
    parser.add_argument(
        "--metacritic-web-sleep",
        default="0.05",
        help="Delay after each live Metacritic backend fetch, in seconds.",
    )
    parser.add_argument(
        "--metacritic-metadata-min-score",
        default="85",
        help="Minimum weighted score for --include-metacritic-metadata-repair targets.",
    )
    parser.add_argument(
        "--metacritic-metadata-min-sample-count",
        default="75",
        help="Minimum review count for --include-metacritic-metadata-repair targets.",
    )
    parser.add_argument(
        "--metacritic-metadata-require-opencritic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require OpenCritic coverage for Metacritic metadata repair targets.",
    )
    parser.add_argument(
        "--refresh-metacritic-cache",
        action="store_true",
        help="Refetch Metacritic backend JSON instead of using the local cache.",
    )
    args = parser.parse_args()

    steps = list(PIPELINE_STEPS)
    opencritic_insert_at = steps.index("import_opencritic") + 1
    if args.include_opencritic_web:
        steps.insert(opencritic_insert_at, "import_opencritic_web")
        opencritic_insert_at += 1
    if args.include_opencritic_legacy:
        steps.insert(opencritic_insert_at, "import_opencritic_web_no_oc")
        opencritic_insert_at += 1
    if args.include_metacritic_web_repair:
        # Metacritic web repair targets score_snapshots.sample_count values, so it
        # must run after an initial scoring pass. Then rerun the downstream steps
        # because the repair replaces capped Kaggle review samples with fuller
        # Metacritic web review sets.
        score_insert_at = steps.index("export_static_json")
        steps[score_insert_at:score_insert_at] = [
            "import_metacritic_web_repair",
            "match_games",
            "canonicalize_entities",
            "normalize_scores",
            "compute_source_metrics",
            "compute_weights",
            "compute_game_scores",
        ]
    if args.include_metacritic_metadata_repair:
        steps.insert(steps.index("export_static_json"), "import_metacritic_metadata_repair")
    if args.skip_frontend:
        steps.remove("export_static_json")

    print("=" * 60)
    print("  IMS Games  -  Full Pipeline Build")
    print("=" * 60)
    print(f"  Python       : {_PYTHON}")
    print(f"  Steps to run : {len(steps)}")
    print(f"  --rebuild    : {args.rebuild}")
    print(f"  --skip-front : {args.skip_frontend}")
    print(f"  OC web       : {args.include_opencritic_web}")
    print(f"  OC legacy    : {args.include_opencritic_legacy}")
    print(f"  MC web repair: {args.include_metacritic_web_repair}")
    print(f"  MC metadata  : {args.include_metacritic_metadata_repair}")
    print()

    timings: list[tuple[str, float]] = []
    total_t0 = time.time()

    for i, step_name in enumerate(steps, start=1):
        label = f"[{i}/{len(steps)}] {step_name}"
        print("-" * 60)
        print(f"  {label}")
        print("-" * 60)

        script_name = (
            "import_opencritic_web"
            if step_name in {"import_opencritic_web_no_oc", "import_opencritic_web_legacy", "import_opencritic_web_legacy_capped_samples"}
            else step_name
        )
        if step_name == "import_metacritic_web_repair":
            script_name = "import_metacritic_web"
        if step_name == "import_metacritic_metadata_repair":
            script_name = "import_metacritic_web"
        script = SCRIPT_DIR / f"{script_name}.py"
        if not script.exists():
            print(f"  [SKIP] {script_name}.py not found -- script not yet implemented.")
            timings.append((step_name, 0.0))
            continue

        extra = None
        if step_name == "init_db" and args.rebuild:
            extra = ["--rebuild"]
        elif step_name == "import_opencritic_web":
            extra = ["--write", "--replace", "--years", *args.opencritic_years]
            if args.opencritic_max_games:
                extra.extend(["--max-games", args.opencritic_max_games])
            extra.extend(["--workers", args.opencritic_workers, "--sleep", args.opencritic_sleep])
            if args.refresh_opencritic_cache:
                extra.append("--refresh-cache")
        elif step_name == "import_opencritic_web_no_oc":
            extra = [
                "--write",
                "--years",
                *args.opencritic_legacy_years,
                "--only-existing-no-oc",
                "--min-opencritic-reviews",
                args.opencritic_legacy_min_reviews,
                "--workers",
                args.opencritic_workers,
                "--sleep",
                args.opencritic_sleep,
            ]
            if args.opencritic_legacy_max_games:
                extra.extend(["--max-games", args.opencritic_legacy_max_games])
            if args.refresh_opencritic_cache:
                extra.append("--refresh-cache")
        elif step_name == "import_metacritic_web_repair":
            extra = [
                "--write",
                "--target-sample-counts",
                *args.metacritic_web_repair_target_sample_counts,
                "--min-review-count",
                args.metacritic_web_repair_min_reviews,
                "--sleep",
                args.metacritic_web_sleep,
            ]
            if args.metacritic_web_repair_limit:
                extra.extend(["--limit", args.metacritic_web_repair_limit])
            if args.refresh_metacritic_cache:
                extra.append("--refresh-cache")
        elif step_name == "import_metacritic_metadata_repair":
            extra = [
                "--write",
                "--metadata-missing-years",
                "--metadata-min-score",
                args.metacritic_metadata_min_score,
                "--metadata-min-sample-count",
                args.metacritic_metadata_min_sample_count,
                "--sleep",
                args.metacritic_web_sleep,
            ]
            if args.metacritic_metadata_require_opencritic:
                extra.append("--metadata-require-opencritic")
            else:
                extra.append("--no-metadata-require-opencritic")
            if args.refresh_metacritic_cache:
                extra.append("--refresh-cache")

        try:
            elapsed = run_step(script_name, extra_args=extra)
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
