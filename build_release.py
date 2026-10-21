"""Cross-platform Release Packaging Script for pr0-retroconsole.
Works identically on Windows, Linux, and GitHub Actions CI.

Produces PortMaster-compliant release ZIPs:
  - pr0-retroconsole-v{VERSION}.zip
  - pr0-retroconsole.zip

Zip Structure:
  ├── pr0-retroconsole.sh       (launcher script at root)
  └── pr0-retroconsole/         (application folder)
      ├── src/
      ├── assets/
      ├── libs/
      ├── pr0.gptk
      ├── pr0_mpv_input.conf
      ├── install.sh
      ├── config.example.json
      ├── requirements.txt
      ├── README.md
      └── LICENSE
"""

from __future__ import annotations
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Ensure project root is in sys.path to read version
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.version import VERSION


def ensure_unix_lf(file_path: Path) -> None:
    """Convert CRLF or CR to Unix LF."""
    if not file_path.is_file():
        return
    try:
        content = file_path.read_bytes()
        normalized = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        file_path.write_bytes(normalized)
    except Exception as e:
        print(f"Warning: could not normalize line endings for {file_path}: {e}")


def build_release(output_dir: Path | None = None) -> tuple[Path, Path]:
    out_dir = output_dir or (PROJECT_ROOT / "release")
    out_dir.mkdir(parents=True, exist_ok=True)
    dist_dir = PROJECT_ROOT / "dist"
    staging_dir = dist_dir / "staging"
    staging_app = staging_dir / "pr0-retroconsole"

    print("=" * 60)
    print(f"  pr0-retroconsole - Packaging Release v{VERSION}")
    print("=" * 60)

    # 1. Clean previous staging
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_app.mkdir(parents=True, exist_ok=True)

    # 2. Copy launcher script to root of staging
    shutil.copy2(PROJECT_ROOT / "pr0-retroconsole.sh", staging_dir / "pr0-retroconsole.sh")
    ensure_unix_lf(staging_dir / "pr0-retroconsole.sh")

    # 3. Copy src/ (skip __pycache__ and .pyc)
    shutil.copytree(
        PROJECT_ROOT / "src",
        staging_app / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    # 4. Copy assets/ (ignore promotional/presentation graphics)
    if (PROJECT_ROOT / "assets").is_dir():
        shutil.copytree(
            PROJECT_ROOT / "assets",
            staging_app / "assets",
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                "*.pyo",
                "*presentation*",
                "*.psd",
                "*.ai",
            ),
        )

    # 5. Copy & clean libs/
    staging_libs = staging_app / "libs"
    local_libs = PROJECT_ROOT / "libs"
    if local_libs.is_dir():
        shutil.copytree(
            local_libs,
            staging_libs,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.pyd", "*.exe", "*.dist-info", "bin"),
        )
    else:
        staging_libs.mkdir(parents=True, exist_ok=True)

    # If running in CI or if requests is missing in libs/, download pure-python dependencies
    if not (staging_libs / "requests").is_dir():
        print("Installing pure-python dependencies into libs/...")
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-compile",
                    "requests",
                    "urllib3",
                    "certifi",
                    "charset-normalizer",
                    "idna",
                    "-t",
                    str(staging_libs),
                ],
                check=True,
            )
            # Remove unwanted dist-info and binaries
            for p in staging_libs.glob("*.dist-info"):
                shutil.rmtree(p, ignore_errors=True)
            for p in staging_libs.glob("*.exe"):
                p.unlink(missing_ok=True)
            for p in staging_libs.glob("*.pyd"):
                p.unlink(missing_ok=True)
            bin_dir = staging_libs / "bin"
            if bin_dir.is_dir():
                shutil.rmtree(bin_dir, ignore_errors=True)
        except Exception as e:
            print(f"Warning: pip install -t failed: {e}")

    # 6. Copy configuration and scripts
    files_to_copy = [
        "install.sh",
        "pr0.gptk",
        "pr0_mpv_input.conf",
        "config.example.json",
        "requirements.txt",
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
    ]
    for fn in files_to_copy:
        src_f = PROJECT_ROOT / fn
        if src_f.is_file():
            dest_f = staging_app / fn
            shutil.copy2(src_f, dest_f)
            if fn.endswith((".sh", ".gptk", ".conf")):
                ensure_unix_lf(dest_f)

    # 7. Ensure config.json is NEVER packaged
    staged_cfg = staging_app / "config.json"
    if staged_cfg.exists():
        staged_cfg.unlink()

    # 8. Create ZIP files
    zip_versioned = out_dir / f"pr0-retroconsole-v{VERSION}.zip"
    zip_compat = out_dir / "pr0-retroconsole.zip"

    print(f"Creating ZIP archive: {zip_versioned} ...")
    with zipfile.ZipFile(zip_versioned, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(staging_dir):
            for file in files:
                abs_p = Path(root) / file
                rel_p = abs_p.relative_to(staging_dir)
                zf.write(abs_p, arcname=str(rel_p))

    shutil.copy2(zip_versioned, zip_compat)

    # Cleanup staging
    shutil.rmtree(staging_dir, ignore_errors=True)

    size_mb = zip_versioned.stat().st_size / (1024 * 1024)
    print("=" * 60)
    print(f"  SUCCESS: Release v{VERSION} created!")
    print(f"  Package: {zip_versioned.name} ({size_mb:.2f} MB)")
    print(f"  Compat:  {zip_compat.name}")
    print("=" * 60)
    return zip_versioned, zip_compat


if __name__ == "__main__":
    build_release()
