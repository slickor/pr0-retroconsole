# ==============================================================================
# build.ps1 - Packaging-Skript für pr0-retroconsole (R36S / ArkOS / PortMaster)
# ==============================================================================
# Erstellt ein sauberes, schlankes ZIP-Release ohne unnötige Windows-Dateien.
#
# Struktur im ZIP (PortMaster / ArkOS Standard):
#   ├── pr0-retroconsole.sh       (Startskript -> direkt in /roms/ports/)
#   └── pr0-retroconsole/         (Hauptordner -> in /roms/ports/pr0-retroconsole/)
#       ├── src/
#       ├── assets/
#       ├── pr0.gptk
#       ├── install.sh
#       ├── config.example.json
#       └── requirements.txt
# ==============================================================================

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       pr0-retroconsole - Handheld Release Builder        " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Projektverzeichnis: $ScriptDir" -ForegroundColor Gray

# 1. Version aus src/version.py ermitteln
$Version = "0.2.0"
try {
    $verOut = python -c "import src.version; print(src.version.VERSION)" 2>$null
    if ($verOut) {
        $Version = "$verOut".Trim()
    }
} catch {
    $Version = "0.2.0"
}

Write-Host "Build-Version:      v$Version" -ForegroundColor Yellow

# 2. Pfade definieren
$DistDir = Join-Path $ScriptDir "dist"
$StagingDir = Join-Path $DistDir "staging"
$StagingAppDir = Join-Path $StagingDir "pr0-retroconsole"
$ZipOutputVersioned = Join-Path $ScriptDir "pr0-retroconsole-v$Version.zip"
$ZipOutputCompat = Join-Path $ScriptDir "pr0-retroconsole.zip"

# 3. Vorherige Builds bereinigen
Write-Host "`n[1/5] Bereinige alte Build-Dateien..." -ForegroundColor Gray
if (Test-Path $StagingDir) {
    Remove-Item -Recurse -Force $StagingDir
}
try { if (Test-Path $ZipOutputVersioned) { Remove-Item -Force $ZipOutputVersioned -ErrorAction Stop } } catch { Write-Host "Hinweis: $ZipOutputVersioned wird überschrieben." -ForegroundColor DarkGray }
try { if (Test-Path $ZipOutputCompat) { Remove-Item -Force $ZipOutputCompat -ErrorAction Stop } } catch { Write-Host "Hinweis: $ZipOutputCompat wird überschrieben." -ForegroundColor DarkGray }
New-Item -ItemType Directory -Path $StagingAppDir -Force | Out-Null

# 4. Dateien kopieren (nur Linux / Handheld relevante Dateien)
Write-Host "[2/5] Kopiere Anwendungsdateien..." -ForegroundColor Gray

# A. Startskript an die Wurzel des Staging-Verzeichnisses (für /roms/ports/)
Copy-Item (Join-Path $ScriptDir "pr0-retroconsole.sh") -Destination $StagingDir

# B. Source-Code (ohne __pycache__ und .pyc)
$StagingSrc = Join-Path $StagingAppDir "src"
New-Item -ItemType Directory -Path $StagingSrc -Force | Out-Null
Get-ChildItem -Path (Join-Path $ScriptDir "src") -Filter "*.py" | ForEach-Object {
    Copy-Item $_.FullName -Destination $StagingSrc
}

# C. Assets (Fonts etc.)
$StagingAssets = Join-Path $StagingAppDir "assets"
Copy-Item -Path (Join-Path $ScriptDir "assets") -Destination $StagingAssets -Recurse

# D. Konfigurations- & Skriptdateien
$FilesToCopy = @(
    "install.sh",
    "pr0.gptk",
    "pr0_mpv_input.conf",
    "config.example.json",
    "requirements.txt",
    "README.md",
    "LICENSE"
)

foreach ($f in $FilesToCopy) {
    $srcPath = Join-Path $ScriptDir $f
    if (Test-Path $srcPath) {
        Copy-Item $srcPath -Destination $StagingAppDir
    }
}

# E. Vorinstallierte pure-Python Bibliotheken kopieren & bereinigen
$StagingLibs = Join-Path $StagingAppDir "libs"
if (Test-Path (Join-Path $ScriptDir "libs")) {
    Write-Host "   - Kopiere und optimiere libs/..." -ForegroundColor DarkGray
    Copy-Item -Path (Join-Path $ScriptDir "libs") -Destination $StagingLibs -Recurse
    # Entferne Windows-spezifische Exes, Pyds und Pycache
    Get-ChildItem -Path $StagingLibs -Recurse -Include "*.exe", "*.pyd", "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $StagingLibs -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $StagingLibs -Recurse -Directory -Filter "*.dist-info" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    $binDirInLibs = Join-Path $StagingLibs "bin"
    if (Test-Path $binDirInLibs) { Remove-Item -Recurse -Force $binDirInLibs }
}

