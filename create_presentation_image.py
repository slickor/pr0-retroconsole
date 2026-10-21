"""Generator script for pr0-retroconsole presentation images for pr0gramm.com.
Creates:
1. pr0-presentation-poster.png (1600x2400 high-res infographic poster)
2. pr0-presentation-banner.png (1920x1080 widescreen showcase banner)
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.version import VERSION

# Paths
SOURCE_RENDER = Path(r"C:\Users\Philipp\.gemini\antigravity\brain\d316afdf-bb51-41fd-aaae-10a6f05e5073\r36s_trimui_pr0gramm_consoles_1792434684236.jpg")
OUTPUT_DIR = PROJECT_ROOT
DOCS_IMAGES_DIR = PROJECT_ROOT / "docs" / "images"
DOCS_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

POSTER_PATH = OUTPUT_DIR / "pr0-presentation-poster.png"
BANNER_PATH = OUTPUT_DIR / "pr0-presentation-banner.png"

# Color Palette (pr0gramm Theme)
COLOR_BG = (18, 18, 20, 255)            # #121214 deep dark
COLOR_CARD_BG = (26, 26, 30, 255)       # #1a1a1e card surface
COLOR_CARD_BORDER = (45, 45, 52, 255)   # #2d2d34 subtle outline
COLOR_ORANGE = (238, 77, 46, 255)       # #ee4d2e pr0 orange
COLOR_ORANGE_DARK = (160, 45, 25, 255)
COLOR_GREEN = (92, 184, 92, 255)        # #5cb85c SFW / success
COLOR_BLUE = (27, 121, 195, 255)        # #1b79c3 pr0 blue
COLOR_TEXT_WHITE = (245, 245, 248, 255)
COLOR_TEXT_GRAY = (165, 165, 175, 255)
COLOR_TEXT_MUTED = (110, 110, 120, 255)

def get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load font with size, fallback to Windows or default."""
    candidates = []
    if name == "bold":
        candidates = [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            r"assets\fonts\Inter-Regular.ttf",
        ]
    elif name == "semibold":
        candidates = [
            r"C:\Windows\Fonts\segoeuisb.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"assets\fonts\Inter-Regular.ttf",
        ]
    elif name == "mono":
        candidates = [
            r"assets\fonts\FiraCode-Regular.ttf",
            r"C:\Windows\Fonts\consola.ttf",
        ]
    else:
        candidates = [
            r"C:\Windows\Fonts\segoeui.ttf",
            r"assets\fonts\Inter-Regular.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ]

    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_pill(
    draw: ImageDraw.ImageDraw,
    x: int | None,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    bg_color: tuple,
    text_color: tuple,
    border_color: tuple = None,
    pad_x: int = 14,
    pad_y: int = 6,
    right_x: int | None = None,
) -> tuple[int, int]:
    """Draw a rounded badge/pill with optional right-alignment (right_x) to prevent boundary overflow."""
    bbox = font.getbbox(text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pw = tw + pad_x * 2
    ph = th + pad_y * 2
    draw_x = (right_x - pw) if right_x is not None else (x if x is not None else 0)
    draw.rounded_rectangle(
        (draw_x, y, draw_x + pw, y + ph),
        radius=ph // 2,
        fill=bg_color,
        outline=border_color,
        width=1 if border_color else 0,
    )
    draw.text((draw_x + pad_x, y + pad_y - bbox[1]), text, font=font, fill=text_color)
    return pw, ph

def create_poster():
    W, H = 1600, 2400
    im = Image.new("RGBA", (W, H), COLOR_BG)
    draw = ImageDraw.Draw(im)

    # 1. Subtle Background Accents (Glow circles)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    # Orange ambient glow behind 3D render
    glow_draw.ellipse((W//2 - 600, 300, W//2 + 600, 1100), fill=(238, 77, 46, 35))
    # Bottom blue/orange subtle glow
    glow_draw.ellipse((-200, 1800, 600, 2500), fill=(27, 121, 195, 20))
    glow_draw.ellipse((W - 600, 1900, W + 200, 2600), fill=(238, 77, 46, 25))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    im = Image.alpha_composite(im, glow)
    draw = ImageDraw.Draw(im)

    # Fonts
    font_title = get_font("bold", 58)
    font_subtitle = get_font("regular", 25)
    font_badge = get_font("bold", 17)
    font_section = get_font("bold", 30)
    font_card_title = get_font("bold", 24)
    font_card_desc = get_font("regular", 18)
    font_card_desc_bold = get_font("semibold", 18)
    font_footer = get_font("regular", 19)
    font_mono = get_font("mono", 17)

    # -------------------------------------------------------------
    # HEADER SECTION
    # -------------------------------------------------------------
    curr_y = 50

    # Badges (ArkOS, CrossMix-OS, Knulli, Release, Open Source)
    p1_w, p1_h = draw_pill(draw, 70, curr_y, "PORTMASTER & ARKOS", font_badge, (20, 45, 25, 255), COLOR_GREEN, (40, 110, 50, 255))
    p2_w, p2_h = draw_pill(draw, 70 + p1_w + 12, curr_y, "CROSSMIX-OS", font_badge, (20, 35, 55, 255), (100, 175, 255, 255), (40, 80, 130, 255))
    p3_w, p3_h = draw_pill(draw, 70 + p1_w + 12 + p2_w + 12, curr_y, "KNULLI", font_badge, (38, 22, 52, 255), (200, 145, 255, 255), (95, 45, 135, 255))
    p4_w, p4_h = draw_pill(draw, 70 + p1_w + 12 + p2_w + 12 + p3_w + 12, curr_y, f"RELEASE v{VERSION}", font_badge, (50, 25, 20, 255), COLOR_ORANGE, COLOR_ORANGE_DARK)
    draw_pill(draw, None, curr_y, "100% OPEN SOURCE", font_badge, (30, 30, 35, 255), COLOR_TEXT_GRAY, (60, 60, 70, 255), right_x=W - 70)

    curr_y += 55

    # Main Brand Title: [ pr0 ]-retroconsole
    b_pr0 = font_title.getbbox("pr0")
    w_pr0 = b_pr0[2] - b_pr0[0]
    h_pr0 = b_pr0[3] - b_pr0[1]

    pad_x = 18
    pad_y = 8
    box_w = w_pr0 + pad_x * 2
    box_h = h_pr0 + pad_y * 2

    # Draw rounded orange box for "pr0"
    draw.rounded_rectangle((70, curr_y, 70 + box_w, curr_y + box_h), radius=12, fill=COLOR_ORANGE)

    # Draw "pr0" centered inside box with generous margin
    text_x = 70 + pad_x - b_pr0[0]
    text_y = curr_y + pad_y - b_pr0[1]
    draw.text((text_x, text_y), "pr0", font=font_title, fill=(255, 255, 255, 255))

    # Draw "-retroconsole" immediately after box
    rest_x = 70 + box_w + 8
    draw.text((rest_x, text_y), "-retroconsole", font=font_title, fill=COLOR_TEXT_WHITE)

    # Subtitle
    curr_y += box_h + 16
    sub_text = "Die native pr0gramm-App für Handheld-Konsolen • R36S, TrimUI Smart Pro, ArkOS, CrossMix, Knulli & Co."
    draw.text((70, curr_y), sub_text, font=font_subtitle, fill=COLOR_TEXT_GRAY)

    curr_y += 48

    # -------------------------------------------------------------
    # 3D RENDER SECTION (Hero Graphic)
    # -------------------------------------------------------------
    if SOURCE_RENDER.is_file():
        render_img = Image.open(SOURCE_RENDER).convert("RGBA")
        # Target render dimensions: 1460 x 820
        target_rw, target_rh = 1460, 820
        render_resized = render_img.resize((target_rw, target_rh), Image.Resampling.LANCZOS)

        # Create rounded mask
        mask = Image.new("L", (target_rw, target_rh), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, target_rw, target_rh), radius=20, fill=255)

        render_x = (W - target_rw) // 2
        render_y = curr_y

        # Draw frame / border glow
        draw.rounded_rectangle((render_x - 3, render_y - 3, render_x + target_rw + 3, render_y + target_rh + 3), 
                               radius=23, outline=(238, 77, 46, 160), width=3)
        draw.rounded_rectangle((render_x - 8, render_y - 8, render_x + target_rw + 8, render_y + target_rh + 8), 
                               radius=28, outline=(238, 77, 46, 50), width=2)

        im.paste(render_resized, (render_x, render_y), mask)

        # Overlay labels on the render
        # Label 1: R36S
        draw_pill(draw, render_x + 35, render_y + 35, "R36S  •  3.5\" 4:3  •  ArkOS", font_badge, 
                  (15, 15, 18, 220), COLOR_TEXT_WHITE, COLOR_ORANGE, pad_x=16, pad_y=8)
        # Label 2: TrimUI Smart Pro
        draw_pill(draw, None, render_y + 35, "TrimUI Smart Pro  •  5.0\" 16:9  •  CrossMix-OS", font_badge, 
                  (15, 15, 18, 220), COLOR_TEXT_WHITE, COLOR_ORANGE, pad_x=16, pad_y=8, right_x=render_x + target_rw - 35)

        curr_y += target_rh + 45

    # -------------------------------------------------------------
    # FEATURES TITLE
    # -------------------------------------------------------------
    draw.text((70, curr_y), "Alle Highlights & Features im Überblick", font=font_section, fill=COLOR_TEXT_WHITE)
    draw.line((70, curr_y + 44, 250, curr_y + 44), fill=COLOR_ORANGE, width=3)
    curr_y += 65

    # -------------------------------------------------------------
    # 6 FEATURE CARDS (2 Columns x 3 Rows)
    # -------------------------------------------------------------
    col_w = 715
    col_h = 245
    col_gap_x = 30
    col_gap_y = 22

    cards = [
        {
            "num": "01",
            "title": "Optimierte Handheld-Steuerung",
            "tag": "GAMEPAD READY",
            "points": [
                ("Native D-Pad & Analog-Stick Unterstützung", True),
                ("Fluid Hold-to-Scroll mit dynamischer Beschleunigung", False),
                ("Nintendo- (B/A) & Xbox-Layout (A/B) umschaltbar", False),
                ("L1 / R1 Schultertasten für Filter & schnelles Voten", True),
            ]
        },
        {
            "num": "02",
            "title": "Videos & Audio ohne Ruckeln",
            "tag": "MPV POWERED",
            "points": [
                ("Integrierter Videoplayer via mpv mit vollem Sound", True),
                ("60 FPS flüssig (B-Frame Reordering Bug behoben!)", True),
                ("Inline-Vorschau im Feed + Fullscreen auf Knopfdruck", False),
                ("Automatischer Netzwerk-Puffer & Offline-Wiedergabe", False),
            ]
        },
        {
            "num": "03",
            "title": "Original pr0.app Look & Header",
            "tag": "AUTHENTIC UI",
            "points": [
                ("Detailgetreuer Header mit Logo, Suche & Filtern", True),
                ("Schnellumschaltung: Beliebt, Neu und Top-Feed", False),
                ("Vollständiger Filter-Support: SFW, NSFW, NSFL & Alle", True),
                ("Tags, Benis-Score und scrollbarer Kommentarbaum", False),
            ]
        },
        {
            "num": "04",
            "title": "QR-Code Express-Login",
            "tag": "NO COOKIE HASSLE",
            "points": [
                ("Nie wieder Cookies manuell auf die SD-Karte kopieren!", True),
                ("Handheld zeigt QR-Code -> mit Smartphone scannen", True),
                ("Integrierter lokaler Auth-Server erledigt den Login", False),
                ("Login bleibt bei Updates dauerhaft erhalten", False),
            ]
        },
        {
            "num": "05",
            "title": "Smarter RAM- & Disk-Cache",
            "tag": "HIGH SPEED",
            "points": [
                ("Asynchrones Multi-Thread Vorladen von Bildern & MP4s", True),
                ("Sofortiges Umschalten von Remote-Stream auf Disk-Cache", False),
                ("Schont mobilen Hotspot & Akkulaufzeit unterwegs", True),
                ("Zero CPU-Waste: Keine unnötigen Bildskalierungen", False),
            ]
        },
        {
            "num": "06",
            "title": "Plug & Play Installation",
            "tag": "EASY SETUP",
            "points": [
                ("ZIP-Archiv direkt auf die SD-Karte in /roms/ports/ entpacken", True),
                ("Kompatibel mit R36S, TrimUI, ArkOS, CrossMix, Knulli uvm.", True),
                ("Alle benötigten Bibliotheken (pure-python requests) an Bord", False),
                ("Konfiguration (config.json) wird bei Updates nicht überschrieben", False),
            ]
        },
    ]

    for idx, card in enumerate(cards):
        row = idx // 2
        col = idx % 2
        cx = 70 + col * (col_w + col_gap_x)
        cy = curr_y + row * (col_h + col_gap_y)

        # Card Background & subtle border
        draw.rounded_rectangle((cx, cy, cx + col_w, cy + col_h), radius=16, fill=COLOR_CARD_BG, outline=COLOR_CARD_BORDER, width=1)
        # Top-left accent pill/border
        draw.rounded_rectangle((cx, cy, cx + col_w, cy + 4), radius=2, fill=(238, 77, 46, 120))

        # Number Badge
        draw_pill(draw, cx + 22, cy + 16, card["num"], font_mono, (45, 22, 18, 255), COLOR_ORANGE, (120, 45, 30, 255), pad_x=8, pad_y=4)

        # Title
        draw.text((cx + 70, cy + 18), card["title"], font=font_card_title, fill=COLOR_TEXT_WHITE)

        # Tag (aligned 20px from right card border to prevent overflow)
        draw_pill(draw, None, cy + 16, card["tag"], font_mono, (35, 35, 42, 255), COLOR_ORANGE, pad_x=10, pad_y=4, right_x=cx + col_w - 20)

        # Bullet Points
        py = cy + 62
        for pt_text, is_highlight in card["points"]:
            bullet_col = COLOR_ORANGE if is_highlight else COLOR_TEXT_MUTED
            text_col = COLOR_TEXT_WHITE if is_highlight else COLOR_TEXT_GRAY
            f = font_card_desc_bold if is_highlight else font_card_desc

            # Bullet dot
            draw.ellipse((cx + 26, py + 8, cx + 32, py + 14), fill=bullet_col)
            draw.text((cx + 42, py), pt_text, font=f, fill=text_col)
            py += 40

    curr_y += 3 * (col_h + col_gap_y) + 30

    # -------------------------------------------------------------
    # FOOTER BAR
    # -------------------------------------------------------------
    footer_h = 100
    footer_y = H - footer_h - 40
    draw.rounded_rectangle((70, footer_y, W - 70, footer_y + footer_h), radius=16, fill=(22, 22, 26, 255), outline=COLOR_CARD_BORDER, width=1)

    # Orange highlight indicator on left
    draw.rounded_rectangle((70, footer_y, 76, footer_y + footer_h), radius=3, fill=COLOR_ORANGE)

    draw.text((100, footer_y + 22), f"Open Source auf GitHub • PortMaster Release v{VERSION}", font=font_card_title, fill=COLOR_TEXT_WHITE)
    draw.text((100, footer_y + 58), "Entwickelt für die Fliesentisch-Elite • Benis, Feedback & Pull Requests willkommen!", font=font_footer, fill=COLOR_TEXT_GRAY)

    draw_pill(draw, None, footer_y + 30, "JETZT TESTEN >>", font_badge, COLOR_ORANGE, (255, 255, 255, 255), pad_x=22, pad_y=12, right_x=W - 70 - 30)

    im.save(POSTER_PATH, "PNG", quality=95)
    im.save(DOCS_IMAGES_DIR / "pr0-presentation-poster.png", "PNG", quality=95)
    print(f"Poster successfully created at {POSTER_PATH} and {DOCS_IMAGES_DIR / 'pr0-presentation-poster.png'}")


def create_banner():
    """Create 1920x1080 widescreen presentation banner."""
    W, H = 1920, 1080
    im = Image.new("RGBA", (W, H), COLOR_BG)
    draw = ImageDraw.Draw(im)

    # Glows
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((1000, 200, 1900, 900), fill=(238, 77, 46, 40))
    glow_draw.ellipse((-100, 600, 700, 1200), fill=(27, 121, 195, 25))
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    im = Image.alpha_composite(im, glow)
    draw = ImageDraw.Draw(im)

    font_title = get_font("bold", 62)
    font_sub = get_font("regular", 26)
    font_badge = get_font("bold", 18)
    font_item_title = get_font("bold", 22)
    font_item_desc = get_font("regular", 18)
    font_footer = get_font("mono", 17)

    # Left Column: Information (Width 850px)
    curr_y = 70
    p1_w, p1_h = draw_pill(draw, 75, curr_y, "PORTMASTER & ARKOS", font_badge, (20, 45, 25, 255), COLOR_GREEN, (40, 110, 50, 255))
    p2_w, p2_h = draw_pill(draw, 75 + p1_w + 10, curr_y, "CROSSMIX-OS", font_badge, (20, 35, 55, 255), (100, 175, 255, 255), (40, 80, 130, 255))
    p3_w, p3_h = draw_pill(draw, 75 + p1_w + 10 + p2_w + 10, curr_y, "KNULLI", font_badge, (38, 22, 52, 255), (200, 145, 255, 255), (95, 45, 135, 255))
    draw_pill(draw, 75 + p1_w + 10 + p2_w + 10 + p3_w + 10, curr_y, f"v{VERSION} RELEASE", font_badge, (50, 25, 20, 255), COLOR_ORANGE, COLOR_ORANGE_DARK)

    curr_y += 62
    # Unified Brand Title: [ pr0 ]-retroconsole
    b_pr0 = font_title.getbbox("pr0")
    w_pr0 = b_pr0[2] - b_pr0[0]
    h_pr0 = b_pr0[3] - b_pr0[1]

    pad_x = 20
    pad_y = 8
    box_w = w_pr0 + pad_x * 2
    box_h = h_pr0 + pad_y * 2

    # Draw rounded orange box for "pr0"
    draw.rounded_rectangle((75, curr_y, 75 + box_w, curr_y + box_h), radius=14, fill=COLOR_ORANGE)

    # Draw "pr0" centered inside box with generous margin
    text_x = 75 + pad_x - b_pr0[0]
    text_y = curr_y + pad_y - b_pr0[1]
    draw.text((text_x, text_y), "pr0", font=font_title, fill=(255, 255, 255, 255))

    # Draw "-retroconsole" immediately after box
    rest_x = 75 + box_w + 8
    draw.text((rest_x, text_y), "-retroconsole", font=font_title, fill=COLOR_TEXT_WHITE)

    curr_y += box_h + 16
    draw.text((75, curr_y), "Das pr0gramm für deinen Retro-Handheld!", font=font_sub, fill=COLOR_TEXT_GRAY)

    curr_y += 48

    # Features List on Left
    features = [
        ("01", "Volle Handheld-Steuerung", "D-Pad, Sticks, Hold-to-Scroll & Nintendo-/Xbox-Layout Switch"),
        ("02", "60 FPS Videos & Sound", "Hardware-gestützter mpv-Player, B-Frame Fix & Inline-Vorschau"),
        ("03", "Authentischer pr0.app Look", "Web-Header, Schnellumschaltung (Beliebt/Neu) & SFW/NSFW/NSFL Filter"),
        ("04", "QR-Code Express-Login", "Scannen mit Smartphone genügt – kein Cookie-Gefummel auf SD!"),
        ("05", "High-Speed Cache", "Asynchrones Vorladen im RAM & auf Disk für flüssiges Durchscrollen"),
        ("06", "Plug & Play Installation", "Einfach ZIP nach /roms/ports/ entpacken & direkt loslegen"),
    ]

    for num, title, desc in features:
        draw_pill(draw, 75, curr_y - 2, num, font_footer, (45, 22, 18, 255), COLOR_ORANGE, (120, 45, 30, 255), pad_x=6, pad_y=2)
        draw.text((120, curr_y - 2), title, font=font_item_title, fill=COLOR_TEXT_WHITE)
        draw.text((120, curr_y + 26), desc, font=font_item_desc, fill=COLOR_TEXT_GRAY)
        curr_y += 66

    # Bottom Footer info
    footer_y = H - 85
    draw.text((75, footer_y), "Open Source auf GitHub • Pure Python & SDL2 • Für R36S, TrimUI Smart Pro, ArkOS, CrossMix, Knulli & Co.", 
              font=font_footer, fill=COLOR_TEXT_MUTED)

    # Right Column: 3D Render (Width 940px, Height 530px or larger)
    if SOURCE_RENDER.is_file():
        render_img = Image.open(SOURCE_RENDER).convert("RGBA")
        target_rw, target_rh = 940, 528
        render_resized = render_img.resize((target_rw, target_rh), Image.Resampling.LANCZOS)

        mask = Image.new("L", (target_rw, target_rh), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, target_rw, target_rh), radius=22, fill=255)

        rx = W - target_rw - 50
        ry = 180

        draw.rounded_rectangle((rx - 3, ry - 3, rx + target_rw + 3, ry + target_rh + 3), radius=25, outline=COLOR_ORANGE, width=3)
        draw.rounded_rectangle((rx - 8, ry - 8, rx + target_rw + 8, ry + target_rh + 8), radius=30, outline=(238, 77, 46, 60), width=2)
        im.paste(render_resized, (rx, ry), mask)

        # Labels
        draw_pill(draw, rx + 25, ry + 25, "R36S (ArkOS)", font_badge, (15, 15, 18, 220), COLOR_TEXT_WHITE, COLOR_ORANGE, pad_x=14, pad_y=6)
        draw_pill(draw, None, ry + 25, "TrimUI Smart Pro (CrossMix)", font_badge, (15, 15, 18, 220), COLOR_TEXT_WHITE, COLOR_ORANGE, pad_x=14, pad_y=6, right_x=rx + target_rw - 25)

        # Bottom card under render
        card_y = ry + target_rh + 35
        card_w = target_rw
        card_h = 190
        draw.rounded_rectangle((rx, card_y, rx + card_w, card_y + card_h), radius=16, fill=COLOR_CARD_BG, outline=COLOR_CARD_BORDER, width=1)
        draw.rounded_rectangle((rx, card_y, rx + card_w, card_y + 4), radius=2, fill=COLOR_ORANGE)

        draw.text((rx + 30, card_y + 25), "Bereit für die Hosentasche?", font=font_item_title, fill=COLOR_TEXT_WHITE)
        draw.text((rx + 30, card_y + 65), f"Das Release v{VERSION} bringt perfekten Videosound, 60 FPS ohne Frame-Jumps,", font=font_item_desc, fill=COLOR_TEXT_GRAY)
        draw.text((rx + 30, card_y + 95), "die originalgetreue pr0.app Navigationsleiste und QR-Code Login.", font=font_item_desc, fill=COLOR_TEXT_GRAY)
        draw.text((rx + 30, card_y + 135), "Feedback, Benis & Pull Requests auf GitHub jederzeit willkommen!", font=font_item_desc, fill=COLOR_ORANGE)

    im.save(BANNER_PATH, "PNG", quality=95)
    im.save(DOCS_IMAGES_DIR / "pr0-presentation-banner.png", "PNG", quality=95)
    print(f"Banner successfully created at {BANNER_PATH} and {DOCS_IMAGES_DIR / 'pr0-presentation-banner.png'}")

if __name__ == "__main__":
    create_poster()
    create_banner()
