#!/Users/bizkut/Downloads/PS5/.venv/bin/python
import sys

# Intercept if called as mkpfs sub-command in bundled mode
if len(sys.argv) > 1 and sys.argv[1] == "--mkpfs-internal":
    try:
        from mkpfs.cli import cli_mkpfs_main
        sys.exit(cli_mkpfs_main(sys.argv[2:]))
    except Exception as e:
        print(f"[ERROR] Internal MkPFS call failed: {e}", file=sys.stderr)
        sys.exit(1)

import os
import argparse
import subprocess
import shutil
import json
import re
import tempfile
from pathlib import Path

def get_title_id_from_name(name: str) -> str:
    # Look for standard PS4/PS5 title ID formats like PPSA12345 or CUSA12345
    match = re.search(r'\b([A-Z]{4}\d{5})\b', name, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    # Otherwise fallback to clean name
    fallback = name
    for suffix in [".exfat", "-app0", "-app", "-patch0", "-patch"]:
        if fallback.lower().endswith(suffix):
            fallback = fallback[:-len(suffix)]
    return fallback

def get_title_id(item_path: Path) -> str:
    if item_path.is_dir():
        param_path = item_path / "sce_sys" / "param.json"
        try:
            if param_path.is_file():
                with open(param_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "titleId" in data:
                        return data["titleId"]
                    if "title_id" in data:
                        return data["title_id"]
        except Exception as e:
            print(f"[WARN] Could not parse param.json for title ID: {e}")
            
    return get_title_id_from_name(item_path.name)

def find_game_items(path: Path, batch: bool = False) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() == '.exfat':
            return [path]
        else:
            print(f"[ERROR] Unsupported file type: {path.name}. Only .exfat files are supported.")
            sys.exit(1)
            
    print(f"[INFO] Scanning for game folder(s) and .exfat file(s) in {path}...")
    valid_items = []
    
    # 1. Scan for .exfat files
    for dirpath, _, filenames in os.walk(path):
        curr_dir = Path(dirpath)
        for f in filenames:
            if f.lower().endswith('.exfat'):
                valid_items.append(curr_dir / f)
                
    # 2. Scan for game folders
    for dirpath, _, _ in os.walk(path):
        curr_dir = Path(dirpath)
        eboot_path = curr_dir / "eboot.bin"
        param_path = curr_dir / "sce_sys" / "param.json"
        
        if eboot_path.is_file() and param_path.is_file():
            valid_items.append(curr_dir)
            
    if len(valid_items) == 0:
        print(f"[ERROR] Could not find any valid game folders or .exfat files in {path}.")
        sys.exit(1)
        
    if not batch and len(valid_items) > 1:
        print(f"[ERROR] Multiple game folders/files found in {path}:")
        for item in valid_items:
            print(f"  - {item}")
        print("Please specify a more specific folder/file or use --batch to process all.")
        sys.exit(1)
        
    if not batch:
        print(f"[OK] Found game source at {valid_items[0]}")
    else:
        print(f"[OK] Found {len(valid_items)} game item(s) for batch processing.")
        
    return valid_items

def pack_folder_uncompressed(game_folder: Path, pfs_path: Path, mkpfs_cmd_base: list[str], mkpfs_cwd: str | None):
    print(f"[INFO] Packing folder {game_folder.name} to uncompressed PFS image {pfs_path.name}...")
    cmd = mkpfs_cmd_base + [
        "pack", "folder",
        "--no-compress",
        "--no-adjust-output-file-extension",
        "--version", "PS5",
        "--inode-bits", "32",
        "--verify",
        str(game_folder),
        str(pfs_path)
    ]
    print(f"[INFO] Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=mkpfs_cwd, check=True)
    print(f"[OK] Uncompressed PFS creation complete: {pfs_path}")

def compress_file_to_ffpfsc(source_file: Path, ffpfsc_path: Path, mkpfs_cmd_base: list[str], mkpfs_cwd: str | None):
    print(f"[INFO] Compressing {source_file.name} to outer container {ffpfsc_path.name} using MkPFS...")
    cmd = mkpfs_cmd_base + [
        "pack", "file",
        "--compress",
        "--version", "PS5",
        "--inode-bits", "32",
        str(source_file),
        str(ffpfsc_path)
    ]
    print(f"[INFO] Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=mkpfs_cwd, check=True)
    print(f"[OK] Compression complete: {ffpfsc_path}")

def main():
    parser = argparse.ArgumentParser(description="Create a compressed PFS container (.ffpfsc) enclosing a nested PFS or exFAT image from a PS5 game folder or .exfat file.")
    parser.add_argument("game_folder", type=str, nargs='?', help="Path to the source game folder or existing .exfat file")
    parser.add_argument("output", type=str, nargs='?', default=".", help="Path to the output .ffpfsc file or directory (defaults to current directory)")
    parser.add_argument("--keep-pfs", action="store_true", help="Keep the intermediate nested PFS image (saved as <title_id>_nested_pfs.dat)")
    parser.add_argument("--batch", action="store_true", help="Process multiple game folders/files into multiple images. 'output' will be treated as the output directory.")
    parser.add_argument("--gui", action="store_true", help="Launch the graphical user interface")
    parser.add_argument("-f", "--force", "--overwrite", dest="overwrite", action="store_true", help="Overwrite existing files without prompting")
    
    args = parser.parse_args()
    
    if args.gui:
        try:
            import customtkinter as ctk
            from gui import PS5ContainerBuilderApp
            root = ctk.CTk()
            app = PS5ContainerBuilderApp(root)
            if args.game_folder:
                app.source_var.set(str(Path(args.game_folder).resolve()))
            if args.output:
                app.output_var.set(str(Path(args.output).resolve()))
            if args.keep_pfs:
                app.keep_pfs_var.set(True)
            if args.batch:
                app.batch_var.set(True)
            root.mainloop()
            sys.exit(0)
        except ImportError:
            print("[ERROR] GUI requires 'customtkinter'. Please install it: pip install customtkinter")
            sys.exit(1)

    if not args.game_folder:
        parser.print_help()
        sys.exit(1)
        
    game_folder = Path(args.game_folder).resolve()
    ffpfs_path = Path(args.output).resolve()
    
    if not game_folder.exists():
        print(f"[ERROR] Source path does not exist: {game_folder}")
        sys.exit(1)
        
    game_items = find_game_items(game_folder, args.batch)
    
    if args.batch:
        if not ffpfs_path.exists():
            ffpfs_path.mkdir(parents=True, exist_ok=True)
        elif not ffpfs_path.is_dir():
            print(f"[ERROR] Output path {ffpfs_path} must be a directory when using --batch.")
            sys.exit(1)
    
    # Locate MkPFS
    mkpfs_cmd_base = None
    mkpfs_cwd = None
    
    if getattr(sys, "frozen", False):
        mkpfs_cmd_base = [sys.executable, "--mkpfs-internal"]
        mkpfs_cwd = None
        print("[INFO] Running in packaged/frozen environment. Using internal MkPFS bundle.")
    
    # 1. Prioritize any local workspace found in sibling folders containing a mkpfs package
    parent_dir = Path(__file__).resolve().parent.parent
    try:
        for sibling in parent_dir.iterdir():
            if sibling.is_dir() and (sibling / "mkpfs" / "__main__.py").is_file():
                mkpfs_cmd_base = [sys.executable, "-m", "mkpfs"]
                mkpfs_cwd = str(sibling)
                print(f"[INFO] Using local workspace directory at {sibling}")
                break
    except Exception:
        pass
    
    # 2. Try system PATH
    if mkpfs_cmd_base is None and shutil.which("mkpfs"):
        mkpfs_cmd_base = ["mkpfs"]
    
    # 3. Auto-install via pip if not found
    if mkpfs_cmd_base is None:
        print("[INFO] MkPFS not found. Installing automatically via pip...")
        res = subprocess.run([sys.executable, "-m", "pip", "install", "mkpfs"], capture_output=True, text=True)
        if res.returncode != 0:
            print("[ERROR] Failed to install mkpfs. Please install it manually: pip install mkpfs")
            print(res.stderr)
            sys.exit(1)
        print("[OK] MkPFS installed successfully.")
        mkpfs_cmd_base = [sys.executable, "-m", "mkpfs"]
        
    ext = ".ffpfsc"
    
    for item in game_items:
        title_id = get_title_id(item)
        
        if args.batch or ffpfs_path.is_dir():
            current_ffpfs_path = ffpfs_path / f"{title_id}{ext}"
        else:
            current_ffpfs_path = ffpfs_path.with_suffix(ext)
        
        if args.batch:
            print(f"\n[INFO] --- Processing batch item: {title_id} ({item.name}) ---")
            
        if current_ffpfs_path.exists():
            if args.overwrite:
                print(f"[WARN] Output file already exists. Overwriting: {current_ffpfs_path}")
                try:
                    current_ffpfs_path.unlink()
                except Exception as e:
                    print(f"[ERROR] Failed to remove existing output file: {e}")
                    sys.exit(1)
            else:
                print(f"[WARN] Output file already exists: {current_ffpfs_path}")
                try:
                    if sys.stdin.isatty():
                        response = input("Overwrite existing file? [y/N]: ").strip().lower()
                    else:
                        print("[INFO] Non-interactive shell detected. Skipping overwrite.")
                        response = 'n'
                except (KeyboardInterrupt, EOFError):
                    print("\n[INFO] Cancelled by user.")
                    sys.exit(0)
                if response not in ('y', 'yes'):
                    print(f"[INFO] Skipping: {current_ffpfs_path.name}")
                    continue
                try:
                    current_ffpfs_path.unlink()
                except Exception as e:
                    print(f"[ERROR] Failed to remove existing output file: {e}")
                    sys.exit(1)
            
        if item.is_file() and item.suffix.lower() == '.exfat':
            # Direct exFAT file to compressed PFS (.ffpfsc) conversion
            compress_file_to_ffpfsc(item, current_ffpfs_path, mkpfs_cmd_base, mkpfs_cwd)
        else:
            # Game folder: pack to uncompressed PFS first, then compress to .ffpfsc
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_pfs = Path(temp_dir) / "pfs_image.dat"
                
                # 1. Pack folder into the uncompressed PFS image
                pack_folder_uncompressed(item, temp_pfs, mkpfs_cmd_base, mkpfs_cwd)
                
                # 2. Compress that PFS image file into the final .ffpfsc
                compress_file_to_ffpfsc(temp_pfs, current_ffpfs_path, mkpfs_cmd_base, mkpfs_cwd)
                
                if args.keep_pfs:
                    saved_pfs_path = current_ffpfs_path.parent / f"{title_id}_nested_pfs.dat"
                    print(f"[INFO] Saving intermediate PFS image to {saved_pfs_path}...")
                    shutil.copy2(temp_pfs, saved_pfs_path)
                
    print("\n[SUCCESS] All operations completed successfully!")

if __name__ == "__main__":
    main()