# E. config.json bewusst NICHT mitliefern (schützt Benutzereinstellungen & Login beim Update)
$stagedConfig = Join-Path $StagingAppDir "config.json"
if (Test-Path $stagedConfig) {
    Remove-Item -Force $stagedConfig
}

# 4. Zeilenumbrüche konvertieren (Windows CRLF -> Linux LF)
# Verhindert den berüchtigten 'bash: \r: command not found' Fehler auf Linux
Write-Host "[3/5] Konvertiere Skript-Zeilenumbrüche zu Unix-LF..." -ForegroundColor Gray

function ConvertTo-LinuxLF ($filePath) {
    if (Test-Path $filePath) {
        $content = [System.IO.File]::ReadAllText($filePath)
        $content = $content.Replace("`r`n", "`n").Replace("`r", "`n")
        [System.IO.File]::WriteAllText($filePath, $content, (New-Object System.Text.UTF8Encoding($false)))
    }
}

ConvertTo-LinuxLF (Join-Path $StagingDir "pr0-retroconsole.sh")
ConvertTo-LinuxLF (Join-Path $StagingAppDir "install.sh")
ConvertTo-LinuxLF (Join-Path $StagingAppDir "pr0.gptk")
ConvertTo-LinuxLF (Join-Path $StagingAppDir "pr0_mpv_input.conf")

# 5. Sanity Check: Prüfe, dass keine .exe oder Windows-Binaries im Paket landen
Write-Host "[4/5] Prüfe auf unerwünschte Binaries..." -ForegroundColor Gray
$unwanted = Get-ChildItem -Path $StagingDir -Recurse -Include "*.exe", "*.bat", "*.ps1"
if ($unwanted) {
    Write-Host "WARNUNG: Unerwünschte Dateien gefunden, werden entfernt:" -ForegroundColor Yellow
    $unwanted | ForEach-Object {
        Write-Host "  - Entf: $($_.FullName)" -ForegroundColor DarkYellow
        Remove-Item -Force $_.FullName
    }
}

# 6. ZIP-Archive erstellen
Write-Host "[5/5] Erstelle ZIP-Archiv: $ZipOutputVersioned..." -ForegroundColor Gray
Compress-Archive -Path "$StagingDir\*" -DestinationPath $ZipOutputVersioned -Force
try { Copy-Item $ZipOutputVersioned -Destination $ZipOutputCompat -Force -ErrorAction Stop } catch { Write-Host "Hinweis: $ZipOutputCompat konnte nicht aktualisiert werden (geöffnet)." -ForegroundColor DarkYellow }

# Bereinige Staging-Ordner
Remove-Item -Recurse -Force $StagingDir

# 7. Abschlussbericht
$zipItem = Get-Item $ZipOutputVersioned
$sizeKB = [math]::Round($zipItem.Length / 1KB, 1)
$sizeMB = [math]::Round($zipItem.Length / 1MB, 2)

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  ERFOLG: Release-ZIP (v$Version) erfolgreich erstellt!   " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Version:      v$Version" -ForegroundColor Yellow
Write-Host "Release-ZIP:  $ZipOutputVersioned" -ForegroundColor White
Write-Host "Kompat-ZIP:   $ZipOutputCompat" -ForegroundColor DarkGray
Write-Host "Größe:        $sizeKB KB ($sizeMB MB)" -ForegroundColor Yellow
Write-Host "`nInstallation auf dem Handheld (R36S / TrimUI Smart Pro):" -ForegroundColor Cyan
Write-Host "1. Stecke deine SD-Karte in den PC." -ForegroundColor Gray
Write-Host "2. Öffne den Ordner 'ports' auf der SD-Karte (z.B. E:\roms\ports\)." -ForegroundColor Gray
Write-Host "3. Entpacke den Inhalt von '$($zipItem.Name)' direkt in diesen 'ports'-Ordner." -ForegroundColor Gray
Write-Host "   -> Es muss 'pr0-retroconsole.sh' direkt in 'ports/' liegen." -ForegroundColor DarkGray
Write-Host "   -> Daneben der Ordner 'pr0-retroconsole/' mit dem Code." -ForegroundColor DarkGray
Write-Host "4. SD-Karte wieder in den Handheld stecken, im Menü 'Ports' starten & fertig!" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan
