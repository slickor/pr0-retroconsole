# ==============================================================================
# install.ps1 - Automatischer SD-Karten Installer fuer pr0-retroconsole
# ==============================================================================
# Sprache: Deutsch (pr0-Amtssprache) • Architektur: 100% zertifizierter Vibecode
# Installiert oder aktualisiert pr0-retroconsole auf jeder eingesteckten SD-Karte
# (TrimUI Smart Pro, R36S, Anbernic, muOS, Knulli, ArkOS, CrossMix-OS, Batocera, etc.).
# ==============================================================================

param(
    [string]$Drive = "",
    [switch]$Force,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

# Zu ignorierende Ordner (Scraper, Cache, OS-Metadaten)
$global:IgnoredDirNames = @(
    'System Volume Information', '$RECYCLE.BIN', '.Spotlight-V100', '.Trashes',
    'cache', 'output', 'application', '.scrappy', '__pycache__'
)
$global:IgnoredAppNames = @(
    'media', 'covers', 'backcovers', 'fanarts', 'marquees',
    'screenshots', 'wheels', 'manuals', 'textures'
)

function Write-Pr0Header {
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host "   pr0-retroconsole - Automatischer SD-Karten Installer    " -ForegroundColor Yellow
    Write-Host "       [ 100% Vibecode  •  Amtssprache: Deutsch ]          " -ForegroundColor Gray
    Write-Host "============================================================" -ForegroundColor Cyan
}

function ConvertTo-UnixLF {
    param ([string]$FilePath)
    if (Test-Path -LiteralPath $FilePath -PathType Leaf) {
        try {
            $bytes = [System.IO.File]::ReadAllBytes($FilePath)
            $text = [System.Text.Encoding]::UTF8.GetString($bytes)
            # Normalisiere Windows CRLF und altes Mac CR zu Unix LF
            $text = $text -replace "\r\n", "`n" -replace "\r", "`n"
            [System.IO.File]::WriteAllBytes($FilePath, [System.Text.Encoding]::UTF8.GetBytes($text))
        } catch {
            Write-Warning "Konnte Zeilenumbrueche fuer $FilePath nicht konvertieren: $_"
        }
    }
}

function Copy-DirectoryFiltered {
    param (
        [string]$Source,
        [string]$Destination,
        [string[]]$ExcludePatterns = @('__pycache__', '*.pyc', '*.pyo', '*presentation*', '*.psd', '*.ai')
    )
    if (-not (Test-Path -LiteralPath $Destination)) {
        New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    }

    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        $item = $_
        $skip = $false
        foreach ($pat in $ExcludePatterns) {
            if ($item.Name -like $pat) {
                $skip = $true
                break
            }
        }
        if (-not $skip) {
            $destPath = Join-Path $Destination $item.Name
            if ($item.PSIsContainer) {
                Copy-DirectoryFiltered -Source $item.FullName -Destination $destPath -ExcludePatterns $ExcludePatterns
            } else {
                Copy-Item -LiteralPath $item.FullName -Destination $destPath -Force
                # Shell-Skripte und Konfigurationsdateien zu Unix LF konvertieren
                if ($item.Extension -in ('.sh', '.py', '.gptk', '.conf', '.json', '.txt', '.md')) {
                    ConvertTo-UnixLF -FilePath $destPath
                }
            }
        }
    }
}

