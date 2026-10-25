"""QR Code Generator utility for pr0-retroconsole.

Sprache: Deutsch (pr0-Amtssprache) • Architektur: 100% zertifizierter Vibecode.
Generates high-contrast Pygame surfaces for display on handheld screens.
Uses pure-Python qrcodegen with zero external dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pygame

# Ensure libs/ directory is accessible
_LIBS_DIR = Path(__file__).parent.parent / "libs"
if str(_LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(_LIBS_DIR))

try:
    from qrcodegen import QrCode
except ImportError:
    QrCode = None


def generate_qr_surface(
    text: str,
    target_size: int = 180,
    border: int = 2,
    fg_color: tuple[int, int, int] = (0, 0, 0),
    bg_color: tuple[int, int, int] = (255, 255, 255),
) -> pygame.Surface | None:
    """Generate a crisp Pygame Surface with the encoded QR code.

    :param text: The URL or text string to encode.
    :param target_size: Desired square width & height in pixels.
    :param border: Quiet zone margin around the QR code in modules.
    :param fg_color: Foreground color (default black).
    :param bg_color: Background color (default white).
    :return: pygame.Surface or None if qrcodegen is unavailable.
    """
    if QrCode is None:
        return None

    try:
        qr = QrCode.encode_text(text, QrCode.Ecc.MEDIUM)
        qr_modules = qr.get_size()
        total_modules = qr_modules + border * 2

        module_px = max(1, target_size // total_modules)
        surf_size = total_modules * module_px

        surf = pygame.Surface((surf_size, surf_size))
        surf.fill(bg_color)

        for y in range(qr_modules):
            for x in range(qr_modules):
                if qr.get_module(x, y):
                    rx = (x + border) * module_px
                    ry = (y + border) * module_px
                    pygame.draw.rect(surf, fg_color, (rx, ry, module_px, module_px))

        if surf_size != target_size:
            surf = pygame.transform.scale(surf, (target_size, target_size))

        return surf
    except Exception:
        return None
