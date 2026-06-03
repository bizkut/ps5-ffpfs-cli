#!/Users/bizkut/Downloads/PS5/.venv/bin/python
import os
import sys
import argparse
import subprocess
import shutil
import json
import tempfile
from pathlib import Path

def get_title_id(game_folder: Path) -> str:
    param_path = game_folder / "sce_sys" / "param.json"
    fallback = game_folder.name
    
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
        
    for suffix in ["-app0", "-app", "-patch0", "-patch"]:
        if fallback.endswith(suffix):
            return fallback[:-len(suffix)]
            
    return fallback

def find_game_folders(folder_path: Path, batch: bool = False) -> list[Path]:
    print(f"[INFO] Scanning for actual game folder(s) in {folder_path}...")
    valid_folders = []
    
    for dirpath, _, _ in os.walk(folder_path):
        curr = Path(dirpath)
        eboot_path = curr / "eboot.bin"
        param_path = curr / "sce_sys" / "param.json"
        
        if eboot_path.is_file() and param_path.is_file():
            valid_folders.append(curr)
            
    if len(valid_folders) == 0:
        print(f"[ERROR] Could not find eboot.bin and sce_sys/param.json in {folder_path} or its subdirectories.")
        sys.exit(1)
        
    if not batch and len(valid_folders) > 1:
        print(f"[ERROR] Multiple game folders found in {folder_path}:")
        for f in valid_folders:
            print(f"  - {f}")
        print("Please specify a more specific game folder or use --batch to process all.")
        sys.exit(1)
        
    if not batch:
        print(f"[OK] Found game folder structure at {valid_folders[0]}")
    else:
        print(f"[OK] Found {len(valid_folders)} game folder(s) for batch processing.")
        
    return valid_folders

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

def compress_pfs_to_ffpfsc(pfs_path: Path, ffpfsc_path: Path, mkpfs_cmd_base: list[str], mkpfs_cwd: str | None):
    print(f"[INFO] Compressing nested PFS image {pfs_path.name} to outer container {ffpfsc_path.name}...")
    cmd = mkpfs_cmd_base + [
        "pack", "file",
        "--compress",
        "--version", "PS5",
        "--inode-bits", "32",
        "--verify",
        str(pfs_path),
        str(ffpfsc_path)
    ]
    print(f"[INFO] Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=mkpfs_cwd, check=True)
    print(f"[OK] Compression complete: {ffpfsc_path}")

def main():
    parser = argparse.ArgumentParser(description="Create a compressed PFS container (.ffpfsc) enclosing a nested PFS image from a PS5 game folder.")
    parser.add_argument("game_folder", type=str, help="Path to the source game folder")
    parser.add_argument("output", type=str, nargs='?', default=".", help="Path to the output .ffpfsc file or directory (defaults to current directory)")
    parser.add_argument("--keep-pfs", action="store_true", help="Keep the intermediate nested PFS image (saved as <title_id>_nested_pfs.dat)")
    parser.add_argument("--batch", action="store_true", help="Process multiple game folders into multiple images. 'output' will be treated as the output directory.")
    
    args = parser.parse_args()
    
    game_folder = Path(args.game_folder).resolve()
    ffpfs_path = Path(args.output).resolve()
    
    if not game_folder.is_dir():
        print(f"[ERROR] Game folder does not exist: {game_folder}")
        sys.exit(1)
        
    game_folders = find_game_folders(game_folder, args.batch)
    
    if args.batch:
        if not ffpfs_path.exists():
            ffpfs_path.mkdir(parents=True, exist_ok=True)
        elif not ffpfs_path.is_dir():
            print(f"[ERROR] Output path {ffpfs_path} must be a directory when using --batch.")
            sys.exit(1)
    
    # Locate MkPFS
    mkpfs_cmd_base = None
    mkpfs_cwd = None
    
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
    
    for gf in game_folders:
        title_id = get_title_id(gf)
        
        if args.batch or ffpfs_path.is_dir():
            current_ffpfs_path = ffpfs_path / f"{title_id}{ext}"
        else:
            current_ffpfs_path = ffpfs_path.with_suffix(ext)
        
        if args.batch:
            print(f"\n[INFO] --- Processing batch item: {title_id} ({gf.name}) ---")
            
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_pfs = Path(temp_dir) / "pfs_image.dat"
            
            # 1. Pack folder into the uncompressed PFS image
            pack_folder_uncompressed(gf, temp_pfs, mkpfs_cmd_base, mkpfs_cwd)
            
            # 2. Compress that PFS image file into the final .ffpfsc
            compress_pfs_to_ffpfsc(temp_pfs, current_ffpfs_path, mkpfs_cmd_base, mkpfs_cwd)
            
            if args.keep_pfs:
                saved_pfs_path = current_ffpfs_path.parent / f"{title_id}_nested_pfs.dat"
                print(f"[INFO] Saving intermediate PFS image to {saved_pfs_path}...")
                shutil.copy2(temp_pfs, saved_pfs_path)
                
    print("\n[SUCCESS] All operations completed successfully!")

if __name__ == "__main__":
    main()