function Get-PartitionName {
    param ([string]$DriveLetter)
    $clean = $DriveLetter.TrimEnd(':\')
    try {
        $dInfo = [System.IO.DriveInfo]::new("$clean`:\")
        if ($dInfo -and -not [string]::IsNullOrWhiteSpace($dInfo.VolumeLabel)) {
            return $dInfo.VolumeLabel
        }
    } catch {}

    $logDisk = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID = '$clean`:'" -ErrorAction SilentlyContinue
    if ($logDisk -and -not [string]::IsNullOrWhiteSpace($logDisk.VolumeName)) {
        return $logDisk.VolumeName
    }
    return "Kein Name"
}

function Test-IsBootPartition {
    param ([string]$RootPath, [string]$Label)
    if ($Label -match '^(KNULLI|BATOCERA|BOOT|RECALBOX|ROCKNIX|JELOS|EMUELEC)$') { return $true }
    if (Test-Path -LiteralPath (Join-Path $RootPath "knulli-boot.conf")) { return $true }
    if (Test-Path -LiteralPath (Join-Path $RootPath "batocera-boot.conf")) { return $true }
    if (Test-Path -LiteralPath (Join-Path $RootPath "recalbox-boot.conf")) { return $true }
    if (Test-Path -LiteralPath (Join-Path $RootPath "rocknix-boot.conf")) { return $true }
    if (Test-Path -LiteralPath (Join-Path $RootPath "jelos-boot.conf")) { return $true }
    # Hat boot/ oder dtb/ aber weder roms noch ports
    if (((Test-Path -LiteralPath (Join-Path $RootPath "boot")) -or (Test-Path -LiteralPath (Join-Path $RootPath "dtb"))) -and 
        (-not (Test-Path -LiteralPath (Join-Path $RootPath "roms"))) -and 
        (-not (Test-Path -LiteralPath (Join-Path $RootPath "Roms"))) -and 
        (-not (Test-Path -LiteralPath (Join-Path $RootPath "ports")))) {
        return $true
    }
    return $false
}

Write-Pr0Header

# 1. Quell-Version ermitteln
$version = "0.4.10"
try {
    $verOut = python -c "import src.version; print(src.version.VERSION)" 2>$null
    if ($verOut) { $version = "$verOut".Trim() }
} catch {}
Write-Host "Quell-Version: v$version ($ProjectRoot)`n" -ForegroundColor Gray

# 2. Externe Laufwerke suchen & intelligente Partitionsauswahl
$targetDrive = $null
if ($Drive) {
    $cleanDrive = $Drive.TrimEnd(':\') + ":\"
    if (Test-Path $cleanDrive) {
        $targetDrive = [PSCustomObject]@{
            Name  = $Drive.TrimEnd(':\')
            Root  = $cleanDrive
            Label = Get-PartitionName -DriveLetter $Drive
        }
    } else {
        Write-Host "FEHLER: Angegebenes Laufwerk '$Drive' wurde nicht gefunden!" -ForegroundColor Red
        exit 1
    }
}

while (-not $targetDrive) {
    $rawDrives = Get-PSDrive -PSProvider FileSystem | Where-Object { 
        $_.Name -ne "C" -and $_.Root -and (Test-Path $_.Root)
    }

    if (-not $rawDrives) {
        Write-Host "Keine externen Laufwerke oder SD-Karten gefunden!" -ForegroundColor Yellow
        Write-Host "Bitte SD-Karte einlegen oder Laufwerksbuchstaben manuell eingeben." -ForegroundColor Gray
        $in = Read-Host "`nLaufwerksbuchstabe (z.B. 'E') oder [R] fuer erneuten Scan, [Q] zum Beenden"
        if ($in -ieq "q") { exit 0 }
        if ($in -and $in -ine "r") {
            $manualRoot = "$($in.TrimEnd(':\'))`:\"
            if (Test-Path $manualRoot) {
                $targetDrive = [PSCustomObject]@{
                    Name  = $in.TrimEnd(':\')
                    Root  = $manualRoot
                    Label = Get-PartitionName -DriveLetter $in
                }
                break
            } else {
                Write-Host "Pfad '$manualRoot' existiert nicht!" -ForegroundColor Red
            }
        }
        continue
    }

    # Laufwerksinformationen sammeln und zwischen Boot- und Daten-Partitionen unterscheiden
    $driveInfoList = [System.Collections.Generic.List[PSCustomObject]]::new()
    foreach ($d in $rawDrives) {
        $label = Get-PartitionName -DriveLetter $d.Name
        $isBoot = Test-IsBootPartition -RootPath $d.Root -Label $label
        $freeGb = [math]::Round($d.Free / 1GB, 1)
        $hasGames = (Test-Path (Join-Path $d.Root "roms")) -or 
                    (Test-Path (Join-Path $d.Root "Roms")) -or 
                    (Test-Path (Join-Path $d.Root "ports")) -or 
                    (Test-Path (Join-Path $d.Root "Emus")) -or 
                    (Test-Path (Join-Path $d.Root "Data\ports")) -or 
                    ($label -in @("SHARE", "EASYROMS", "GAMES", "ROMS", "PORTMASTER"))

        $driveInfoList.Add([PSCustomObject]@{
            DriveObj = $d
            Name     = $d.Name
            Root     = $d.Root
            Label    = $label
            FreeGb   = $freeGb
            IsBoot   = $isBoot
            HasGames = $hasGames
        })
    }

    # Intelligente Knulli / Batocera Erkennung (Boot- vs. SHARE-Partition)
    $dataPartitions = @($driveInfoList | Where-Object { -not $_.IsBoot })
    $bootPartitions = @($driveInfoList | Where-Object { $_.IsBoot })

    if ($driveInfoList.Count -eq 1) {
        $single = $driveInfoList[0]
        $targetDrive = [PSCustomObject]@{
            Name  = $single.Name
            Root  = $single.Root
            Label = $single.Label
        }
        Write-Host "Automatisch erkannte SD-Karte: $($targetDrive.Name): ($($targetDrive.Label)) - $($single.FreeGb) GB frei" -ForegroundColor Green
    } elseif ($dataPartitions.Count -eq 1 -and $bootPartitions.Count -ge 1) {
        # Z.B. Knulli mit D: (KNULLI Boot) und E: (SHARE Daten)
        $autoData = $dataPartitions[0]
        $bootNames = ($bootPartitions | ForEach-Object { "$($_.Name): ($($_.Label))" }) -join ", "
        Write-Host "Multi-Partition SD-Karte erkannt (Boot: $bootNames)" -ForegroundColor Cyan
        Write-Host "Automatisch ausgewaehlte Spiele-Partition: $($autoData.Name): ($($autoData.Label)) - $($autoData.FreeGb) GB frei" -ForegroundColor Green
        $targetDrive = [PSCustomObject]@{
            Name  = $autoData.Name
            Root  = $autoData.Root
            Label = $autoData.Label
        }
    } else {
        # Mehrere echte Daten-Partitionen oder unklare Lage
        Write-Host "Mehrere externe Laufwerke gefunden:" -ForegroundColor Cyan
        for ($i = 0; $i -lt $driveInfoList.Count; $i++) {
            $di = $driveInfoList[$i]
            $tag = if ($di.IsBoot) { "[System/Boot - nicht fuer Spiele]" } elseif ($di.HasGames) { "[Spiele/ROMs Partition]" } else { "" }
            Write-Host "  [$($i+1)] $($di.Name): ($($di.Label)) - $($di.FreeGb) GB frei  $tag" -ForegroundColor White
        }
        $choice = Read-Host "`nNummer der gewuenschten SD-Karte waehlen [1-$($driveInfoList.Count)] (Standard: 1)"
        if (-not $choice) { $choice = 1 }
        $idx = [int]$choice - 1
        if ($idx -ge 0 -and $idx -lt $driveInfoList.Count) {
            $sel = $driveInfoList[$idx]
            $targetDrive = [PSCustomObject]@{
                Name  = $sel.Name
                Root  = $sel.Root
                Label = $sel.Label
            }
        } else {
            Write-Host "Ungueltige Auswahl!" -ForegroundColor Red
        }
    }
}

# 3. Intelligente Analyse des gewaehlten Laufwerks (muOS, Knulli, ArkOS, TrimUI CrossMix)
Write-Host "`nAnalysiere SD-Karten-Struktur auf $($targetDrive.Name): ($($targetDrive.Label))..." -ForegroundColor Cyan
$driveRoot = $targetDrive.Root

# 3a. Gezielte Suche nach 'ports'-Ordnern (ohne zeitraubenden Gesamt-Scan von Tausenden ROMs)
$discoveredPortsMap = @{} # LowerCase Pfad -> DirectoryInfo

# Standard-Kandidatenpfade
$standardSubDirs = @(
    "roms\ports",
    "ROMS\ports",
    "Roms\PORTS",
    "roms2\ports",
    "userdata\roms\ports",
    "Emus\PORTS",
    "MUOS\ports",
    "Data\ports",
    "ports"
)

foreach ($sub in $standardSubDirs) {
    $candPath = Join-Path $driveRoot $sub
    if (Test-Path -LiteralPath $candPath -PathType Container) {
        $realItem = Get-Item -LiteralPath $candPath -ErrorAction SilentlyContinue
        if ($realItem) {
            $key = $realItem.FullName.ToLowerInvariant()
            if (-not $discoveredPortsMap.ContainsKey($key)) {
                $discoveredPortsMap[$key] = $realItem
            }
        }
    }
}

# Flacher 2-Ebenen-Scan nach weiteren ports-Ordnern (falls abweichende Gross-/Kleinschreibung)
if ($discoveredPortsMap.Count -eq 0) {
    $lvl1Dirs = Get-ChildItem -LiteralPath $driveRoot -Directory -Force -ErrorAction SilentlyContinue |
                Where-Object { $global:IgnoredDirNames -notcontains $_.Name }
    foreach ($d1 in $lvl1Dirs) {
        if ($d1.Name -ieq "ports") {
            $discoveredPortsMap[$d1.FullName.ToLowerInvariant()] = $d1
        } else {
            $lvl2Dirs = Get-ChildItem -LiteralPath $d1.FullName -Directory -Force -ErrorAction SilentlyContinue |
                        Where-Object { $global:IgnoredDirNames -notcontains $_.Name }
            foreach ($d2 in $lvl2Dirs) {
                if ($d2.Name -ieq "ports") {
                    $discoveredPortsMap[$d2.FullName.ToLowerInvariant()] = $d2
                }
            }
        }
    }
}

$allPortsDirs = @($discoveredPortsMap.Values)

# 3b. Bestehende Installation suchen (Update-Erkennung)
$existingLauncher = $null
$existingAppDir   = $null

# Pruefe die gefundenen Ports-Verzeichnisse direkt auf pr0-retroconsole.sh
foreach ($pDir in $allPortsDirs) {
    $candSh = Join-Path $pDir.FullName "pr0-retroconsole.sh"
    if (Test-Path -LiteralPath $candSh -PathType Leaf) {
        $existingLauncher = $candSh
        break
    }
}

# Pruefe wo das Programmverzeichnis pr0-retroconsole liegt:
# Entweder in einem der Ports-Verzeichnisse (z.B. Unified: roms\ports\pr0-retroconsole)
# oder im Root-Ports-Verzeichnis (z.B. muOS: D:\ports\pr0-retroconsole)
foreach ($pDir in $allPortsDirs) {
    $candApp = Join-Path $pDir.FullName "pr0-retroconsole"
    if (Test-Path -LiteralPath $candApp -PathType Container) {
        $existingAppDir = $candApp
        break
    }
}

$rootPortsDir = Join-Path $driveRoot "ports"
$hasRootPorts = Test-Path -LiteralPath $rootPortsDir -PathType Container
if (-not $existingAppDir -and $hasRootPorts) {
    $candAppRoot = Join-Path $rootPortsDir "pr0-retroconsole"
    if (Test-Path -LiteralPath $candAppRoot -PathType Container) {
        $existingAppDir = $candAppRoot
    }
}

# 3c. CFW-Systemidentifikation
$cfwName = "Unbekannt"
$hasKnulliConf   = Test-Path -LiteralPath (Join-Path $driveRoot "system\knulli.conf")
$hasBatoceraConf = Test-Path -LiteralPath (Join-Path $driveRoot "system\batocera.conf")
$hasAmberConf    = Test-Path -LiteralPath (Join-Path $driveRoot "system\amberelec.conf")
$hasRocknixConf  = (Test-Path -LiteralPath (Join-Path $driveRoot "system\rocknix")) -or (Test-Path -LiteralPath (Join-Path $driveRoot "rocknix-boot.conf"))
$hasJelosConf    = (Test-Path -LiteralPath (Join-Path $driveRoot "system\jelos")) -or (Test-Path -LiteralPath (Join-Path $driveRoot "jelos-boot.conf"))
$hasMuOSDir      = Test-Path -LiteralPath (Join-Path $driveRoot "MUOS")
$hasEmusDir      = Test-Path -LiteralPath (Join-Path $driveRoot "Emus")
$hasDataPorts    = Test-Path -LiteralPath (Join-Path $driveRoot "Data\ports")
$hasTrimuiDir    = Test-Path -LiteralPath (Join-Path $driveRoot "trimui")

$siblingBootKnulli = Get-PSDrive -PSProvider FileSystem | Where-Object { 
    $_.Name -ne "C" -and (Test-Path (Join-Path $_.Root "knulli-boot.conf"))
}
$siblingBootArkOS = Get-PSDrive -PSProvider FileSystem | Where-Object { 
    $_.Name -ne "C" -and ((Test-Path (Join-Path $_.Root "rk3326-r36s-linux.dtb")) -or (Test-Path (Join-Path $_.Root "boot.ini")))
}
$siblingBootRocknix = Get-PSDrive -PSProvider FileSystem | Where-Object { 
    $_.Name -ne "C" -and (Test-Path (Join-Path $_.Root "rocknix-boot.conf"))
}

if ($hasKnulliConf -or $siblingBootKnulli -or $targetDrive.Label -ieq "KNULLI") {
    $cfwName = "Knulli (TrimUI / Linux Handheld)"
} elseif ($hasBatoceraConf -or $targetDrive.Label -ieq "BATOCERA") {
    $cfwName = "Batocera"
} elseif ($hasAmberConf -or $targetDrive.Label -ieq "GAMES") {
    $cfwName = "AmberELEC (RG351 / RK3326)"
} elseif ($hasRocknixConf -or $siblingBootRocknix -or $targetDrive.Label -ieq "ROCKNIX") {
    $cfwName = "ROCKNIX (RK3566 / Handheld)"
} elseif ($hasJelosConf -or $targetDrive.Label -ieq "JELOS") {
    $cfwName = "JELOS"
} elseif ($targetDrive.Label -ieq "EASYROMS" -or $siblingBootArkOS) {
    if ($siblingBootArkOS) {
        $cfwName = "ArkOS (R36S / RK3326)"
    } else {
        $cfwName = "ArkOS (Slot 2 / TF2 ROMs)"
    }
} elseif ($hasMuOSDir) {
    $cfwName = "muOS"
} elseif ($hasDataPorts -or $hasTrimuiDir -or $hasEmusDir) {
    $cfwName = "TrimUI (CrossMix-OS / MinUI)"
} elseif (Test-Path -LiteralPath (Join-Path $driveRoot "Roms\PORTS")) {
    $cfwName = "Anbernic Stock OS (H700 / RG35XX)"
}

# Mismatch-Analyse fuer muOS / PortMaster:
# Pruefe ob vorhandene Starter-Dateien in ROMS\ports auf Ordner in \ports verweisen
$romsPortsDir = $allPortsDirs | Where-Object { $_.FullName -match "roms[\\/]ports" } | Select-Object -First 1
$splitModeDetected = $false
if ($romsPortsDir -and $hasRootPorts -and ($hasMuOSDir -or -not $hasKnulliConf)) {
    $shInLauncherDir = Get-ChildItem -LiteralPath $romsPortsDir.FullName -File -Filter "*.sh" -Force -ErrorAction SilentlyContinue
    foreach ($sh in $shInLauncherDir) {
        $content = Get-Content -LiteralPath $sh.FullName -Raw -ErrorAction SilentlyContinue
        if ($content -match 'GAMEDIR\s*=\s*["'']?(?:/[^/'']+)?/ports/([^/''"\s\n\r]+)' -or
            $content -match 'cd\s+["'']?(?:.*/)?ports/([^/''"\s\n\r]+)') {
            $targetFolderName = $matches[1]
            if (Test-Path -LiteralPath (Join-Path $rootPortsDir $targetFolderName)) {
                $splitModeDetected = $true
                break
            }
        }
    }
}

# 3d. Bestimme finale Zielpfade
$destLauncherDir  = $null
$destAppParentDir = $null
$detectedSystem   = $cfwName

if ($existingLauncher -and $existingAppDir) {
    # Bestehende Installation wiederverwenden
    $destLauncherDir  = [System.IO.Path]::GetDirectoryName($existingLauncher)
    $destAppParentDir = [System.IO.Path]::GetDirectoryName($existingAppDir)
    $archType = if ($destLauncherDir.ToLowerInvariant() -eq $destAppParentDir.ToLowerInvariant()) { "Unified Architecture" } else { "Split Architecture" }
    $detectedSystem   = "$cfwName ($archType - Bestehende Installation)"
} elseif ($hasDataPorts) {
    # CrossMix-OS / MinUI Split-Architektur (Launcher in Roms\PORTS oder Emus\PORTS, App in Data\ports)
    $candLauncher = @("Roms\PORTS", "Emus\PORTS", "Data\ports") | ForEach-Object { Join-Path $driveRoot $_ } | Where-Object { Test-Path $_ } | Select-Object -First 1
    $destLauncherDir  = if ($candLauncher) { $candLauncher } else { Join-Path $driveRoot "Roms\PORTS" }
    $destAppParentDir = Join-Path $driveRoot "Data\ports"
    $detectedSystem   = "$cfwName (Split: Launcher in $([System.IO.Path]::GetFileName($destLauncherDir)) | App in Data\ports)"
} elseif ($hasMuOSDir -or $splitModeDetected) {
    # muOS Neuinstallation: Starter in ROMS\ports, App in ports\pr0-retroconsole
    $destLauncherDir  = if ($romsPortsDir) { $romsPortsDir.FullName } else { Join-Path $driveRoot "ROMS\ports" }
    $destAppParentDir = $rootPortsDir
    $detectedSystem   = "muOS (Split: ROMS\ports + ports\)"
} elseif ($allPortsDirs.Count -eq 1) {
    # Ein einzelner gefundener Ports-Ordner (Knulli, CrossMix, ArkOS, AmberELEC etc.)
    $singlePorts      = $allPortsDirs[0]
    $destLauncherDir  = $singlePorts.FullName
    $destAppParentDir = $singlePorts.FullName
    if ($cfwName -eq "Unbekannt") {
        if ($singlePorts.FullName -match "userdata") { $detectedSystem = "Knulli / Batocera" }
        elseif ($singlePorts.FullName -match "Emus") { $detectedSystem = "TrimUI (CrossMix-OS)" }
        elseif ($singlePorts.FullName -match "roms2") { $detectedSystem = "ArkOS / AmberELEC (SD2)" }
        elseif ($singlePorts.FullName -match "roms") { $detectedSystem = "ArkOS / AmberELEC" }
        else { $detectedSystem = "PortMaster" }
    } else {
        $detectedSystem = "$cfwName (Unified Architecture)"
    }
} elseif ($allPortsDirs.Count -gt 1) {
    # Mehrere Ports-Ordner gefunden
    $romsPorts = $allPortsDirs | Where-Object { $_.FullName -match "roms[\\/]ports" } | Select-Object -First 1
    $knulli    = $allPortsDirs | Where-Object { $_.FullName -match "userdata" } | Select-Object -First 1
    $crossmix  = $allPortsDirs | Where-Object { $_.FullName -match "Emus" } | Select-Object -First 1
    
    if ($hasKnulliConf -and $romsPorts) {
        $destLauncherDir  = $romsPorts.FullName
        $destAppParentDir = $romsPorts.FullName
        $detectedSystem   = "Knulli (TrimUI / Linux Handheld)"
    } elseif ($knulli) {
        $destLauncherDir  = $knulli.FullName
        $destAppParentDir = $knulli.FullName
        $detectedSystem   = "Knulli / Batocera"
    } elseif ($crossmix) {
        $destLauncherDir  = $crossmix.FullName
        $destAppParentDir = $crossmix.FullName
        $detectedSystem   = "TrimUI (CrossMix-OS)"
    } else {
        Write-Host "`nMehrere Ports-Ordner gefunden:" -ForegroundColor Cyan
        for ($i = 0; $i -lt $allPortsDirs.Count; $i++) {
            $p = $allPortsDirs[$i]
            Write-Host "  [$($i+1)] $($p.FullName)" -ForegroundColor White
        }
        $c = Read-Host "`nNummer des Ziel-Verzeichnisses waehlen [1-$($allPortsDirs.Count)] (Standard: 1)"
        if (-not $c) { $c = 1 }
        $chosen = $allPortsDirs[[int]$c - 1]
        $destLauncherDir  = $chosen.FullName
        $destAppParentDir = $chosen.FullName
        $detectedSystem   = "Benutzerdefiniert"
    }
} else {
    # Gar kein Ports-Ordner gefunden: Standard vorschlagen
    $destLauncherDir  = Join-Path $driveRoot "roms\ports"
    $destAppParentDir = $destLauncherDir
    $detectedSystem   = "Standard (Neu)"
}

$destShPath  = Join-Path $destLauncherDir "pr0-retroconsole.sh"
$destAppPath = Join-Path $destAppParentDir "pr0-retroconsole"
$isUpdate    = (Test-Path -LiteralPath $destAppPath)

# 4. Zusammenfassung anzeigen
Write-Host "`n------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Ziel-Konfiguration:" -ForegroundColor Yellow
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  SD-Karte:          $($targetDrive.Name): ($($targetDrive.Label))" -ForegroundColor White
Write-Host "  Erkanntes System:  $detectedSystem" -ForegroundColor White
Write-Host "  Starter-Skript:    $destShPath" -ForegroundColor White
Write-Host "  Programm-Ordner:   $destAppPath" -ForegroundColor White
Write-Host "  Installations-Art: $(if ($isUpdate) { 'Aktualisierung (Update)' } else { 'Neuinstallation' }) auf v$version" -ForegroundColor $(if ($isUpdate) { 'Cyan' } else { 'Green' })

$existingConfig = Join-Path $destAppPath "config.json"
if (Test-Path -LiteralPath $existingConfig) {
    Write-Host "  Konfiguration:     Bestehende config.json wird beibehalten (Login bleibt erhalten)" -ForegroundColor Green
} else {
    Write-Host "  Konfiguration:     Neue config.json wird aus config.example.json erstellt" -ForegroundColor Gray
}
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray

if ($CheckOnly) {
    Write-Host "`n[-CheckOnly Modus aktiv - Keine Dateien geschrieben]`n" -ForegroundColor Yellow
    exit 0
}

# 5. Bestaetigung anfordern (ausser bei -Force)
if (-not $Force) {
    $proceed = Read-Host "`nInstallation jetzt starten? [J/n]"
    if ($proceed -and $proceed -inotmatch "^(j|y|ja|yes)$") {
        Write-Host "Abgebrochen durch Benutzer." -ForegroundColor Yellow
        exit 0
    }
}

# 6. Installation durchfuehren
Write-Host "`n[1/3] Kopiere Starter-Skript 'pr0-retroconsole.sh'..." -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $destLauncherDir)) {
    New-Item -ItemType Directory -Path $destLauncherDir -Force | Out-Null
}
$srcSh = Join-Path $ProjectRoot "pr0-retroconsole.sh"
Copy-Item -LiteralPath $srcSh -Destination $destShPath -Force
ConvertTo-UnixLF -FilePath $destShPath

Write-Host "[2/3] Kopiere Programmdateien nach '$destAppPath'..." -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $destAppPath)) {
    New-Item -ItemType Directory -Path $destAppPath -Force | Out-Null
}

# Unterordner kopieren
Copy-DirectoryFiltered -Source (Join-Path $ProjectRoot "src") -Destination (Join-Path $destAppPath "src")

if (Test-Path -LiteralPath (Join-Path $ProjectRoot "tools")) {
    Copy-DirectoryFiltered -Source (Join-Path $ProjectRoot "tools") -Destination (Join-Path $destAppPath "tools")
}
if (Test-Path -LiteralPath (Join-Path $ProjectRoot "assets")) {
    Copy-DirectoryFiltered -Source (Join-Path $ProjectRoot "assets") -Destination (Join-Path $destAppPath "assets")
}
if (Test-Path -LiteralPath (Join-Path $ProjectRoot "libs")) {
    Copy-DirectoryFiltered -Source (Join-Path $ProjectRoot "libs") -Destination (Join-Path $destAppPath "libs")
}

# Einzeldateien kopieren
$rootFiles = @(
    "pr0.gptk",
    "pr0_mpv_input.conf",
    "install.sh",
    "requirements.txt",
    "README.md",
    "LICENSE",
    "config.example.json"
)

foreach ($f in $rootFiles) {
    $srcF = Join-Path $ProjectRoot $f
    if (Test-Path -LiteralPath $srcF) {
        $dstF = Join-Path $destAppPath $f
        Copy-Item -LiteralPath $srcF -Destination $dstF -Force
        ConvertTo-UnixLF -FilePath $dstF
    }
}

# 7. Konfiguration behandeln
Write-Host "[3/3] Pruefe Konfiguration..." -ForegroundColor Cyan
if (Test-Path -LiteralPath $existingConfig) {
    Write-Host "  -> Bestehende config.json beibehalten (Login & Einstellungen bleiben erhalten)." -ForegroundColor Green
} else {
    $exampleConfig = Join-Path $destAppPath "config.example.json"
    if (Test-Path -LiteralPath $exampleConfig) {
        Copy-Item -LiteralPath $exampleConfig -Destination $existingConfig -Force
        ConvertTo-UnixLF -FilePath $existingConfig
        Write-Host "  -> Neue config.json aus Vorlage erstellt." -ForegroundColor Gray
    }
}

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "  ERFOLG: pr0-retroconsole v$version erfolgreich installiert! " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Starter: $destShPath" -ForegroundColor White
Write-Host "  Ordner:  $destAppPath" -ForegroundColor White
Write-Host "`n  Du kannst die SD-Karte nun sicher auswerfen und in deinen" -ForegroundColor Yellow
Write-Host "  Handheld stecken. Viel Spass auf pr0gramm!" -ForegroundColor Yellow
Write-Host "============================================================`n" -ForegroundColor Green
