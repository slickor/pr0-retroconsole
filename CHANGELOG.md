# Changelog

Alle nennenswerten Änderungen an **pr0-retroconsole** werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/)
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

---

## [0.3.7] - 2026-10-21

### Hinzugefügt
- **Dokumentations-Grafiken in `docs/images/`:** Präsentationsbanner und Infografik-Poster werden nun auf der GitHub-Landingpage und in der `README.md` gerendert, ohne das Release-ZIP aufzublähen.
- **`CHANGELOG.md`:** Vollständiges Changelog aller Versionen im Keep-a-Changelog Format.
- **Erweiterte Dokumentation:** `README.md` überarbeitet mit Shields.io Badges, ausklappbarem Feature-Poster und detaillierter Tastenmatrix.

## [0.3.6] - 2026-10-21

### Geändert
- **Release-Archiv um 75% verkleinert:** Die Marketing- und Präsentationsgrafiken wurden aus dem Installationspaket entfernt und in `docs/images/` ausgelagert. Das Release-ZIP schrumpft von 3,14 MB auf schlanke **0,77 MB**.
- **Build-Filter:** `build_release.py` ignoriert beim Paketieren von `assets/` automatisch alle Präsentationsgrafiken, Photoshop-Dateien und temporären Assets.

### Behoben
- **Rahmenüberläufe in Infografiken:** In `create_presentation_image.py` wurde eine dynamische Rechtsbündigung (`right_x`) für alle Pills und Badges eingeführt.
  - Das Badge *TrimUI Smart Pro* steht nicht mehr rechts über den 3D-Render-Rahmen hinaus (35 px / 25 px definierter Innenabstand).
  - Feature-Tags wie *NO COOKIE HASSLE* und *GAMEPAD READY* halten nun verlässlich 20 px Innenabstand zur rechten Begrenzung der Feature-Karten.
  - Das Badge *100% OPEN SOURCE* im Header schließt bündig mit der Inhaltsbegrenzung (1530 px) ab.
  - Versions-Badges in Postern und Bannern werden jetzt dynamisch aus `src/version.py` gespeist.

---

## [0.3.5] - 2026-10-20

### Hinzugefügt
- **Videosound in der Post-Vorschau:** Videos laufen in der Post-Ansicht (wo auch Kommentare, Tags und Benis sichtbar sind) nun synchron mit Begleit-Audio über einen leichtgewichtigen Hintergrundprozess.
- **Einstellungsoption `Sound in Vorschau`:** In den Einstellungen (`X`) kann der Vorschau-Ton bei Bedarf deaktiviert werden (Standard: *Aktiviert*).
- **Vollbild-Hinweis:** Tastenhinweis im Footer und Badge über dem Vorschau-Video auf `[A] Vollbild` aktualisiert.

### Behoben
- **Vollbild-Beenden mit B (`mpv`):** Parameter `--terminal=no` durch `--input-terminal=yes`, `--input-gamepad=yes` und `--really-quiet` ersetzt, sodass Tasten-Events vom `gptokeyb`-Dienst auf Handhelds (TrimUI Smart Pro, ArkOS) nicht mehr verworfen werden.
- **Doppelte Absicherung beim Videobeenden:** Python-Event-Watcher in `VideoPlayer.play()` fängt `B` und `ESC` als Ausstiegsbefehl ab, falls das Handheld-OS den DRM-KMS-Framebuffer nicht direkt an `mpv` weiterreicht.
- **Gamepad-Mappings in `pr0_mpv_input.conf`:** Vollständige Unterstützung für `GAMEPAD_ACTION_RIGHT`, `GAMEPAD_BACK`, `BTN_EAST`, `BTN_B` und Standard-Tastaturbelegungen.

---

## [0.3.4] - 2026-10-20

