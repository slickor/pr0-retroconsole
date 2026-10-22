#!/bin/bash
# Installation script for pr0-retroconsole

GAMEDIR=$(cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P)
cd "$GAMEDIR"

# Determine sudo helper
if [ -z "$ESUDO" ]; then
    if [ "$(id -u)" -eq 0 ]; then
        ESUDO=""
    elif command -v sudo >/dev/null 2>&1; then
        ESUDO="sudo"
    else
        ESUDO=""
    fi
fi

# Print to screen and logfile
status_msg() {
    echo "$1"
}

status_msg "========================================="
status_msg "  pr0-retroconsole: Ersteinrichtung      "
status_msg "========================================="

# 1. Check if pygame or pygame-ce with functional display support is available
has_functional_pygame() {
    python3 -c "import pygame; pygame.display.init(); drv = pygame.display.get_driver(); exit(0 if drv not in ('offscreen', 'dummy') else 1)" >/dev/null 2>&1
}

if has_functional_pygame; then
    status_msg "Funktionsfaehiges Pygame ist verfuegbar."
else
    status_msg "Pygame fehlt oder unterstuetzt keine Handheld-Displays!"
    status_msg "Installiere Pygame-CE mit nativer KMSDRM-Unterstuetzung... (WLAN aktiv halten)"

    # Method A: apt-get (Debian / Ubuntu / ArkOS on R36S)
    if command -v apt-get > /dev/null 2>&1; then
        status_msg "Aktualisiere Paketlisten (apt-get update)..."
        $ESUDO apt-get update -y
        status_msg "Installiere python3-pygame, mpv, ffmpeg via apt-get..."
        $ESUDO apt-get install -y python3-pygame python3-pip mpv ffmpeg
    fi

    # Method B: pip (prefer pygame-ce for KMSDRM/console support on muOS & embedded Linux)
    if ! has_functional_pygame; then
        status_msg "Installiere pygame-ce via pip..."
        if ! python3 -m pip --version > /dev/null 2>&1; then
            $ESUDO apt-get install -y python3-pip >/dev/null 2>&1 || python3 -m ensurepip --upgrade >/dev/null 2>&1
        fi
        # Remove legacy wheel if it had no display support
        python3 -m pip uninstall -y pygame >/dev/null 2>&1
        python3 -m pip install pygame-ce --no-cache-dir || python3 -m pip install pygame --no-cache-dir
    fi
fi

# Ensure video player (mpv / ffmpeg) is installed on Debian/Ubuntu/ArkOS
if ! command -v mpv > /dev/null 2>&1 && ! command -v ffmpeg > /dev/null 2>&1; then
    if command -v apt-get > /dev/null 2>&1; then
        status_msg "Installiere Videoplayer (mpv, ffmpeg)..."
        $ESUDO apt-get install -y mpv ffmpeg > /dev/null 2>&1
    fi
fi

# 2. Check pure-python dependencies (requests, urllib3)
if PYTHONPATH="$GAMEDIR/libs:$PYTHONPATH" python3 -c "import requests" > /dev/null 2>&1; then
    status_msg "Python-Bibliotheken (libs) verfuegbar."
else
    status_msg "Installiere ergaenzende Bibliotheken in libs/..."
    if ! python3 -m pip --version > /dev/null 2>&1; then
        python3 -m ensurepip --upgrade > /dev/null 2>&1
    fi
    python3 -m pip install --target="$GAMEDIR/libs" --no-cache-dir --no-compile -r requirements.txt
    rm -rf "$GAMEDIR/libs/bin" "$GAMEDIR/libs/Scripts" "$GAMEDIR/libs"/*.dist-info "$GAMEDIR/libs"/*.egg-info 2>/dev/null
fi

# 3. Final verification
if PYTHONPATH="$GAMEDIR/libs:$PYTHONPATH" python3 -c "import pygame, requests" > /dev/null 2>&1; then
    status_msg "Erfolg: Alle Abhaengigkeiten einsatzbereit!"
    status_msg "Starte pr0-retroconsole..."
    touch .installed
    sleep 1
    exit 0
else
    status_msg "========================================="
    status_msg "FEHLER: Pygame konnte nicht geladen werden."
    status_msg "Bitte WLAN-Verbindung pruefen."
    status_msg "Manuelle Installation via SSH (ark / ark):"
    status_msg "  sudo apt-get update"
    status_msg "  sudo apt-get install -y python3-pygame"
    status_msg "========================================="
    sleep 6
    exit 1
fi
