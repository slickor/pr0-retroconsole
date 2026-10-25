# Changelog

Alle nennenswerten Änderungen an **pr0-retroconsole** werden in dieser Datei dokumentiert.

> [!NOTE]
> Dieses Änderungsprotokoll und alle Release-Dokumentationen werden verbindlich in der einzig wahren **Amtssprache (Deutsch)** geführt.
> Sämtlicher Code in diesem Projekt ist **100% zertifizierter Vibecode**.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/)
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

---

## [0.4.11] - 2026-10-25

### Behoben
- **Knulli / TrimUI Smart Pro Vollbild-Videoausgabe endgültig repariert:**
  - **Mali FBDEV Display-Anbindung (`--vo=sdl,gpu`):** TrimUI Smart Pro (Allwinner A133) nutzt proprietäre Mali FBDEV EGL-Treiber ohne DRM-KMS (`Option gpu-context: 'drm' isn't supported`). Durch den Wechsel auf `--vo=sdl,gpu` greift mpv direkt auf den systemeigenen SDL2-Mali-Treiber (`driver=mali`) zu – exakt wie Pygame selbst.
  - **`--input-gamepad=no` behebt SDL-Subsystemkonflikt:** Verhindert, dass mpvs interne Gamepad-Erkennung das SDL2-Joystick-Subsystem vorzeitig initialisiert und dadurch `vo_sdl` mit *'Another component is using SDL already'* blockiert.
  - **Reparatur der mpv-Tastenbindings:** Syntaxfehler in `_generate_mpv_input_conf()` behoben, durch den A/B-Tasten ohne Action-Befehle generiert wurden.

---

## [0.4.10] - 2026-10-25

### Hinzugefügt
- **Vollbildansicht für Bilder inklusive vertikalem Scrollen ("Tapeten-Modus"):**
  - **A-Taste öffnet Bild im Vollbild:** In der Einzelpostansicht (`STATE_POST`) schaltet das Drücken der A-Taste (`ACTION_SELECT`) bei Bildern direkt in die Vollbildansicht (`STATE_IMAGE_FULLSCREEN`).
  - **Responsive Skalierung & Vertikales Scrollen ("Tapeten"):**
    - Überhohe Bilder (Webcomics, Infografiken, Memes mit Hochkant-Format) füllen automatisch die volle Bildschirmbreite aus, sodass Texte und Details groß und gestochen scharf lesbar sind.
    - Fließendes vertikales Scrollen über die gesamte Bildlänge mit Steuerkreuz (D-Pad ▲/▼), Analogsticks (stufenloses Halten) und Schultertasten (L1/R1 für schnelle Seitensprünge).
    - Dezente, elegante Scrollbar am rechten Bildschirmrand zeigt aktuelle Position und relative Bildhöhe an.
    - Normale Querformat- und quadratische Bilder werden formatfüllend zentriert dargestellt.
  - **Direkte Post-Navigation & Voting im Vollbild:**
    - Mit ◄ / ► kann direkt im Vollbild zum nächsten oder vorherigen Post gewechselt werden (bei Video-Posts erfolgt ein nahtloser Wechsel in die Postansicht).
    - Schnelles Bewerten mit Y/R1 (+1) und X/L1 (-1) direkt im Vollbildmodus.
    - Zurück zur Postansicht mit B, A, START oder Esc.

### Behoben
- **Knulli / Batocera Vollbild-Video Freeze auf TrimUI Smart Pro behoben:**
  - **DRM/KMS Video-Output repariert:** In Linux-Handheld-Umgebungen ohne X11/Wayland-Server schlug mpv mit `--vo=gpu,drm,sdl --gpu-context=auto` fehl (`[vo] Video output drm not found!`, `[vo/sdl] Another component is using SDL already.`), wodurch mpv stumm in den Audio-Only-Modus wechselte und der Bildschirm auf dem letzten Frame einfror.
  - **Exklusiver DRM-Kontext:** mpv wird in TTY-/Handheld-Konsolenumgebungen nun gezielt mit `--vo=gpu-next,gpu --gpu-context=drm` gestartet.
  - **LD_PRELOAD-Isolation:** `LD_PRELOAD` wird beim Starten externer Media-Player aus dem Subprozess-Environment entfernt, wodurch Konflikte zwischen Pygames gepatchter SDL2 und systemeigenen Bibliotheken verhindert werden.
  - **Säuberung der mpv-Steuerung (`pr0_mpv_input.conf`):** Entfernung ungültiger Linux-Evdev-Schlüssel; Einbindung nativer mpv-Tasten (`GAMEPAD_MENU`, `GAMEPAD_DPAD_*`, `GAMEPAD_A`, `GAMEPAD_B`, `BS`). Die Taste MENU beendet die Wiedergabe zuverlässig.