### Hinzugefügt
- **L2 / R2 Schnellumschaltung (Beliebt 🔁 Neu):** Tasten 9 und 10 (L2/R2) in `src/input.py` und `pr0.gptk` entkoppelt und als Schnellwechsel zwischen *Beliebt* und *Neu* belegt.
- **Automatische Release-Pipeline:** Neues PowerShell-Tooling `push.ps1` und GitHub Actions Workflow (`.github/workflows/release.yml`), die bei jedem Git-Push automatisch ein offizielles GitHub Release mit PortMaster-konformem ZIP-Archiv generieren.

---

## [0.3.3] - 2026-10-19

### Behoben
- **ALSA-Lock für Vollbild-Audio:** `pygame.mixer` wird vor dem Starten externer Videoplayer mit `pygame.mixer.quit()` freigegeben, sodass `mpv` exklusiven Zugriff auf das ALSA-Audiogerät auf Handhelds erhält.
- **TrimUI Smart Pro Video-Ruckeln:** Allwinner A133 Cedrus Hardware-Dekoder-Bug behoben (B-Frames wurden in DTS statt PTS ausgegeben, was Vor- und Zurückspringen erzeugte). Durch softwareseitiges Dekodieren (`--hwdec=no`) laufen Videos auf dem Quad-Core Cortex-A53 flüssig mit 60 FPS.

---

## [0.3.2] - 2026-10-19

### Hinzugefügt
- **Originalgetreuer pr0.app Web-Header:** Headerleiste mit pr0-Logo, Suchfeld-Attrappe, Benis-Score, aktuellem Benutzer und Rang-Farben (Schwuchtel, Neuschwuchtel, Altschwuchtel, Moderator, Admin).
- **Theming-Engine:** Integrierter Farbschema-Wechsler in den Einstellungen für Themes (*pr0 Dark*, *OLED Schwarz*, *Nord*, *Gruvbox*, *Retro Terminal*) und Akzentfarben (*pr0 Orange*, *SFW Grün*, *pr0 Blau*, *Lila*, *Cyberpunk Pink*).

---

## [0.3.1] - 2026-10-18

### Hinzugefügt
- **QR-Code Express-Login:** Lokaler Authentifizierungs-Server (`auth_server.py`), der einen QR-Code auf dem Handheld anzeigt. Durch Scannen mit dem Smartphone kann das Login ohne manuelles Kopieren von Cookies auf die SD-Karte erfolgen.
- **Virtuelle Bildschirmtastatur:** Fallback-Tastatur für die Direkteingabe von Benutzername, Passwort und Captcha auf dem Handheld.

---

## [0.3.0] - 2026-10-18

### Hinzugefügt
- **Post-Detailansicht:** Vollständige Post-Ansicht mit Bild-/Videodarstellung, Tags, Uploader, Benis-Punkten und Zeitangaben.
- **Hierarchischer Kommentarbaum:** Vollständig scrollbarer Kommentarbaum mit baumartiger Einrückung, Autoren-Rängen und Bewertungsanzeige.
- **Tapeten-Erkennung:** Automatische Anpassung langer Bilder auf Inhaltsbreite mit flüssigem vertikalem Scrollen.

---

## [0.2.0] - 2026-10-17

### Hinzugefügt
- **Handheld-Input-Manager:** Optimierte D-Pad- und Analog-Stick-Unterstützung mit Hold-to-Scroll und dynamischer Beschleunigung.
- **Umschaltbares Button-Layout:** Unterstützung für Standard (Nintendo: A=Öffnen, B=Zurück) und invertiert (Xbox: B=Öffnen, A=Zurück).
- **Integrierter Tasten-Test:** Diagnose-Screen zur Überprüfung von Knöpfen, Achsen und `gptokeyb`-Events direkt am Gerät.

---

## [0.1.0] - 2026-10-16

### Hinzugefügt
- Initiale Version von **pr0-retroconsole**.
- Asynchroner Thumbnail-Grid-Feed mit Endlos-Scrollen für pr0gramm.com.
- Unterstützung für R36S (ArkOS, 640x480) und TrimUI Smart Pro (CrossMix OS, 1280x720).
- Pure-Python Abhängigkeiten und PortMaster-Startskript (`pr0-retroconsole.sh`).
