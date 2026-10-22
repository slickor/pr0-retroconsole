#!/usr/bin/env python3
"""SDL2 System Library Patcher for Handheld Linux (muOS, TrimUI, Knulli, ArkOS).

Many Linux handheld distributions (especially muOS and Knulli on TrimUI) use custom
hardware display drivers (such as Mali framebuffer EGL or custom KMSDRM) compiled
into the operating system's system libSDL2.so.

Official pip wheels (pygame and pygame-ce) bundle a generic 'manylinux' libSDL2.so
that lacks these hardware console drivers, causing SDL2 to fall back to 'offscreen'.

This utility:
1. Discovers the native operating system libSDL2.so (with hardware Mali/DRM support).
2. Preloads it into the Python process (RTLD_GLOBAL) before pygame loads.
3. Automatically patches/symlinks any bundled wheel libraries to use the system library.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import glob
import os
import shutil
import sys
from pathlib import Path


def find_system_sdl2() -> str | None:
    """Find the path to the operating system's native libSDL2.so."""
    if sys.platform != "linux":
        return None

    candidates: list[str] = []

    # 1. Common system paths on retro handheld CFWs (muOS, Knulli, ArkOS, CrossMix, Debian/Ubuntu)
    common_paths = [
        "/usr/lib/libSDL2-2.0.so.0",
        "/usr/lib/libSDL2.so",
        "/usr/lib/libSDL2-2.0.so",
        "/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0",
        "/usr/lib/aarch64-linux-gnu/libSDL2.so",
        "/usr/lib/arm-linux-gnueabihf/libSDL2-2.0.so.0",
        "/usr/lib/arm-linux-gnueabihf/libSDL2.so",
        "/lib/aarch64-linux-gnu/libSDL2-2.0.so.0",
        "/lib/aarch64-linux-gnu/libSDL2.so",
        "/lib/libSDL2-2.0.so.0",
        "/lib/libSDL2.so",
        "/usr/local/lib/libSDL2-2.0.so.0",
        "/usr/local/lib/libSDL2.so",
        "/opt/muos/lib/libSDL2-2.0.so.0",
        "/opt/muos/lib/libSDL2.so",
    ]
    for p in common_paths:
        if os.path.isfile(p):
            candidates.append(p)

    # 2. ctypes find_library
    try:
        name = ctypes.util.find_library("SDL2")
        if name:
            if os.path.isabs(name) and os.path.isfile(name):
                candidates.append(name)
            else:
                for base in [
                    "/usr/lib",
                    "/usr/lib/aarch64-linux-gnu",
                    "/lib",
                    "/lib/aarch64-linux-gnu",
                    "/usr/local/lib",
                    "/lib64",
                    "/usr/lib64",
                ]:
                    p = os.path.join(base, name)
                    if os.path.isfile(p):
                        candidates.append(p)
    except Exception:
        pass

    # 3. Glob system directories
    for pat in [
        "/usr/lib/libSDL2*.so*",
        "/lib/libSDL2*.so*",
        "/usr/lib/aarch64-linux-gnu/libSDL2*.so*",
        "/lib/aarch64-linux-gnu/libSDL2*.so*",
    ]:
        for match in glob.glob(pat):
            if os.path.isfile(match):
                candidates.append(match)

    # 4. Filter and prioritize:
    # Must NOT be inside a python site-packages / pygame folder
    # Must NOT be an extension library (image, ttf, mixer, gfx)
    valid: list[str] = []
    for c in candidates:
        try:
            real = os.path.realpath(c)
            fname = os.path.basename(real)
            if "site-packages" in real or "pygame" in real:
                continue
            if any(ext in fname for ext in ("image", "ttf", "mixer", "gfx", "net")):
                continue
            if real not in valid and os.path.isfile(real):
                valid.append(real)
        except Exception:
            pass

    return valid[0] if valid else None


def preload_system_sdl2() -> bool:
    """Preload system libSDL2.so into process memory with global visibility."""
    if sys.platform != "linux":
        return False

    sdl_path = find_system_sdl2()
    if not sdl_path:
        return False

    try:
        mode = ctypes.RTLD_GLOBAL
        if hasattr(os, "RTLD_NOW"):
            mode |= os.RTLD_NOW
        ctypes.CDLL(sdl_path, mode=mode)
        print(f"[pr0.sdl] Preloaded system SDL2: {sdl_path}")
        return True
    except Exception as e:
        print(f"[pr0.sdl] Warning: Failed to CDLL preload {sdl_path}: {e}")
        return False


def patch_bundled_pygame_sdl() -> bool:
    """Find any bundled libSDL2 in pygame wheels and replace with system libSDL2."""
    if sys.platform != "linux":
        return False

    sdl_path = find_system_sdl2()
    if not sdl_path:
        print("[pr0.sdl] No system libSDL2.so found to patch against.")
        return False

    patched_any = False
    try:
        import pygame

        pkg_dir = os.path.dirname(pygame.__file__)
        parent = os.path.dirname(pkg_dir)
        bundled_dirs = [
            os.path.join(parent, "pygame_ce.libs"),
            os.path.join(parent, "pygame.libs"),
            os.path.join(pkg_dir, ".libs"),
        ]

        for b_dir in bundled_dirs:
            if not os.path.isdir(b_dir):
                continue
            for fname in os.listdir(b_dir):
                # Target the core libSDL2 file, but NOT image/ttf/mixer
                if fname.startswith("libSDL2-2") and not any(
                    ext in fname for ext in ("image", "ttf", "mixer", "gfx", "net")
                ):
                    target_file = os.path.join(b_dir, fname)
                    try:
                        if os.path.islink(target_file):
                            curr_target = os.path.realpath(target_file)
                            if curr_target == sdl_path:
                                print(f"[pr0.sdl] Bundled lib already linked: {target_file} -> {sdl_path}")
                                patched_any = True
                                continue
                            os.unlink(target_file)
                        else:
                            backup = target_file + ".orig"
                            if not os.path.exists(backup):
                                os.rename(target_file, backup)
                            else:
                                os.remove(target_file)

                        try:
                            os.symlink(sdl_path, target_file)
                            print(f"[pr0.sdl] Symlinked bundled SDL2: {target_file} -> {sdl_path}")
                        except OSError:
                            shutil.copyfile(sdl_path, target_file)
                            print(f"[pr0.sdl] Copied system SDL2 over bundled: {target_file} -> {sdl_path}")
                        patched_any = True
                    except Exception as err:
                        print(f"[pr0.sdl] Warning: could not patch {target_file}: {err}")
    except Exception as e:
        print(f"[pr0.sdl] Error inspecting pygame bundled libs: {e}")

    return patched_any


def main() -> None:
    parser = argparse.ArgumentParser(description="SDL2 System Library Patcher for Handheld Linux")
    parser.add_argument("--find-only", action="store_true", help="Print path to system libSDL2.so and exit")
    parser.add_argument("--patch", action="store_true", help="Patch bundled pygame wheel libraries")
    parser.add_argument("--preload", action="store_true", help="Preload system libSDL2 and test import")
    args = parser.parse_args()

    if args.find_only:
        p = find_system_sdl2()
        if p:
            print(p)
    elif args.patch:
        patch_bundled_pygame_sdl()
    elif args.preload:
        preload_system_sdl2()
    else:
        p = find_system_sdl2()
        print("Detected system libSDL2:", p)
        if p:
            patch_bundled_pygame_sdl()


if __name__ == "__main__":
    main()
