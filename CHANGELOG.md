# Changelog

Alle nennenswerten Änderungen an **pr0-retroconsole** werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/)
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

---

## [0.3.12] - 2026-10-21

### Behoben
- **Kritischer Video-Crash mit `ffplay` auf Handhelds (z. B. R36S) behoben:**
  - Laut Geräte-Log (`log.txt`) stürzte `ffplay` sofort mit Exit-Code 1 ab (`Failed to set value '-window_title' for option 'autoexit=0': Option not found`).
  - Der ungültige Parameter `-autoexit=0` wurde entfernt (in `ffplay` ist `-autoexit` ein reines Boolean-Flag).
  - Auf Handhelds startet `ffplay` nun sauber im echten Vollbildmodus (`-fs`, `-noborder`, `-loop 0`), sodass Videos auf dem R36S und anderen Linux-Handhelds ohne `mpv` direkt abgespielt werden.
  - Fehlerausgaben des internen FFmpeg-Streamers werden nun für besseres Debugging im Log erfasst.

---

## [0.3.11] - 2026-10-21

### Entfernt
- **Obsoleten `[X]`-Hinweis im Header entfernt:**
  - Die Beschriftung `[X]` ganz oben rechts im Header stammte noch aus Versionen, in denen die Taste X das Setup öffnete. Da Einstellungen nun einheitlich über `START` aufgerufen werden (und im Footer dokumentiert sind), wurde das Element entfernt. Der Header wirkt dadurch deutlich aufgeräumter.

---

## [0.3.10] - 2026-10-21

### Hinzugefügt
- **Bereinigte Tastenbelegung & START für Einstellungen:**
  - `START` öffnet nun zuverlässig auf allen Handhelds und Controllern die Einstellungen (`BTN_START` auf Gamepads, `F1` via gptokeyb).
  - Im Einstellungsmenü kann mit `START` oder `B` gespeichert und direkt zum Grid zurückgekehrt werden.
  - Doppelte Belegung von `Y` im Grid entfernt: `Y` schaltet nicht mehr versehentlich zwischen "Neu" und "Beliebt" um (dies erfolgt nun sauber über `L2` / `R2` bzw. über die interaktive Header-Navigation). Im Header dient `Y` weiterhin der schnellen Solo-Flag-Auswahl.
  - Taste `X` öffnet nicht mehr die Einstellungen.
- **Neue Einstellung "Nur Bilder laden" (Videos ausblenden):**
  - Neuer Umschalter in den Einstellungen: Schaltet wahlweise alle Medien frei oder filtert Videos (`.mp4`, `.webm`) vollständig aus.
  - Ideal für Handhelds mit geringerer Rechenleistung oder zur Reduzierung des Datenverbrauchs unterwegs.
- **Sauberes Beenden über "App beenden":**
  - Neuer Menüpunkt "App beenden" in den Einstellungen sichert alle Anpassungen und beendet das Programm sauber, sodass man direkt ins Hauptmenü / PortMaster zurückkehrt.

### Behoben
- **Karten-Überhang in den Einstellungen behoben:**
  - In der ausgewählten Zeile ragten die Einstellungsoptionen mit den Pfeilen (`◄ ... ►`) über den rechten Rand der Menü-Kachel hinaus, da die Breitenmessung mit der normalen Schrift erfolgte, der Text jedoch fett gerendert wurde.
  - Messung und Textanzeige nutzen nun strikt dieselbe Schriftart und Skalierung; der rechte Sicherheitsabstand bleibt stets gewahrt.
- **Viewport-Scrolling mit Scrollbar für Einstellungen:**
  - Dynamisches vertikales Scrolling mit nativer Scrollbar stellt sicher, dass alle 16 Einstellungsoptionen auf allen Handheld-Auflösungen (480p, 720p) optimal erreichbar sind.

---

## [0.3.9] - 2026-10-21