---

## [0.4.9] - 2026-10-25

### Hinzugefügt
- **Universeller automatischer SD-Karten-Installer (`install.ps1`):**
  - **Intelligente Partitions- & CFW-Erkennung:** Erkennt automatisch jede eingesteckte SD-Karte und ordnet sie der korrekten Custom Firmware (CFW) zu:
    - **muOS (Split-Architektur):** Trennt automatisch zwischen Starter-Skript (`ROMS\ports\pr0-retroconsole.sh`) und App-Ordner (`\ports\pr0-retroconsole\`).
    - **Knulli & Batocera (Multi-Partition):** Erkennt Dual-Partitionen, ignoriert automatisch die Boot-Partition (`KNULLI`/`BATOCERA`) und wählt zielsicher die Datenpartition (`SHARE\roms\ports\`).
    - **ArkOS (Single- & Dual-SD):** Erkennt `EASYROMS` und navigiert Starter & App direkt nach `ports\`.
    - **TrimUI (CrossMix-OS & MinUI):** Unterstützt `Data\ports\` für Game-Assets und `Roms\PORTS\` / `Emus\PORTS\` für Starter.
    - **AmberELEC, ROCKNIX & JELOS:** Unterstützt `GAMES` und verschachtelte `roms\ports\`-Strukturen.
  - **Automatischer Login- & Einstellungs-Schutz:** Eine bestehende `config.json` auf der SD-Karte wird bei Updates niemals überschrieben; Zugangsdaten, Filter und Themes bleiben dauerhaft erhalten.
  - **Garantierte Unix-LF-Konvertierung:** Alle `.sh`, `.py`, `.gptk`, `.conf` und `.json` Dateien werden beim Kopiervorgang automatisch auf Unix-Zeilenumbrüche (`\n`) normalisiert.
- **Offizielle Amtssprache & 100% Vibecode Siegel:**
  - Verbindliche Deklaration der pr0-Amtssprache (Deutsch) und der 100% Vibecode-Philosophie in sämtlichen Projektdateien, Quellcode-Docstrings, im Handheld-Einstellungsmenü (`START`) sowie auf allen Präsentationsgrafiken (Poster & Banner).

### Verbessert
- **Robuste Pfadauflösung im Launcher (`pr0-retroconsole.sh`):**
  - Erweiterte `GAMEDIR`-Auflösung für `Data/ports/pr0-retroconsole` (CrossMix & MinUI), `/storage/roms/ports/` (AmberELEC & ROCKNIX) und `/storage/games-external/` (ROCKNIX Slot 2).
- **Entwickler-Skripte bereinigt:**
  - Lokale Hilfsskripte (`run.bat`, `run.ps1`, `push.ps1`, `export_sd_ports_check.ps1`) sauber in `dev/` verschoben und vom Git-Tracking ausgeschlossen.

---

## [0.4.8] - 2026-10-25

### Behoben
- **QR-Code Login Bildschirm Layout & Skalierung korrigiert:**
  - **Vollständig responsive Card-Größe:** Die Hauptkarte für den QR-Code-Login war zuvor fälschlicherweise auf maximal 600 Pixel beschränkt (`min(600, width - 20)`). Auf 1280×720-Displays (wie dem TrimUI Smart Pro) führte dies dazu, dass der graue Hintergrundkasten zu schmal war, der Text viel zu weit nach rechts gerückt erschien und über den Kasten hinausragte. Nun skaliert die Karte dynamisch (`card_w = min(int(740 * scale), width - 24)` $\approx$ 1110 Pixel auf 720p).
  - **Dynamische URL-Box gegen Text-Überlauf:** Die IP-Adresse (`http://<ip>:<port>`) ragte aus ihrem Umrandungskasten heraus. Die Box passt sich nun dynamisch an die Textbreite an (`url_box_w = min(right_w, max(url_w + 36 * scale, 260 * scale))`), sodass die IP-Adresse mit beidseitigem Abstand zentriert und umrahmt im Kasten dargestellt wird.
  - **Perfekte vertikale Zentrierung:** QR-Code und rechte Anleitungsspalte sind nun optisch und mathematisch zentriert aufeinander abgestimmt.
  - **Höher aufgelöster QR-Code:** Für hochauflösende Panels wird der QR-Code nun mit vergrößerter Basisauflösung erzeugt, was das Scannen per Smartphone-Kamera noch schneller und zuverlässiger macht.

---

## [0.4.7] - 2026-10-25

### Behoben
- **TrimUI Smart Pro Controller Mapping & Login-Workflow Fix:**
  - **TrimUI Smart Pro Tasten-Layout behoben:**
    - Auf dem TrimUI Smart Pro Controller (ohne gptokeyb, z. B. unter muOS) sendet die physische **START-Taste** im Linux-Treiber `Button 9`. Unser bisheriges Mapping fing Button 9 für L2/R2 (`ACTION_TOGGLE_MODE`) ab, wodurch beim Druck auf START der Modus (Neu/Beliebt) umgeschaltet und der Feed neu geladen wurde, statt die Einstellungen zu öffnen.
    - Nun erkennt `InputManager` Controller mit dem Namen "TRIMUI" automatisch und mappt die Tasten präzise:
      - Button 9 $\rightarrow$ `START` (`ACTION_SETTINGS`)
      - Button 8 $\rightarrow$ `SELECT` (`ACTION_BACK`)
      - Button 6 & 7 $\rightarrow$ `L2` & `R2` (`ACTION_TOGGLE_MODE`)
      - Button 4 & 5 $\rightarrow$ `L1` & `R1` (`ACTION_DOWNVOTE` & `ACTION_UPVOTE`)
      - Button 1 $\rightarrow$ physisches `A` (Bestätigen / Öffnen)
      - Button 0 $\rightarrow$ physisches `B` (Zurück)
      - Button 3 $\rightarrow$ physisches `X` (Info / Setup)
      - Button 2 $\rightarrow$ physisches `Y` (Solo-Filter)
  - **Direkter Express-Login per Taste A auf dem Empty-Screen:**
    - Erscheint die Meldung *"Anmeldung erforderlich für NSFW/NSFL"*, startet ein Druck auf die **A-Taste** sofort direkt den QR-Code Express-Login (`_start_login_flow()`), ohne Umweg über Menüs.
    - Druck auf **START** oder **X** öffnet zuverlässig die Einstellungen.
  - **Kein endloser Reload-Loop / Durchrutschen von Tasten:**
    - Behoben: Auf leeren Feeds löste jede ungemappte Taste (wie `X`) versehentlich das automatische Feed-Paging aus, da `total == 0 < cols * 2` fälschlicherweise `fetch_feed(append=True)` feuerte.
    - Schutz gegen Sofort-Schließen: Wenn die Einstellungen über START betreten werden, verhindert ein Cooldown-Fenster (450 ms), dass ein langes Halten der START-Taste die Einstellungen sofort wieder schließt und speichert.
  - **Automatisches Feed-Neuladen nach erfolgreichem Login:**
    - Sobald der Login über den Smartphone-Begleiter abgeschlossen ist, wird der zuvor leere Feed sofort automatisch geladen und befüllt.

---

## [0.4.6] - 2026-10-25

### Behoben
- **Präziser Hinweis bei nicht angemeldeten NSFW/NSFL-Aufrufen (Kein irreführendes "WLAN prüfen"):**
  - **Ursache behoben:** Wenn ein Nutzer ohne Login (z. B. nach einer Neuinstallation ohne `config.json`) auf NSFW, NSFL oder POL umschaltete, wies die pr0gramm-API den Request mit HTTP 403 ("Nicht eingeloggt") ab. Die App zeigte fälschlicherweise "Keine Beiträge geladen (WLAN prüfen)", obwohl das WLAN funktionierte.
  - **403-Erkennung in der API:** In `Pr0API.get_items` wird HTTP 403 / `nsfwRequiresLogin` nun gezielt als `auth_required` identifiziert, statt generische Verbindungsfehler zu werfen.
  - **Dedizierter Empty-Feed-Screen:**
    - Zeigt eine klare Info-Karte: *"Anmeldung erforderlich für NSFW/NSFL"* mit pr0-Orange-Hervorhebung.
    - Erklärungstext: *"pr0gramm blendet 18+ Inhalte nur für eingeloggte Accounts ein."*
    - Handlungsanweisung: `[START] Drücken für Setup & QR-Code Express-Login`.
    - Drücken von `A` auf dem leeren Screen öffnet direkt das Einstellungs-/Login-Menü.
  - **Toast-Hinweise beim Filterwechsel:**
    - Beim Umschalten auf NSFW/NSFL in der Header-Leiste, per Schnellwahl (`L1`/`R1`) oder im Einstellungsmenü weist ein Toast-Hinweis direkt darauf hin, dass ein Login nötig ist.
    - Im Einstellungsmenü wird der Filter bei fehlendem Login mit `(Login nötig)` gekennzeichnet.
  - **Auto-Retry-Schutz:** Verhindert endlose Hintergrund-Wiederholungsversuche bei Feeds, die zwingend einen Login erfordern.

---

## [0.4.5] - 2026-10-22

### Behoben
- **Schwarzer Bildschirm auf muOS (TrimUI Brick) behoben:**
  - **Mali-Hardwaretreiber statt manylinux-Offscreen:** Pip-Wheels (`pygame` und `pygame-ce`) bündeln vorkompilierte `libSDL2.so`-Bibliotheken für generische Linux-Server, denen hardwarenahe Konsolentreiber wie Mali fehlen (Fehlermeldung: `mali not available`, woraufhin SDL auf `driver=offscreen` auswich).
  - **Automatisches Patcher- & Preload-System (`tools/patch_sdl2.py`):**
    - Ermittelt beim Start dynamisch die native System-`libSDL2.so` von muOS (welche über vollen Mali-Treiber-Support verfügt).
    - Lädt diese via `LD_PRELOAD` und `ctypes.CDLL(..., mode=RTLD_GLOBAL)` vor dem Pygame-Import in den globalen Adressraum.
    - Ersetzt/verlinkt automatisch die gebündelten Bibliotheken in `pygame_ce.libs/` auf die native muOS-Systembibliothek.
  - **Display-Initialisierung für Mali-Framebuffer:**
    - Priorisiert den Treiber `mali` vor `kmsdrm` auf Mali-Handhelds.
    - Unterstützt native Fullscreen-Panelauflösungen (z. B. 1024×768 auf TrimUI Brick) mit automatischer Anpassung und hardwarebeschleunigtem Scaling.
  - **Bereinigung von Berechtigungen und Pfaden:**
    - `chmod 666 /dev/mali*` im Launcher hinzugefügt.
    - Saubere Priorisierung von Systembibliotheken vor PortMaster-Ordnern in `LD_LIBRARY_PATH`.

---

## [0.4.4] - 2026-10-22

### Behoben
- **Vollbild-Videoansicht auf Handhelds mit Hardware-Layer (Knulli / Mali GPU / TrimUI):**
  - **Exklusiver Display-Wechsel für mpv:** Auf Linux-Handhelds ohne Fenstermanager blockierte das aktive Pygame-Fenster (Mali EGL Surface) den Zugriff von mpv auf den Bildschirm. Pygame gibt das Display vor dem Start von mpv nun temporär frei (`pygame.display.quit()`), sodass mpv exklusiven Vollbild-Hardwarezugriff (`--vo=gpu,drm,sdl`) erhält. Nach Beendigung des Videos wird das Pygame-Display sofort nahtlos wiederhergestellt.
  - **Tasten-Exit bei Invertiert-Layout korrigiert:** In `back_keys` wurde `K_ESCAPE` für das invertierte Layout entfernt, sodass nur noch die tatsächliche Zurück-Taste das Video beendet und B wie vorgesehen pausiert/weiterspielt.
- **Automatisches Upgrade auf `pygame-ce` für muOS:**
  - Auf muOS fehlten dem standardmäßigen pip-Pygame-Wheel die Linux-Konsolentreiber (`kmsdrm`), weshalb SDL auf `offscreen` verfiel.
  - Sowohl `install.sh` als auch `pr0-retroconsole.sh` erkennen nun automatisch, ob Pygame nur im `offscreen`-Modus läuft, und installieren gezielt `pygame-ce` (Community Edition), welches vollen KMSDRM- und Konsolen-Support für Embedded Handhelds mitbringt.
  - `mod_${CFW_NAME}.txt` von PortMaster wird nun beim Start geladen und alle PortMaster-Pfade auf muOS (`/mnt/mmc/MUOS/PortMaster/...`) werden in `PATH` und `LD_LIBRARY_PATH` eingebunden.

---

## [0.4.3] - 2026-10-21

### Behoben
- **Tastenbelegung in der Vollbild-Videoansicht (Knulli / TrimUI):**
  - **A/B-Tastentausch in mpv behoben:** In mpv (`pr0_mpv_input.conf`) war `BTN_EAST` (auf Nintendo-/TrimUI-Handhelds die physische A-Taste) fälschlicherweise auf `quit` und `BTN_SOUTH` (physische B-Taste) auf `cycle pause` gemappt. Dadurch beendete A das Video und B pausierte.
  - **Dynamische Tastenbelegung:** Sowohl `mpv` als auch der Event-Loop in Pygame generieren und interpretieren die Steuerbefehle nun exakt abgestimmt auf das in den Einstellungen gewählte Layout (Standard: A=Play/Pause, B=Beenden; Invertiert: B=Play/Pause, A=Beenden).
- **Physische Display-Erkennung auf muOS (`driver=offscreen` Fix):**
  - Auf Systemen, bei denen SDL ohne expliziten Treiber in den unsichtbaren `offscreen`-Modus verfällt, erkennt Pygame nun automatisch, dass kein physischer Bildschirm angesteuert wird.
  - Automatische Suche nach echten Hardware-Backends (`kmsdrm`, `mali`, `fbcon`, `wayland`, `x11`) mit nativer Panel-Auflösung `(0, 0, FULLSCREEN)`.
  - **Rechte & Pfade in `pr0-retroconsole.sh`:** Zugriffsberechtigungen für `/dev/dri/*` und `/dev/fb*` für Non-Root-User sowie PortMaster-Pfade für muOS (`/mnt/mmc/MUOS/PortMaster`, `/mnt/mmc/ports/PortMaster`, etc.) ergänzt.

---

## [0.4.2] - 2026-10-21

### Behoben
- **Display-Initialisierung auf muOS / TrimUI (`pygame.error: kmsdrm not available`):**
  - **Entfernung von forciertem `SDL_VIDEODRIVER=kmsdrm` in `pr0-retroconsole.sh`:** Auf TrimUI und muOS verwendet SDL standardmäßig den nativen OS-Grafiktreiber; das Erzwingen von `kmsdrm` schlug fehl, da die pip-Pygame-Binaries nicht gegen KMSDRM gelinkt sind bzw. muOS andere Video-Backends nutzt.
  - **Automatischer Driver-Fallback in Pygame:** Sollte ein in der Systemumgebung gesetzter `SDL_VIDEODRIVER` fehlschlagen, wird die Variable im Fehlerfall automatisch entfernt, das Pygame-Display-Subsystem reinitialisiert und auf den Standard-Treiber zurückgegriffen.
  - **Stufenweises Fallback bei Display-Modi:** Bei Fehlern mit `DOUBLEBUF` oder `FULLSCREEN` wird automatisch ein sicherer Fallback-Modus gewählt, damit die App in jedem Fall startet.

---

## [0.4.1] - 2026-10-21

### Behoben
- **DNS- & Verbindungs-Resilienz (muOS / TrimUI Fix):**
  - **Automatischer Domain-Fallback (`pr0gramm.com` 🔁 `pr0.app`):** Sollte eine Domain (`pr0.app`) DNS-Auflösungsfehler (`Temporary failure in name resolution`) oder Verbindungsprobleme melden, wechselt die App automatisch zur Hauptdomain `pr0gramm.com` (und umgekehrt).
  - **Wiederholungsversuche mit Backoff:** Temporäre DNS- und Verbindungsabbrüche beim Hochfahren der Handheld-WLAN-Verbindung werden bis zu 3-mal automatisch mit Pause wiederholt, statt direkt abzubrechen.
  - **Auto-Retry & Manueller Reload bei leerem Feed:** Bei Verbindungsverlust beim Start versucht die App nun automatisch alle 3 Sekunden im Hintergrund den Feed nachzuladen, sobald WLAN bereit ist. Zudem kann mit der Taste `A` der Feed jederzeit manuell neu geladen werden.
  - **KMSDRM & Vollbild-Garantie auf Embedded Linux (muOS / TrimUI):** Auf Handhelds erzwingt Pygame nun stets Vollbild-KMSDRM (`pygame.FULLSCREEN | pygame.DOUBLEBUF`), passt sich der nativen Display-Auflösung an (z. B. 1280x720 auf TrimUI Smart Pro) und verhindert unsichtbare Fenstermodi.
  - **CDN-Fallback für Medien & Vorschaubilder:** Auch der Download-Cache probiert bei Netzwerkfehlern automatisch beide CDN-Domains (`pr0gramm.com` und `pr0.app`).

---

## [0.4.0] - 2026-10-21

### Hinzugefügt
- **Interaktive Kommentare (Upvote / Downvote & Antworten):**
  - **D-Pad Fokus-Navigation:** In der Beitragsansicht kann mit D-Pad Oben / Unten stufenlos und mit weichem Auto-Scroll zwischen dem Medium, der neuen Kommentar-Schaltfläche und allen Kommentaren navigiert werden.
  - **Kommentar-Aktionsmenü:** Drücken von `A` auf einem ausgewählten Kommentar öffnet ein zentriertes Popup-Modal mit Optionen:
    - `✎ Antworten`: Öffnet die Bildschirmtastatur zur direkten Antwort an `@autor`.
    - `▲ +1 (Blussi)`: Vergibt ein Upvote auf den Kommentar.
    - `▼ -1 (Downvote)`: Vergibt ein Downvote auf den Kommentar.
    - `✕ Abbrechen`: Schließt das Modal.
  - **Schnell-Voting:** Mit `Y` (oder `R1`) bzw. `X` (oder `L1`) kann der fokussierte Kommentar (oder der Post selbst, wenn das Medium fokussiert ist) sofort bewertet werden.
  - **Neuen Kommentar verfassen:** Über die neue Schaltfläche `[ ✎ Neuen Kommentar verfassen... ]` direkt unter der Kommentaranzahl können neue Hauptkommentare erstellt werden.
  - **Bildschirmtastatur & USB-Tastatur-Support:** Volle Unterstützung für die virtuelle Tastatur (QWERTY, Shift, Backspace, Fertig) per Gamepad sowie Texteingabe per physischer Tastatur.
  - **Optimistisches UI-Feedback:** Benis-Punkte und Bewertungen werden sofort visuell aktualisiert (grün für positiv, rot für negativ) und im Hintergrund per API synchronisiert.

---

## [0.3.16] - 2026-10-21

### Hinzugefügt
- **Video-Fortschrittsbalken in Inline- und Vollbildansicht:**
  - **Inline-Ansicht (Kommentaransicht):** Am unteren Rand des abgespielten Videos wird nun ein schlanker, akzentfarbener Fortschrittsbalken (z. B. pr0-Orange) in Echtzeit gerendert, der die genaue Abspielposition anzeigt.
  - **Vollbildansicht (`ffplay` / `mpv`):** Ein visueller Fortschrittsbalken wird im Vollbildmodus am unteren Bildschirmrand eingeblendet.
- **Relatives 10%-Springen mit den Pfeiltasten (Links / Rechts):**
  - Anstelle eines starren 10-Sekunden-Sprungs ermittelt die App nun die exakte Gesamtlänge des Videos (per MP4/WebM-Headeranalyse).
  - Beim Drücken der Pfeiltasten Links/Rechts (oder des D-Pads) springt der Player nun exakt **10 % der Gesamtlänge** des Videos vor oder zurück.

---

## [0.3.15] - 2026-10-21

### Behoben
- **NameError-Absturz beim Öffnen von Videos behoben:**
  - Laut Crash-Log stürzte die App beim Betreten der Videoansicht sofort ab (`NameError: name 'FLAG_NSFW' is not defined`).
  - Die Konstanten `FLAG_NSFW`, `FLAG_NSFL` und `FLAG_NSFP` wurden in den Import von `src/main.py` aufgenommen.
  - Sämtliche Quelldateien wurden statisch auf fehlende Symbole geprüft.

---

## [0.3.14] - 2026-10-21

### Behoben
- **NSFW/NSFL-Video- und Bildwiedergabe repariert (Altersverifikations-Cookie `av`):**
  - **Ursache im Log identifiziert:** pr0gramm CDN verlangt für alle jugendgeschützten Inhalte (NSFW/NSFL-Videos auf `vid.pr0.app` und Vorschaubilder auf `thumb.pr0gramm.com`) neben dem Anmelde-Cookie (`me`) zwingend ein dynamisches Altersverifikations-Cookie (`av`). Fehlt dieses, blockiert der CDN-Server jegliche Wiedergabe mit `403 age-verification-required` (`X-Age-Gate: denied`).
  - **Automatische Sitzungssynchronisation (`sync_user_session`):** Die App ruft beim Start und nach jeder Anmeldung automatisch `/api/user/me` ab und extrahiert das `av`-Token. Der Nutzer muss kein zusätzliches Cookie manuell eingeben.
  - **Multi-Domain Cookie-Dispatch:** Das `av`-Cookie wird domainspezifisch und RFC-konform sowohl an `pr0.app` als auch an `pr0gramm.com` gebunden und nahtlos an den Download-Cache (`MediaCache`), `InlineVideoPlayer` (FFmpeg-Streamer & Audio) sowie den Vollbild-Player (`ffplay` / `mpv`) übermittelt.
  - **Präzises Benutzer-Feedback:** Sollte ein Account auf pr0gramm noch nicht altersverifiziert sein, wird beim Aufrufen von NSFW-Beiträgen ein entsprechender Toast-Hinweis eingeblendet (`Altersverifikation auf pr0gramm.com nötig!`).

---

## [0.3.13] - 2026-10-21

### Behoben
- **Inline-Video-Wiedergabe in der Post-Ansicht repariert (403-Fix):**
  - Authentifizierungs-Cookie (`me_cookie`) wird nun nahtlos an den Download-Cache (`MediaCache`), den integrierten FFmpeg-Videodecoder sowie den Audio-Begleiter übergeben.
  - Verhindert, dass NSFW/NSFL-Videos mit HTTP 403 Forbidden ("age-verification-required") abgelehnt werden. Videos spielen nun direkt eingebettet in der Beitragsansicht über den Kommentaren ab.
- **Display-Freeze beim Beenden des Vollbild-Videos (KMSDRM -16) behoben:**
  - Auf Linux-Handhelds (ArkOS / R36S) führte das Beenden von `ffplay` zu `ERROR: Could not queue pageflip: -16` (EBUSY), wodurch der Bildschirm einfror und ein Verlassen mit `B` unmöglich schien.
  - Die Display-Oberfläche wird beim Verlassen des Players jetzt sofort sauber resynchronisiert (`set_mode`), sodass die Rückkehr zur App verzögerungsfrei gelingt.
  - Doppelpufferung (`SDL_VIDEO_DOUBLE_BUFFER=1`) im Start-Skript aktiviert.

### Geändert
- **`A: Vollbild` Overlay-Badge entfernt:**
  - Das Abzeichen oben rechts über dem Video in der Beitragsansicht wurde vollständig entfernt, damit das Video ungestört und unverdeckt sichtbar ist.
- **Release-ZIPs im Unterordner `release/`:**
  - Gebaute Release-Archive werden ab sofort ordentlich in `release/` abgelegt, um das Hauptverzeichnis sauber zu halten.

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
