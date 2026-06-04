# PS5 PFS-in-PFSC CLI Container Builder

A seamless, zero-config CLI tool to pack and build PS5 homebrew images in the `.ffpfsc` container format for ShadowMountPlus (SMP).

Rather than using complex, platform-dependent exFAT loopback mounts, this tool creates a standard **uncompressed PFS image (`pfs_image.dat`)** and packs it inside a **compressed PFS container (`.ffpfsc`)**, which is the recommended layout for nested images in ShadowMountPlus.

## Features
- **Pure Python & Cross-Platform**: Runs natively on macOS, Linux, and Windows with **zero** OS-specific dependencies.
- **No Admin/Root Privileges Required**: Since it doesn't need to mount loopback disks or format drives, it runs completely in userland.
- **Smart Folder Discovery**: You don't need to pass the exact game root. The script recursively scans the provided directory for the actual game folder (containing `eboot.bin` and `sce_sys/param.json`).
- **Title ID Auto-Naming**: Automatically parses `sce_sys/param.json` to extract the game's actual Title ID (e.g., `PPSA01411`) and names output files accordingly.
- **Batch Processing**: Process an entire directory of multiple games into separate images automatically using the `--batch` flag.
- **Auto-Cleanup**: Automatically cleans up intermediate nested PFS files, keeping only the final compressed `.ffpfsc` file.

## Requirements
- Python 3.8+
- The `mkpfs` package. 
  > **Note:** The script will automatically prioritize any local workspace directory found in sibling folders. Otherwise, it will fallback to the system `mkpfs` command or auto-install it via `pip` on first run.

## Installation & Setup

```bash
git clone https://github.com/bizkut/ps5-ffpfs-cli.git
cd ps5-ffpfs-cli
```

## Usage

```bash
python3 cli.py [game_folder_or_exfat_file] [output_dir_or_file] [options]
```

### Examples

**Standard Process (Nested PFS -> .ffpfsc):**
Scans for the game folder inside the given path, builds a nested PFS image (`pfs_image.dat`), compresses it via `mkpfs` into `.ffpfsc`, and cleans up the intermediate files. It outputs to the current directory.
```bash
python3 cli.py /path/to/GameFolder
```

**Convert Existing exFAT (exFAT -> .ffpfsc):**
Directly converts an existing `.exfat` file to `.ffpfsc` container format using `mkpfs`, skipping the nested PFS creation and leaving the original `.exfat` file intact.
```bash
python3 cli.py /path/to/GameImage.exfat
```

**Batch Processing:**
Scan an entire directory for multiple game folders and `.exfat` files, packing/converting all of them into the specified output directory using their Title IDs.
```bash
python3 cli.py /path/to/AllGames /path/to/OutputFolder --batch
```

**Keep Intermediate Files:**
If you want to keep the uncompressed nested PFS image (saved as `<title_id>_nested_pfs.dat`):
```bash
python3 cli.py /path/to/GameFolder --keep-pfs
```
