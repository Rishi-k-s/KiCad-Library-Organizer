# KiCad Library Organizer

A command-line tool that takes KiCad component `.zip` files (typically downloaded from LCSC, SnapEDA, or similar sources) and sorts their contents into a clean, structured library directory.

## Requirements

- Python 3.10 or higher (no third-party packages needed)

## Usage

```bash
python kicad_organizer.py <input_dir> <output_dir>
```

| Argument | Description |
|---|---|
| `input_dir` | Folder containing your downloaded `.zip` files. Searched recursively — zips inside subdirectories are found automatically. |
| `output_dir` | Root folder where the organised library will be created. |

**Example:**

```bash
python kicad_organizer.py C:\Downloads\kicad_zips D:\parayu\library
```

## Output Structure

```
output_dir/
├── 3d_models/     ← .step files
├── schematic/     ← .kicad_mod footprint files
└── symbol/        ← .kicad_sym symbol files
```

Original `.zip` files are never modified or deleted.

---

## How It Works

### 1. Recursive zip discovery
The script walks the entire `input_dir` tree and processes every `.zip` it finds, regardless of how deeply nested.

### 2. Deep extraction
Each zip is extracted to a temporary folder. The script then digs into all nested folders inside the zip looking for `.step`, `.kicad_mod`, and `.kicad_sym` files. Any other file types are ignored.

### 3. Multiple files of the same type — interactive picker
Some zips (common with EasyEDA exports) contain several variants of the same file type, e.g.:

```
CAP_CC0402_YAG.kicad_mod
CAP_CC0402_YAG-L.kicad_mod
CAP_CC0402_YAG-M.kicad_mod
```

When this happens the script pauses and asks you to pick one:

```
  Multiple Footprint (.kicad_mod) files found in 'CAP_CC0402.zip':
    [1] CAP_CC0402_YAG.kicad_mod
    [2] CAP_CC0402_YAG-L.kicad_mod
    [3] CAP_CC0402_YAG-M.kicad_mod
    [s] Skip all
  Pick one →
```

Enter the number of the file you want, or `s` to skip that file type entirely for this part.

### 4. Automatic renaming
Some exporters generate files with timestamp-based names like `2026-06-14_13-34-00.kicad_sym`. The script detects this and renames the file to match the part name automatically.

**The rule:** the chosen `.kicad_mod` filename is the canonical part name. Any other file whose name does not share the same first 3 characters as the `.kicad_mod` is renamed to match it.

```
CAP_CC0402_YAG-L.kicad_mod  →  schematic/CAP_CC0402_YAG-L.kicad_mod  (unchanged)
CAP_CC0402_YAG.step          →  3d_models/CAP_CC0402_YAG.step          (unchanged, CAP = CAP)
2026-06-14_13-34-00.kicad_sym  →  symbol/CAP_CC0402_YAG-L.kicad_sym   (renamed, 202 ≠ CAP)
```

If no `.kicad_mod` is present in the zip, the zip filename stem is used as the canonical name instead.

### 5. Duplicate handling
If a file with the same name already exists in the output directory (e.g. you run the script twice, or two zips produce the same output name), the script pauses and asks:

```
  ⚠  Duplicate: 'ESP32.kicad_mod' already exists at 'D:\library\schematic\ESP32.kicad_mod'
     [o] Overwrite  [s] Skip  [r] Rename →
```

| Option | Action |
|---|---|
| `o` | Overwrite the existing file |
| `s` | Skip this file, keep the existing one |
| `r` | Enter a new filename to save it under |

---

## End-of-Run Summary

After processing all zips, the script prints a summary:

```
============================================================
Done.  Files found: 42  |  Copied: 42  |  Skipped: 0

Output structure:
  D:\parayu\library\3d_models   (13 file(s))
  D:\parayu\library\schematic   (13 file(s))
  D:\parayu\library\symbol      (13 file(s))

============================================================
⚠  MISSING FILE TYPES PER PART

  Part                                      Missing
  ----------------------------------------  -------------------------------------------
  TXU0204RUTR                               3D Model  (.step)
  ul_AP7365-33WG-7                          3D Model  (.step)
```

If all parts are complete it prints:

```
✓  All parts have all three file types.
```

The missing report is keyed by zip filename, so `TXU0204RUTR` means the file `TXU0204RUTR.zip` had no `.step` inside it. Use this list to go back to the source (LCSC/EasyEDA) and download the missing assets.

---

## Adding the Library to KiCad

Once the script finishes, point KiCad at the output folders:

**Footprints** — Preferences → Manage Footprint Libraries → Add `output_dir/schematic/`

**Symbols** — Preferences → Manage Symbol Libraries → Add `output_dir/symbol/`

**3D Models** — Referenced automatically from footprint files; set the `KICAD_3DMODEL_DIR` path variable to `output_dir/3d_models/` under Preferences → Configure Paths.