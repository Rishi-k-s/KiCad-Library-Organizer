#!/usr/bin/env python3

import sys
import zipfile
import shutil
import argparse
from pathlib import Path
from collections import defaultdict


# Map file extensions to output subdirectories
EXT_MAP = {
    ".step":      "3d_models",
    ".kicad_mod": "schematic",
    ".kicad_sym": "symbol",
}

EXT_LABELS = {
    ".step":      "3D Model  (.step)",
    ".kicad_mod": "Footprint (.kicad_mod)",
    ".kicad_sym": "Symbol    (.kicad_sym)",
}


# ─── prompts ────────────────────────────────────────────────────────────────

def prompt_pick_one(candidates: list[Path], ext: str, zip_name: str) -> Path | None:
    """When a zip has multiple files of the same type, ask user to pick one."""
    print(f"\n  Multiple {EXT_LABELS[ext]} files found in '{zip_name}':")
    for i, p in enumerate(candidates, 1):
        print(f"    [{i}] {p.name}")
    print(f"    [s] Skip all")
    while True:
        choice = input("  Pick one → ").strip().lower()
        if choice == "s":
            return None
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(candidates):
                return candidates[idx - 1]
        print(f"  Enter a number between 1 and {len(candidates)}, or 's' to skip.")


def prompt_duplicate(filename: str, dest: Path) -> str | Path:
    """When output file already exists, ask user what to do."""
    print(f"\n  ⚠  Duplicate: '{filename}' already exists at '{dest}'")
    while True:
        choice = input("     [o] Overwrite  [s] Skip  [r] Rename → ").strip().lower()
        if choice == "o":
            return "overwrite"
        elif choice == "s":
            return "skip"
        elif choice == "r":
            new_name = input("     Enter new filename: ").strip()
            if new_name:
                return dest.parent / new_name
            print("     Name cannot be empty.")
        else:
            print("     Please enter o, s, or r.")


# ─── file copy ──────────────────────────────────────────────────────────────

def resolve_filename(src: Path, canonical_stem: str) -> str:
    """
    Return the output filename for src.
    If the first 3 chars of src.stem match canonical_stem, keep the original name.
    Otherwise rename to canonical_stem + src.suffix.
    """
    if src.stem[:3].lower() == canonical_stem[:3].lower():
        return src.name
    return canonical_stem + src.suffix.lower()


def copy_file(src: Path, dest_dir: Path, filename: str) -> str:
    """Copy src to dest_dir/filename, handling duplicates. Returns status string."""
    dest = dest_dir / filename
    if dest.exists():
        resolution = prompt_duplicate(filename, dest)
        if resolution == "skip":
            return "skipped"
        elif resolution != "overwrite":
            dest = resolution          # renamed path
    shutil.copy2(src, dest)
    return f"→ {dest.relative_to(dest.parent.parent)}"


# ─── per-zip processing ─────────────────────────────────────────────────────

