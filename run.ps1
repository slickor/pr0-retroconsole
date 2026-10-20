# PowerShell Start-Skript für pr0-retroconsole auf Windows

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "      pr0-retroconsole Starter          " -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Pfad: $ScriptDir" -ForegroundColor Gray

# Prüfe ob Python verfügbar ist
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "FEHLER: Python wurde nicht im PATH gefunden!" -ForegroundColor Red
    Write-Host "Bitte installiere Python von https://www.python.org/" -ForegroundColor Yellow
    Read-Host "Drücke Enter zum Beenden..."
    exit 1
}

# Prüfe / Installiere Abhängigkeiten falls nötig
Write-Host "Prüfe Abhängigkeiten (pygame, requests, Pillow)..." -ForegroundColor Gray
python -c "import pygame, requests, PIL" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installiere fehlende Pakete aus requirements.txt..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FEHLER bei der Paketinstallation!" -ForegroundColor Red
        Read-Host "Drücke Enter zum Beenden..."
        exit 1
    }
}

# Starte Anwendung
Write-Host "Starte pr0-retroconsole..." -ForegroundColor Green
python src/main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nAnwendung wurde mit Fehlercode $LASTEXITCODE beendet." -ForegroundColor Red
    Read-Host "Drücke Enter zum Schließen..."
}