### Hinzugefügt
- **Echtzeit Caching-Fortschrittsbalken im Footer:**
  - Sobald neue Beiträge geladen werden, lädt die App Thumbnails im Hintergrund automatisch vor (`preload_items`).
  - Eine elegante Lade-Linie am oberen Rand des Footers visualisiert den Caching-Fortschritt in Echtzeit in pr0-Orange mit weißem Leuchtpunkt.
  - Auf der rechten Seite des Footers informiert eine dezente Statusanzeige über den aktuellen Vorlade-Status (z.B. `Cache: 38/60 (63%)`), die nach Abschluss zu `v0.3.9` wechselt.
- **Größerer Header & Footer für verbesserte Lesbarkeit:**
  - Header-Höhe von 38 px auf **46 px** vergrößert (auf 16:9-Displays entsprechend skaliert).
  - Footer-Höhe von 32 px auf **38 px** vergrößert.
  - Größere Touch- & Navigations-Pills (22 px statt 18 px) und angepasste Schriftgrößen (+1-2 pt) sorgen auf kleinen 3,5" und 5" Handheld-Displays für deutlich angenehmere Ablesbarkeit.
- **Asset-Bereinigung (Unbenutzte Fonts entfernt):**
  - Die ungenutzte Pixel-Schriftart `assets/fonts/m5x7.ttf` wurde gelöscht.
  - Robuste Fallbacks auf `Inter-Regular.ttf` implementiert.

---

## [0.3.8] - 2026-10-21

### Hinzugefügt
- **Interaktive Header-Navigation im Web-Stil (Option 3):**
  - Befindet man sich in der obersten Zeile der Grid-Ansicht, springt der Cursor mit **D-Pad Hoch** nahtlos in die Header-Leiste direkt über das jeweilige Flag.
  - Im Header kann mit **D-Pad Links/Rechts** zwischen `neu`, `beliebt`, `sfw`, `nsfw`, `nsfl` und `pol` navigiert werden.
  - **Einzelschaltung mit `A`:** Jedes Flag (`sfw`, `nsfw`, `nsfl`, `pol`) lässt sich einzeln an- und abwählen (wie im Web!). Mindestens ein Filter bleibt als Schutz immer aktiv.
  - **Solo-Auswahl mit `Y`:** Blitzschnell ausschließlich das gewählte Flag aktivieren (z.B. Cursor auf `nsfw` -> `Y` drücken -> sofort reiner NSFW-Feed!).
  - **Rückkehr zum Grid mit `D-Pad Runter` oder `B`:** Der Cursor kehrt räumlich passend in die entsprechende Spalte des Kachelgitters zurück.
- **`Nur NSFW (2)` & `Nur NSFL (4)` in Schnellwahl & Settings:**
  - Die Schultertasten `L1` / `R1` durchlaufen nun: `SFW (1) -> Nur NSFW (2) -> SFW+NSFW (3) -> SFW+NSFW+NSFL (7) -> Alle (15)`.
  - Im Einstellungsmenü (`START`) kann `Nur NSFW` ebenfalls direkt als Filter gewählt werden.
- **Photorealistisches 3D-Produkt-Rendering:** Neues Octane-Rendering in Banner und Infografik-Poster mit unverzerrter, nativer pr0gramm-Gridview auf R36S und TrimUI Smart Pro.

---

## [0.3.7] - 2026-10-21

### Hinzugefügt
- **Harmonisches Brand-Logo `[pr0]-retroconsole`:** Das doppelte Logo (`[pr0] pr0-retroconsole`) wurde durch einen einheitlichen Markenschriftzug ersetzt. Der Teil `pr0` ist in eine passgenaue orangefarbene Badge mit zentriertem Text und großzügigem Innenabstand gefasst, gefolgt vom nahtlosen Schriftzug `-retroconsole`.
- **Knulli OS Unterstützung & Badge:** Neues stylisches Badge für *Knulli* (Batocera-basierte Handheld-Firmware) in Banner und Infografik-Poster ergänzt. Knulli-Pfade (`/userdata/roms/ports/`) in `pr0-retroconsole.sh` und `README.md` integriert.
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
