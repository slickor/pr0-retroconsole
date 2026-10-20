# ==============================================================================
# push.ps1 - Automatischer Git Commit & Push fuer pr0-retroconsole
# ==============================================================================
# Verwendung:
#   .\push.ps1
#   .\push.ps1 "Beschreibung der Aenderungen"
#   .\push.ps1 -Message "Fix: Video-Sound" -Build
#   .\push.ps1 -Tag
# ==============================================================================

param(
    [string]$Message = "",
    [switch]$Build,
    [switch]$Tag
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         pr0-retroconsole - GitHub Push Utility           " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Version aus src/version.py auslesen
$Version = "0.3.2"
try {
    $verOut = python -c "import src.version; print(src.version.VERSION)" 2>$null
    if ($verOut) {
        $Version = "$verOut".Trim()
    }
} catch {
    $Version = "0.3.2"
}

Write-Host "Projektverzeichnis: $ScriptDir" -ForegroundColor Gray
Write-Host "Aktuelle Version:   v$Version" -ForegroundColor Yellow

# 2. Optional: Release-ZIP neu bauen vor dem Push
if ($Build) {
    Write-Host "`n[1/4] Baue Release-Paket mit build.ps1..." -ForegroundColor Cyan
    powershell -ExecutionPolicy Bypass -File (Join-Path $ScriptDir "build.ps1")
}

# 3. Git-Repository & Remote ueberpruefen
if (-not (Test-Path (Join-Path $ScriptDir ".git"))) {
    Write-Host "`nInitialisiere Git-Repository..." -ForegroundColor DarkYellow
    git init -b main
}

$remotes = git remote -v 2>$null
if (-not ($remotes -match "origin")) {
    $defaultRemote = "https://github.com/slickor/pr0-retroconsole.git"
    Write-Host "Setze Git Remote 'origin' auf $defaultRemote..." -ForegroundColor DarkYellow
    git remote add origin $defaultRemote
}

# 4. Aenderungen stagen und pruefen
Write-Host "`n[2/4] Pruefe Aenderungen (git status)..." -ForegroundColor Gray
git add .

$status = git status --porcelain
if (-not $status) {
    Write-Host "Keine geaenderten Dateien im Arbeitsverzeichnis." -ForegroundColor Green
    
    # Pruefen, ob noch ungesendete Commits vorliegen
    $unpushed = git log '@{u}..' --oneline 2>$null
    if ($unpushed) {
        Write-Host "`nAusstehende lokale Commits gefunden:" -ForegroundColor Yellow
        $unpushed | ForEach-Object { Write-Host "  - $_" -ForegroundColor DarkGray }
        Write-Host "`n[3/4] Pushe ausstehende Commits zu GitHub..." -ForegroundColor Cyan
        git push origin main
        Write-Host "Erfolgreich gepusht!" -ForegroundColor Green
    } else {
        Write-Host "Alles ist bereits auf dem neuesten Stand auf GitHub!" -ForegroundColor Cyan
    }
} else {
    Write-Host "Geaenderte Dateien erkannt:" -ForegroundColor Yellow
    $status | ForEach-Object {
        $line = $_.Trim()
        Write-Host "  $line" -ForegroundColor DarkYellow
    }

    # 5. Commit-Nachricht bestimmen
    $commitMsg = $Message
    if (-not $commitMsg) {
        $timeStr = (Get-Date).ToString("yyyy-MM-dd HH:mm")
        $defaultMsg = "Update v$Version ($timeStr)"
        
        # Falls interaktive Konsole: Benutzer fragen, sonst Default verwenden
        if ([System.Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
            $inputMsg = Read-Host "`nCommit-Nachricht eingeben (Enter fuer '$defaultMsg')"
            if ($inputMsg) {
                $commitMsg = $inputMsg
            } else {
                $commitMsg = $defaultMsg
            }
        } else {
            $commitMsg = $defaultMsg
        }
    }

    # 6. Commit erstellen
    Write-Host "`n[3/4] Erstelle Commit: '$commitMsg'..." -ForegroundColor Cyan
    git commit -m "$commitMsg"

    # 7. Pushen
    Write-Host "`n[4/4] Pushe Aenderungen zu GitHub (origin/main)..." -ForegroundColor Cyan
    git push -u origin main
}

# 8. Optional: Git-Tag erstellen und pushen
if ($Tag) {
    $tagName = "v$Version"
    Write-Host "`nErstelle und pushe Release-Tag '$tagName'..." -ForegroundColor Cyan
    try {
        git tag -fa $tagName -m "Release $tagName"
        git push origin $tagName --force
        Write-Host "Tag '$tagName' erfolgreich gepusht!" -ForegroundColor Green
    } catch {
        Write-Host "Hinweis beim Tag-Push: $_" -ForegroundColor DarkYellow
    }
}

# Abschlussbericht
Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "   ERFOLG: Repository ist synchronisiert mit GitHub!      " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "GitHub URL:   https://github.com/slickor/pr0-retroconsole" -ForegroundColor White
Write-Host "Releases:     https://github.com/slickor/pr0-retroconsole/releases" -ForegroundColor DarkGray
Write-Host "==========================================================" -ForegroundColor Cyan
