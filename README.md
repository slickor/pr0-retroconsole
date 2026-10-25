# pr0-retroconsole

<p align="center">
  <img src="https://raw.githubusercontent.com/slickor/pr0-retroconsole/refs/heads/main/docs/images/pr0-presentation-banner.png?v=0.4.9" alt="pr0-retroconsole Banner" width="100%">
</p>

<p align="center">
  <a href="https://github.com/slickor/pr0-retroconsole/releases"><img src="https://img.shields.io/github/v/release/slickor/pr0-retroconsole?color=ee4d2e&style=for-the-badge" alt="Latest Release"></a>
  <img src="https://img.shields.io/badge/Platform-ArkOS%20%7C%20CrossMix%20%7C%20muOS%20%7C%20Knulli%20%7C%20PortMaster-1b79c3?style=for-the-badge" alt="Platform">
  <img src="https://img.shields.io/badge/Amtssprache-Deutsch%20%F0%9F%87%A9%F0%9F%87%AA-ee4d2e?style=for-the-badge" alt="Amtssprache: Deutsch">
  <img src="https://img.shields.io/badge/Code-100%25%20Vibecode%20%E2%9C%A8-f5a623?style=for-the-badge" alt="100% Vibecode">
  <img src="https://img.shields.io/badge/Python-3.8%2B%20%7C%20SDL2-5cb85c?style=for-the-badge" alt="Python Version">
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Changelog-v0.4.9-orange?style=for-the-badge" alt="Changelog"></a>
  <a href="ROADMAP.md"><img src="https://img.shields.io/badge/Roadmap-2026-blueviolet?style=for-the-badge" alt="Roadmap"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/slickor/pr0-retroconsole?style=for-the-badge" alt="License"></a>
</p>