def process_zip(zip_path: Path, output_root: Path, tmp_base: Path) -> dict:
    """
    Extract zip, resolve multiple-file-per-type conflicts interactively,
    copy winners to output dirs.
    Returns {"found", "skipped", "copied", "missing": set[ext]}.
    """
    counts = {"found": 0, "skipped": 0, "copied": 0}

    tmp_dir = tmp_base / zip_path.stem
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)
    except zipfile.BadZipFile:
        print(f"  ✗ Bad zip file, skipping: {zip_path.name}")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        counts["missing"] = set(EXT_MAP.keys())
        return counts

    # Group all relevant files by extension
    by_ext: dict[str, list[Path]] = defaultdict(list)
    for file_path in tmp_dir.rglob("*"):
        if file_path.is_file():
            ext = file_path.suffix.lower()
            if ext in EXT_MAP:
                by_ext[ext].append(file_path)

    chosen: dict[str, Path | None] = {}   # ext -> file to copy (None = skipped/missing)

    for ext in EXT_MAP:
        files = by_ext.get(ext, [])
        if not files:
            chosen[ext] = None           # genuinely missing
        elif len(files) == 1:
            chosen[ext] = files[0]       # only one, no choice needed
        else:
            # Multiple — ask user
            picked = prompt_pick_one(files, ext, zip_path.name)
            chosen[ext] = picked         # None means user skipped

    # Determine canonical stem: prefer .kicad_mod choice, fall back to zip stem
    mod_choice = chosen.get(".kicad_mod")
    canonical_stem = mod_choice.stem if mod_choice else zip_path.stem

    # Copy chosen files, renaming where needed
    missing_exts = set()
    for ext, src in chosen.items():
        if src is None:
            if not by_ext.get(ext):      # truly absent, not user-skipped
                missing_exts.add(ext)
            else:
                counts["skipped"] += 1
                print(f"    SKIP  (user skipped {EXT_LABELS[ext]})")
            continue

        counts["found"] += 1
        dest_subdir = output_root / EXT_MAP[ext]
        dest_subdir.mkdir(parents=True, exist_ok=True)

        out_name = resolve_filename(src, canonical_stem)
        if out_name != src.name:
            print(f"    RENAME  {src.name}  →  {out_name}")

        status = copy_file(src, dest_subdir, out_name)
        if status == "skipped":
            counts["skipped"] += 1
            print(f"    SKIP  {src.name}")
        else:
            counts["copied"] += 1
            print(f"    COPY  {src.name}  {status}")

    shutil.rmtree(tmp_dir, ignore_errors=True)
    counts["missing"] = missing_exts
    return counts


# ─── main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Organise KiCad footprint zips into 3d_models/, schematic/, symbol/."
    )
    parser.add_argument("input_dir",  help="Directory containing .zip files (searched recursively)")
    parser.add_argument("output_dir", help="Root output directory")
    args = parser.parse_args()

    input_root  = Path(args.input_dir).resolve()
    output_root = Path(args.output_dir).resolve()

    if not input_root.is_dir():
        print(f"Error: input directory does not exist: {input_root}")
        sys.exit(1)

    output_root.mkdir(parents=True, exist_ok=True)
    tmp_base = output_root / ".kicad_tmp"
    tmp_base.mkdir(parents=True, exist_ok=True)

    zips = sorted(input_root.rglob("*.zip"))
    if not zips:
        print("No .zip files found in the input directory.")
        shutil.rmtree(tmp_base, ignore_errors=True)
        return

    print(f"\nFound {len(zips)} zip file(s) in '{input_root}'\n")
    print(f"Output root: {output_root}\n")
    print("=" * 60)

    total = {"found": 0, "skipped": 0, "copied": 0}
    missing_report: dict[str, set] = {}   # zip stem -> set of missing exts

    for zip_path in zips:
        print(f"\n[ZIP] {zip_path.relative_to(input_root)}")
        counts = process_zip(zip_path, output_root, tmp_base)
        for k in ("found", "skipped", "copied"):
            total[k] += counts[k]

        if counts["found"] == 0 and not counts["missing"] == set(EXT_MAP.keys()):
            print("    (all files were skipped by user)")

        if counts.get("missing"):
            missing_report[zip_path.stem] = counts["missing"]

    shutil.rmtree(tmp_base, ignore_errors=True)

    # ── summary ──
    print("\n" + "=" * 60)
    print(f"Done.  Files found: {total['found']}  |  Copied: {total['copied']}  |  Skipped: {total['skipped']}")
    print(f"\nOutput structure:")
    for label, subdir in [("STEP models", "3d_models"), ("Footprints", "schematic"), ("Symbols", "symbol")]:
        d = output_root / subdir
        count = len(list(d.glob("*"))) if d.exists() else 0
        print(f"  {d}  ({count} file(s))")

    # ── missing report ──
    if missing_report:
        print("\n" + "=" * 60)
        print("⚠  MISSING FILE TYPES PER PART\n")
        print(f"  {'Part':<40}  {'Missing'}")
        print(f"  {'-'*40}  {'-'*45}")
        for part_name, missing_exts in sorted(missing_report.items()):
            missing_str = ",  ".join(EXT_LABELS[e] for e in sorted(missing_exts))
            print(f"  {part_name:<40}  {missing_str}")
        print()
    else:
        print("\n✓  All parts have all three file types.")


if __name__ == "__main__":
    main()