> **pr0-retroconsole** ist ein nativer, leichtgewichtiger Client für das Imageboard [pr0gramm](https://pr0gramm.com), maßgeschneidert für Linux-basierte Retro-Handheld-Konsolen wie den **R36S** (640x480, ArkOS), den **TrimUI Smart Pro** (1280x720, CrossMix-OS), Anbernic-, Powkiddy-, Knulli- und PortMaster-Systeme.

> [!IMPORTANT]
> ### 🇩🇪 Amtssprache & 100% Vibecode-Garantie
> Dieses Projekt wird mit voller Absicht, Hingabe und ohne faule Kompromisse auf **Deutsch** (auf dem pr0 bekanntlich die einzig wahre *„Amtssprache“*) dokumentiert, kommentiert, bedient und ausgeführt. Wer hier angelsächsischen Firlefanz sucht, darf ihn behalten.
>
> Zudem ist diese Software zu **100% zertifizierter Vibecode**: Keine endlosen Scrum-Zeremonien, keine Enterprise-Jira-Tickets, keine überkandidelten Architektur-Ausschüsse – sondern pure Vibes, KI-Pair-Programming, handverlesene Pygame- und SDL2-Hacks und ein Traum von pr0gramm auf dem Fliesentisch-Handheld. Es läuft einfach!

---

<details>
<summary>📱 <b>Infografik & Feature-Poster ansehen (Klicken zum Ausklappen)</b></summary>
<br>
<p align="center">
  <img src="https://raw.githubusercontent.com/slickor/pr0-retroconsole/refs/heads/main/docs/images/pr0-presentation-poster.png?v=0.4.9" alt="pr0-retroconsole Infografik-Poster" width="850">
</p>
</details>

---

## Highlights & Features

- **Flüssiger Videosound & 60 FPS:**
  - Videos laufen direkt in der Beitragsansicht synchron mit Ton.
  - Vollbild-Wiedergabe via `mpv` oder `ffplay` auf Knopfdruck (`A`) mit Pause/Weiter und sauberem Beenden (`B`).
  - Spezieller Software-Decoder-Modus (`--hwdec=no`) behebt den Allwinner-A133 DTS/PTS B-Frame-Ruckel-Bug auf dem TrimUI Smart Pro.
- **Originalgetreuer pr0.app Look:**
  - Authentischer Web-Header mit Suchleiste, Benis-Punkten, Benutzernamen und korrekten Rang-Farben (*Schwuchtel, Neuschwuchtel, Altschwuchtel, Moderator, Admin*).
  - Integrierter Farbschema- und Akzent-Wechsler in den Einstellungen (*pr0 Dark, OLED Schwarz, Nord, Gruvbox, Retro Terminal*).
- **Komfortable Handheld-Bedienung:**
  - Flüssiges D-Pad & Analog-Stick Scrolling mit dynamischer Beschleunigung.
  - Umschaltung zwischen **Beliebt** und **Neu** blitzschnell über `L2` / `R2` (oder im Header).
  - Schneller Content-Filter-Wechsel (`SFW` -> `Nur NSFW` -> `SFW+NSFW` -> `SFW+NSFW+NSFL` -> `Alle`) über `R1` / `L1`.
  - Wählbares Button-Layout (Standard `A`/`B` vs. Invertiert `B`/`A`).
- **QR-Code Express-Login:**
  - Kein manuelles Kopieren von Cookies auf die SD-Karte mehr nötig!
  - Handheld zeigt einen QR-Code an -> mit dem Smartphone scannen -> im Browser einloggen -> Handheld ist sofort angemeldet.
  - Alternativ steht eine Bildschirmtastatur zur Direkteingabe bereit.
- **Vollständiger Kommentarbaum:**
  - Hierarchische Kommentare mit Einrückungen, Autorenrängen, Benis-Bewertung und Upvote/Downvote (+1 / -1).
  - Intelligente Darstellung von "Tapeten" (lange Bilder scrollen vertikal über Inhaltsbreite).
- **Smarter RAM- & Disk-Cache:**
  - Asynchroner Mehrthread-Downloader nach `/tmp/pr0cache` (tmpfs) schont den Flash-Speicher der SD-Karte und sorgt für verzögerungsfreies Scrollen.
- **Kompaktes Release-Paket:**
  - Nur **~0,77 MB** klein (Pure-Python-Abhängigkeiten `requests` an Bord, keine unnötigen Bloatware-Assets).
- **100% Vibecode in Amtssprache:**
  - Konsequent auf Deutsch (pr0-Amtssprache) gehalten: von der Menüführung über Toast-Meldungen bis hin zu den Quellcode-Kommentaren.
  - Mit maximalem Vibe und purer Leidenschaft entwickelt – pragmatisch, schnell und frei von Enterprise-Bürokratie.

---

## Steuerung & Tastenbelegung

Die Bedienung ist komplett auf Gamepads optimiert und funktioniert auf Handhelds (via `gptokeyb`) sowie am PC identisch.

### 🎮 Hauptnavigation (Raster, Header & Beitragsansicht)

| Taste (Handheld) | PC / Tastatur | Kachelgitter (Grid-View) | Header-Filterleiste (▲ in Zeile 0) | Beitragsansicht (Post & Kommentare) | Vollbild-Player (`mpv`/`ffplay`) |
|---|---|---|---|---|---|
| **D-Pad ◄ / ►** | `◄` / `►` | Kachel auswählen | Modus / Flag wählen (`neu`, `sfw`, `nsfw` ...) | Vorheriger / Nächster Post | 10% Vor- / Zurückspulen |
| **D-Pad ▲ / ▼** | `▲` / `▼` | Zeilen wechseln (**▲ in Zeile 0 öffnet Header**) | **▼ kehrt ins Grid zurück** | Fokus wechseln (Medium ➔ Neuer Kommentar ➔ Kommentare) mit Auto-Scroll | - |
| **Rechter Stick ▲ / ▼** | `W` / `S` | Turbo-Scrollen im Raster | - | Freies Scrollen im Beitrag | Lautstärke |
| **A** | `Enter` / `Leertaste` | Post öffnen | Gewähltes Flag an- / abwählen (Einzelschaltung) | **Aktion ausführen:**<br>• Auf Medium: Vollbild-Video<br>• Auf Button: Neuer Kommentar<br>• Auf Kommentar: **Aktions-Popup** (*Antworten, +1, -1*) | Pause / Weiter |
| **B** | `Esc` / `Backspace` / `Q` | App beenden (mit Bestätigung) | Zurück ins Kachelgitter | Zurück zum Kachelgitter | Vollbild beenden / Zurück |
| **START** | `F1` / `F2` / `P` | **Einstellungen öffnen** | **Einstellungen öffnen** | **Einstellungen öffnen** | - |
| **Y** | `Tab` / `Y` | - | **Solo-Filter** (ausschließlich gewähltes Flag aktivieren) | Upvote (**+1 Blussi**) auf Post oder fokussierten Kommentar | - |
| **X** | `I` / `X` | - | - | Downvote (**-1**) auf Post oder fokussierten Kommentar | - |
| **L2 / R2** | `T` | **Beliebt 🔁 Neu** | Modus umschalten | - | - |
| **R1** | `+` / `=` / `R` | Schnell-Filter vorwärts (`SFW` ➔ `Nur NSFW` ➔ `SFW+NSFW` ...) | - | Upvote (**+1 Blussi**) vergeben | - |
| **L1** | `-` / `E` | Schnell-Filter rückwärts | - | Downvote (**-1**) vergeben | - |

---

### 💬 Kommentare, Voting & Antworten

- **Kommentar-Aktionsmenü:** Drücke `A` auf einem beliebigen Kommentar in der Beitragsansicht, um das Popup-Menü zu öffnen:
  - **✎ Antworten:** Öffnet die virtuelle Bildschirmtastatur mit Empfänger `@autor`.
  - **▲ +1 (Blussi):** Gibt dem Kommentar ein Upvote (auch direkt per `Y` oder `R1`).
  - **▼ -1 (Downvote):** Gibt dem Kommentar ein Downvote (auch direkt per `X` oder `L1`).
  - **✕ Abbrechen:** Schließt das Menü (`B`).
- **Neuen Kommentar verfassen:** Direkt unter der Beitragsüberschrift befindet sich die Schaltfläche `[ ✎ Neuen Kommentar verfassen... ]`. Drücke dort `A`, um einen neuen Top-Level-Kommentar zu schreiben.
- **Tippen:** Sowohl per D-Pad / Controller über die Bildschirmtastatur als auch mit angeschlossener USB-/PC-Tastatur möglich. Submit mit `[FERTIG]`, `START` oder `Enter`.

---

### ⚙️ Einstellungsmenü (`START`)

Im Einstellungsmenü können alle Optionen direkt per Gamepad konfiguriert werden:

| Taste | Funktion |
|---|---|
| **D-Pad ▲ / ▼** | Option auswählen |
| **D-Pad ◄ / ►** | Wert durchschalten (*Farbschema, Akzentfarbe, Nur Bilder laden, Autoplay, Filter, Tempo, etc.*) |
| **A** | Aktion ausführen (*pr0gramm Account an/abmelden, Tasten-Test, Cache leeren, App beenden*) |
| **B** oder **START** | Einstellungen speichern & zurück zum Kachelgitter |

---

### ⌨️ Bildschirmtastatur (Direkt-Login)

Beim Direkteingabe-Login auf dem Handheld steht eine virtuelle Tastatur bereit:

| Taste | Funktion |
|---|---|
| **D-Pad** | Tastaturcursor bewegen |
| **A** | Markiertes Zeichen eingeben |
| **X** | `[SHIFT]` (Groß- / Kleinschreibung umschalten) |
| **Y** | `[DEL]` (Letztes Zeichen löschen) |
| **START** | `[FERTIG]` (Eingabe bestätigen & anmelden) |
| **B** | Abbrechen & zurück zur QR-Code-Ansicht |

---

### 🔄 Knopfbelegung (Standard vs. Invertiert)

In den Einstellungen kann unter **Knopfbelegung** jederzeit zwischen zwei Modi gewechselt werden:
- **Standard (Xbox / PC-Stil):** `A` = Öffnen / Bestätigen, `B` = Zurück / Abbrechen
- **Invertiert (Nintendo / RetroArch-Stil):** `B` = Öffnen / Bestätigen, `A` = Zurück / Abbrechen

---

## Installation auf dem Handheld

1. Lade das neueste Release-Archiv **`pr0-retroconsole-v*.zip`** von der [Releases-Seite](https://github.com/slickor/pr0-retroconsole/releases) herunter.
2. Entpacke den Inhalt direkt in das `ports`-Verzeichnis deiner SD-Karte:
   - **ArkOS / R36S:** `/roms/ports/` (bzw. auf dem `EASYROMS`-Laufwerk in `ports/`)
   - **CrossMix-OS / TrimUI Smart Pro:** `/mnt/SDCARD/Emus/PORTS/`
   - **Knulli / Batocera:** `/userdata/roms/ports/` bzw. `/roms/ports/`
   - **PortMaster:** `/roms/ports/` bzw. `tools/PortMaster/`
3. Stelle sicher, dass die Dateistruktur so aussieht:
   ```text
   ports/
   ├── pr0-retroconsole.sh
   └── pr0-retroconsole/
       ├── src/
       ├── assets/fonts/
       ├── libs/
       ├── pr0.gptk
       └── ...
   ```
4. Handheld starten, ins Menü **Ports** wechseln, **pr0-retroconsole** auswählen und genießen!

---

### 🔄 Updates durchführen (Kinderleicht & Sicher)

Wenn eine neue Version von **pr0-retroconsole** erscheint, musst du **keine Neueinrichtung** vornehmen:

1. Lade einfach die neue `pr0-retroconsole-v*.zip` von der [Releases-Seite](https://github.com/slickor/pr0-retroconsole/releases) herunter.
2. Entpacke den Inhalt direkt über deine bestehende Installation auf der SD-Karte und **überschreibe alle vorhandenen Dateien**.
3. **Deine Einstellungen & Logindaten bleiben 100% erhalten!**
   > [!TIP]
   > Alle persönlichen Daten (wie dein pr0gramm Login-Cookie, gewählte Filter, Farbschema und Tastenlayout) werden lokal in der Datei `config.json` auf deinem Handheld gespeichert. Da im Release-Paket bewusst nur die unverfängliche Vorlage `config.example.json` mitgeliefert wird, wird deine aktive `config.json` bei einem Update niemals überschrieben. Du bleibst dauerhaft eingeloggt!

---

## Authentifizierung & Login

Für Upvotes/Downvotes sowie NSFW-/NSFL-Inhalte stehen drei bequeme Anmeldemethoden zur Verfügung:

1. **Smartphone-Companion (Empfohlen):**
   * Im Einstellungsmenü (`START`) auf **pr0gramm Account** drücken (`A`).
   * Den angezeigten QR-Code mit der Smartphone-Kamera scannen (Handy und Handheld im selben WLAN).
   * Im mobilen Browser Benutzername, Passwort und Captcha eingeben – der Handheld loggt sich automatisch ein!
2. **Direkt auf dem Handheld:**
   * Im Anmelde-Bildschirm `X` drücken, um zwischen QR-Code und direkter Eingabe umzuschalten.
   * Mit dem integrierten virtuellen On-Screen-Keyboard Zugangsdaten und Captcha eingeben.
3. **Manuell per `config.json`:**
   * Bestehenden `me`-Cookie-Wert aus dem Desktop-Browser direkt in `config.json` unter `"me_cookie"` einfügen.

---

## Changelog

Alle Versionsänderungen und Neuerungen findest du ausführlich in der Datei [CHANGELOG.md](CHANGELOG.md).

---

## Lizenz & Disclaimer

### Lizenz
Dieses Projekt ist unter der [MIT License](LICENSE) lizenziert.

### Disclaimer
Dies ist ein inoffizielles, freies Community-Projekt und steht in **keiner geschäftlichen oder offiziellen Verbindung** zu *pr0gramm* bzw. *pr0.app*. Alle Markennamen, Logos und abgerufenen Bild-/Videoinhalte sind Eigentum der jeweiligen Rechteinhaber bzw. Uploader. Dieses Tool dient lediglich als Schnittstelle zur Darstellung auf Retro-Gaming-Hardware.
