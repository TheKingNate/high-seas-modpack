@echo off
set "PS1=%TEMP%\salvage-setup.ps1"
more +5 "%~f0" > "%PS1%"
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%PS1%"
exit /b
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$REPO      = "TheKingNate/high-seas-modpack"
$PACK_URL  = "https://raw.githubusercontent.com/$REPO/release/pack.toml"
$OLD_URL   = "https://raw.githubusercontent.com/$REPO/main/pack.toml"
$BOOTSTRAP = "https://github.com/packwiz/packwiz-installer-bootstrap/releases/latest/download/packwiz-installer-bootstrap.jar"
$INSTANCE  = "Salvage"
$MCV       = "1.20.1"
$FABRIC    = "0.19.3"

$C_BG   = [System.Drawing.Color]::FromArgb(27,30,36)
$C_CARD = [System.Drawing.Color]::FromArgb(36,40,50)
$C_FG   = [System.Drawing.Color]::FromArgb(236,239,244)
$C_DIM  = [System.Drawing.Color]::FromArgb(139,147,161)
$C_ACC  = [System.Drawing.Color]::FromArgb(90,162,255)
$C_GOOD = [System.Drawing.Color]::FromArgb(95,209,140)
$C_BAD  = [System.Drawing.Color]::FromArgb(255,112,112)

$script:Prism = $null
$script:Mode  = $null
$script:Steps = @()
$script:Rows  = @()
$script:Idx   = 0
$script:Halted = $false
$script:Starting = $true
$script:Found = @()

# Repair path. Phase stays "steps" for the install and switch-to-stable flows;
# once it is "repair" the step machine is fenced off and the two button handlers
# below drive everything through OnPrimary / OnSecondary instead.
$script:Phase       = "steps"
$script:OnPrimary   = $null
$script:OnSecondary = $null
$script:Insts       = @()
$script:Diag        = @()
$script:Rung        = 1

$form = New-Object Windows.Forms.Form
$form.Text = "Salvage Setup"
$form.ClientSize = New-Object Drawing.Size(660,700)
$form.StartPosition = "CenterScreen"
$form.BackColor = $C_BG
$form.FormBorderStyle = "FixedSingle"
$form.MaximizeBox = $false

function Add-Lbl($text,$size,$bold,$colour,$x,$y,$w,$h,$align,$parent) {
    $l = New-Object Windows.Forms.Label
    $l.Text = $text
    $st = if ($bold) { [Drawing.FontStyle]::Bold } else { [Drawing.FontStyle]::Regular }
    $l.Font = New-Object Drawing.Font("Segoe UI",$size,$st)
    $l.ForeColor = $colour
    $l.BackColor = if ($parent) { $C_CARD } else { $C_BG }
    $l.TextAlign = $align
    $l.Location = New-Object Drawing.Point($x,$y)
    $l.Size = New-Object Drawing.Size($w,$h)
    if ($parent) { $parent.Controls.Add($l) } else { $form.Controls.Add($l) }
    return $l
}

$null = Add-Lbl "Salvage" 26 $true $C_FG 40 24 580 42 "MiddleCenter" $null
$null = Add-Lbl "Minecraft modpack setup" 10 $false $C_DIM 40 68 580 20 "MiddleCenter" $null

$listPanel = New-Object Windows.Forms.Panel
$listPanel.Location = New-Object Drawing.Point(60,104)
$listPanel.Size = New-Object Drawing.Size(540,90)
$listPanel.BackColor = $C_BG
$form.Controls.Add($listPanel)

$card = New-Object Windows.Forms.Panel
$card.Location = New-Object Drawing.Point(40,206)
$card.Size = New-Object Drawing.Size(580,150)
$card.BackColor = $C_CARD
$form.Controls.Add($card)

$lblHead = Add-Lbl "Starting up" 14 $true $C_FG 20 16 540 26 "TopLeft" $card
$lblBody = Add-Lbl "Give it a second." 10 $false $C_DIM 20 48 540 88 "TopLeft" $card

$bar = New-Object Windows.Forms.ProgressBar
$bar.Style = "Marquee"
$bar.MarqueeAnimationSpeed = 30
$bar.Location = New-Object Drawing.Point(40,368)
$bar.Size = New-Object Drawing.Size(580,6)
$bar.Visible = $false
$form.Controls.Add($bar)

$btn = New-Object Windows.Forms.Button
$btn.Text = "Please wait..."
$btn.Font = New-Object Drawing.Font("Segoe UI",13,[Drawing.FontStyle]::Bold)
$btn.BackColor = $C_ACC
$btn.ForeColor = [Drawing.Color]::White
$btn.FlatStyle = "Flat"
$btn.FlatAppearance.BorderSize = 0
$btn.Size = New-Object Drawing.Size(280,48)
$btn.Location = New-Object Drawing.Point(190,386)
$btn.Enabled = $false
$form.Controls.Add($btn)

$btn2 = New-Object Windows.Forms.Button
$btn2.Font = New-Object Drawing.Font("Segoe UI",12,[Drawing.FontStyle]::Regular)
$btn2.BackColor = $C_CARD
$btn2.ForeColor = $C_FG
$btn2.FlatStyle = "Flat"
$btn2.FlatAppearance.BorderSize = 1
$btn2.FlatAppearance.BorderColor = [Drawing.Color]::FromArgb(85,90,99)
$btn2.Size = New-Object Drawing.Size(280,48)
$btn2.Location = New-Object Drawing.Point(40,386)
$btn2.Visible = $false
$form.Controls.Add($btn2)

$lblStatus = Add-Lbl "" 9 $false $C_DIM 40 442 580 20 "MiddleCenter" $null
$null = Add-Lbl "Details" 8 $true $C_DIM 40 470 200 16 "TopLeft" $null

$log = New-Object Windows.Forms.TextBox
$log.Multiline = $true
$log.ScrollBars = "Vertical"
$log.ReadOnly = $true
$log.BackColor = [Drawing.Color]::FromArgb(20,22,27)
$log.ForeColor = $C_DIM
$log.BorderStyle = "None"
$log.Font = New-Object Drawing.Font("Consolas",9)
$log.Location = New-Object Drawing.Point(40,492)
$log.Size = New-Object Drawing.Size(580,178)
$form.Controls.Add($log)

function Say($m) { $log.AppendText("$m`r`n"); [Windows.Forms.Application]::DoEvents() }
function Status($m) { $lblStatus.Text = $m; [Windows.Forms.Application]::DoEvents() }
function Card($h,$b) { $lblHead.Text = $h; $lblHead.ForeColor = $C_FG; $lblBody.Text = $b; [Windows.Forms.Application]::DoEvents() }

# The main button sits centred when it is alone and slides right when a second
# choice appears, so the pair always reads "the other thing" then "the main thing".
function Buttons($primary,$secondary) {
    $btn.Text = $primary
    $btn.Enabled = $true
    if ($secondary) {
        $btn.Location  = New-Object Drawing.Point(340,386)
        $btn2.Text     = $secondary
        $btn2.Location = New-Object Drawing.Point(40,386)
        $btn2.Enabled  = $true
        $btn2.Visible  = $true
    } else {
        $btn.Location = New-Object Drawing.Point(190,386)
        $btn2.Visible = $false
    }
    [Windows.Forms.Application]::DoEvents()
}

function Hide-Secondary {
    $script:OnSecondary = $null
    $btn2.Visible = $false
    $btn.Location = New-Object Drawing.Point(190,386)
}

function Draw-List {
    $listPanel.Controls.Clear()
    $script:Rows = @()
    $y = 0
    foreach ($s in $script:Steps) {
        $m = Add-Lbl "o" 12 $false $C_DIM 0 $y 22 24 "MiddleCenter" $listPanel
        $t = Add-Lbl $s.Name 11 $false $C_DIM 26 $y 500 24 "MiddleLeft" $listPanel
        $script:Rows += ,@($m,$t)
        $y += 28
    }
}

function Mark($i,$state) {
    if ($i -ge $script:Rows.Count) { return }
    $m = $script:Rows[$i][0]; $t = $script:Rows[$i][1]
    switch ($state) {
        "now"  { $m.Text = ">"; $m.ForeColor = $C_ACC; $t.ForeColor = $C_FG
                 $t.Font = New-Object Drawing.Font("Segoe UI",11,[Drawing.FontStyle]::Bold) }
        "done" { $m.Text = [char]0x2713; $m.ForeColor = $C_GOOD; $t.ForeColor = $C_GOOD
                 $t.Font = New-Object Drawing.Font("Segoe UI",11,[Drawing.FontStyle]::Regular) }
        "fail" { $m.Text = "x"; $m.ForeColor = $C_BAD; $t.ForeColor = $C_BAD }
    }
    [Windows.Forms.Application]::DoEvents()
}

function Fail($what,$todo) {
    $bar.Visible = $false
    $script:OnPrimary = $null
    Hide-Secondary
    Mark $script:Idx "fail"
    $lblHead.Text = "Couldn't finish that step"
    $lblHead.ForeColor = $C_BAD
    $lblBody.Text = "$what`r`n`r`n$todo"
    Say ""; Say "STOPPED: $what"
    if ($todo) { Say $todo }
    Say "Nothing was broken. Close this and try again."
    Status ""
    $btn.Text = "Close"; $btn.BackColor = [Drawing.Color]::FromArgb(85,90,99); $btn.Enabled = $true
    $script:Halted = $true
}

function Heap {
    $t = [int]((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1MB)
    $h = [int]($t / 2)
    if ($h -lt 4096) { $h = 4096 }
    if ($h -gt 12288) { $h = 12288 }
    return @($h,$t)
}

function Find-Prism {
    foreach ($c in @("$env:APPDATA\PrismLauncher","$env:USERPROFILE\Desktop\PrismLauncher","$env:LOCALAPPDATA\Programs\PrismLauncher")) {
        Say "  looked in $c"
        if (Test-Path (Join-Path $c "instances")) { return $c }
    }
    return $null
}

function Find-Insts($url) {
    if (-not $script:Prism) { return @() }
    $r = Join-Path $script:Prism "instances"
    if (-not (Test-Path $r)) { return @() }
    return @(Get-ChildItem $r -Depth 1 -Filter instance.cfg -EA SilentlyContinue |
        Where-Object { (Get-Content $_.FullName -Raw -EA SilentlyContinue) -like "*$url*" })
}

function Get-Boot($mc) {
    $jar = Join-Path $mc "packwiz-installer-bootstrap.jar"
    if ((Test-Path $jar) -and ((Get-Item $jar).Length -gt 10000)) {
        Say "  updater already there"; Status "already present"; return $true
    }
    New-Item -ItemType Directory -Force -Path $mc | Out-Null
    Status "downloading the updater from GitHub..."
    Say "  downloading packwiz-installer-bootstrap.jar"
    try { Invoke-WebRequest $BOOTSTRAP -OutFile $jar }
    catch { Fail "Couldn't download the updater from GitHub." "Check your internet connection and try again. If GitHub is blocked on your network, that's the cause."; return $false }
    if ((Get-Item $jar).Length -lt 10000) {
        Fail "The updater downloaded but looks damaged." "Your network may be interfering with downloads. Try a different connection."; return $false }
    try { Unblock-File $jar } catch { }
    Say "  done"; Status "updater ready"; return $true
}

function Step-Prism {
    if ($script:Prism) { Say "Prism already installed at $script:Prism"; Status "already installed"; return $true }
    Status "downloading Prism Launcher, this takes a minute..."
    Say "Fetching the latest Prism Launcher release"
    try { $rel = Invoke-RestMethod "https://api.github.com/repos/PrismLauncher/PrismLauncher/releases/latest" }
    catch { Fail "Couldn't reach GitHub to download Prism Launcher." "Check your internet connection, or install Prism yourself from prismlauncher.org and run this again."; return $false }
    $a = $rel.assets | Where-Object { $_.name -like "*MinGW-w64-Portable*.zip" } | Select-Object -First 1
    if (-not $a) { $a = $rel.assets | Where-Object { $_.name -like "*MinGW-w64-Portable*.zip" } | Select-Object -First 1
    if (-not $a) { $a = $rel.assets | Where-Object { $_.name -like "*Windows-MSVC-Portable*.zip" } | Select-Object -First 1 } }
    if (-not $a) { Fail "Couldn't find a Windows download in the latest Prism release." "Install Prism yourself from prismlauncher.org, then run this again."; return $false }
    $zip = "$env:TEMP\prism.zip"; $dest = "$env:USERPROFILE\Desktop\PrismLauncher"
    Say "  $($a.name)"
    try {
        Invoke-WebRequest $a.browser_download_url -OutFile $zip
        Say "  unzipping to your Desktop"
        Expand-Archive $zip -DestinationPath $dest -Force
        Remove-Item $zip -Force
    } catch { Fail "The download or unzip failed." "You may be out of disk space, or antivirus blocked it. Install Prism yourself from prismlauncher.org."; return $false }
    $script:Prism = $dest
    Say "Installed to $dest"; Status "installed"
    return $true
}

function Step-Instance {
    $inst = Join-Path $script:Prism "instances\$INSTANCE"
    $mc = Join-Path $inst "minecraft"
    Status "creating folders..."
    Say "Instance folder: $inst"
    try { New-Item -ItemType Directory -Force -Path $mc | Out-Null }
    catch { Fail "Couldn't create a folder at $mc" "Check you have permission to write there, and that your disk isn't full."; return $false }

    Say "Minecraft $MCV with Fabric $FABRIC"
    $json = '{ "components": [ { "important": true, "uid": "net.minecraft", "version": "' + $MCV + '" }, { "uid": "net.fabricmc.fabric-loader", "version": "' + $FABRIC + '" } ], "formatVersion": 1 }'
    $json | Set-Content (Join-Path $inst "mmc-pack.json") -Encoding UTF8

    $h,$t = Heap
    Status "allocating $h MB of memory"
    Say "Memory: $h MB (half of your $t MB)"

    $cfg = Join-Path $inst "instance.cfg"
    $keep = @()
    if (Test-Path $cfg) {
        Say "Existing settings found - keeping anything not ours"
        $keep = Get-Content $cfg | Where-Object { $_ -notmatch '^(InstanceType|name|OverrideCommands|PreLaunchCommand|OverrideMemory|MinMemAlloc|MaxMemAlloc)=' }
    }
    $keep += "InstanceType=OneSix"
    $keep += "name=$INSTANCE"
    $keep += "OverrideCommands=true"
    $keep += "PreLaunchCommand=\`"`$INST_JAVA\`" -jar \`"`$INST_MC_DIR/packwiz-installer-bootstrap.jar\`" -g -s client $PACK_URL"
    $keep += "OverrideMemory=true"
    $keep += "MinMemAlloc=4096"
    $keep += "MaxMemAlloc=$h"
    $keep | Set-Content $cfg -Encoding UTF8
    Say "Instance created."; Status "done"
    return $true
}

function Step-Boot { return (Get-Boot (Join-Path $script:Prism "instances\$INSTANCE\minecraft")) }

function Step-Check {
    Status "scanning your instances..."
    $script:Found = @(Find-Insts $OLD_URL) + @(Find-Insts $PACK_URL)
    foreach ($c in $script:Found) {
        $src = if ((Get-Content $c.FullName -Raw) -like "*$OLD_URL*") { "old" } else { "stable" }
        Say "$($c.Directory.Name): currently on the $src channel"
    }
    Say "$($script:Found.Count) instance(s) to look at."
    Say "Your worlds and settings will not be modified."
    Status "$($script:Found.Count) found"
    return $true
}

function Step-Switch {
    $n = 0
    foreach ($cfg in $script:Found) {
        $text = Get-Content $cfg.FullName -Raw
        if ($text -notlike "*$OLD_URL*") { Say "$($cfg.Directory.Name): already on stable, skipping"; continue }
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        Copy-Item $cfg.FullName "$($cfg.FullName).backup-$stamp"
        Say "$($cfg.Directory.Name): settings backed up"
        $text.Replace($OLD_URL,$PACK_URL) | Set-Content $cfg.FullName -Encoding UTF8 -NoNewline
        Say "$($cfg.Directory.Name): now on the stable channel"
        $n++
    }
    Say "Changed $n instance(s)."; Status "$n switched"
    return $true
}

function Step-BootAll {
    foreach ($cfg in $script:Found) {
        if (-not (Get-Boot (Join-Path $cfg.Directory.FullName "minecraft"))) { return $false }
    }
    return $true
}

# --- repair ----------------------------------------------------------------
#
# Nothing here deletes. Every file a rung acts on is MOVED into
# minecraft\.salvage-quarantine\<stamp>\ keeping its relative path, so a wrong
# call can always be undone by hand. A packwiz.json can be stale, and a player
# can have put a mod in on purpose; without that rule either case eats good files.

# Never touched by any rung, whether the pack tracks the file or not. The pack
# does install a shaderpack and two resourcepacks, so a hash failure in there is
# reported but left in place; dropping packwiz.json at rung 2 makes the updater
# replace it anyway. Losing a player's own shaders is the worse mistake.
$LOCKED_DIRS = @("saves/","screenshots/","shaderpacks/","resourcepacks/",
                 "logs/","crash-reports/",".salvage-quarantine/",
                 "server-resource-packs/","texturepacks/")
$LOCKED_FILES = @("options.txt","optionsof.txt","optionsshaders.txt",
                  "servers.dat","servers.dat_old","usercache.json")

function Locked($rel) {
    $p = $rel.Replace("\","/").ToLower()
    foreach ($d in $LOCKED_DIRS)  { if ($p.StartsWith($d)) { return $true } }
    foreach ($f in $LOCKED_FILES) { if ($p -eq $f) { return $true } }
    # config/*.txt is where mods keep the keybind and preference files a player edits
    if ($p.StartsWith("config/") -and $p.EndsWith(".txt")) { return $true }
    return $false
}

function Move-Quarantine($mc,$rel,$stamp) {
    if (Locked $rel) { return $false }
    $r = $rel.Replace("/","\")
    $src = Join-Path $mc $r
    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { return $false }
    $dst = Join-Path (Join-Path $mc ".salvage-quarantine\$stamp") $r
    try {
        New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
        Move-Item -LiteralPath $src -Destination $dst -Force -EA Stop
    } catch {
        Say "  could not move $rel"
        return $false
    }
    return $true
}

# packwiz records both sha512 and sha1 hashes - the sha1 ones come from
# CurseForge metadata. Assuming one algorithm invents dozens of false
# corruption reports, so the declared type is always honoured, and an
# algorithm we do not know is reported as unchecked, never as corrupt.
function Get-Sum($path,$type) {
    switch ("$type") {
        "sha512" { $a = "SHA512" }
        "sha256" { $a = "SHA256" }
        "sha1"   { $a = "SHA1" }
        "md5"    { $a = "MD5" }
        default  { return $null }
    }
    try { return (Get-FileHash -LiteralPath $path -Algorithm $a).Hash.ToLower() } catch { return $null }
}

function Find-PackInsts {
    if (-not $script:Prism) { return @() }
    $r = Join-Path $script:Prism "instances"
    if (-not (Test-Path $r)) { return @() }
    $out = @()
    foreach ($d in @(Get-ChildItem $r -Directory -EA SilentlyContinue)) {
        $hit = Test-Path -LiteralPath (Join-Path $d.FullName "minecraft\packwiz.json")
        if (-not $hit) {
            $cfg = Join-Path $d.FullName "instance.cfg"
            if (Test-Path -LiteralPath $cfg) {
                $t = Get-Content -LiteralPath $cfg -Raw -EA SilentlyContinue
                if ($t -and (($t -like "*$PACK_URL*") -or ($t -like "*$OLD_URL*"))) { $hit = $true }
            }
        }
        if ($hit) { $out += $d }
    }
    return @($out)
}

function Get-JavaVer($dir) {
    $p = $null
    $cfg = Join-Path $dir.FullName "instance.cfg"
    if (Test-Path -LiteralPath $cfg) {
        $lines = @(Get-Content -LiteralPath $cfg -EA SilentlyContinue)
        $ov = @($lines | Where-Object { $_ -like "OverrideJavaLocation=*" }) | Select-Object -First 1
        $jp = @($lines | Where-Object { $_ -like "JavaPath=*" }) | Select-Object -First 1
        if (($ov -like "*true*") -and $jp) { $p = ($jp -replace '^JavaPath=','') }
    }
    if (-not $p) {
        $g = Join-Path $script:Prism "prismlauncher.cfg"
        if (Test-Path $g) {
            $jp = @(Get-Content $g -EA SilentlyContinue | Where-Object { $_ -like "JavaPath=*" }) | Select-Object -First 1
            if ($jp) { $p = ($jp -replace '^JavaPath=','') }
        }
    }
    if (-not $p) { $p = "java" }
    # javaw has no console, so its -version output would go nowhere
    $p = $p -replace 'javaw\.exe$','java.exe'
    $o = Join-Path $env:TEMP "salvage-java-out.txt"
    $e = Join-Path $env:TEMP "salvage-java-err.txt"
    try { Start-Process -FilePath $p -ArgumentList "-version" -NoNewWindow -Wait -RedirectStandardOutput $o -RedirectStandardError $e -EA Stop }
    catch { return @("unknown",0) }
    $txt = ""
    foreach ($f in @($e,$o)) { if (Test-Path $f) { $txt += ([string](Get-Content $f -Raw -EA SilentlyContinue)) } }
    Remove-Item $o,$e -Force -EA SilentlyContinue
    if ($txt -match 'version "([^"]+)"') {
        $v = $matches[1]
        $maj = 0
        if ($v -match '^1\.(\d+)') { $maj = [int]$matches[1] } elseif ($v -match '^(\d+)') { $maj = [int]$matches[1] }
        return @($v,$maj)
    }
    return @("unknown",0)
}

function Get-LastCrash($mc) {
    $cr = Join-Path $mc "crash-reports"
    if (-not (Test-Path -LiteralPath $cr)) { return [PSCustomObject]@{ File = ""; Lines = @() } }
    $f = @(Get-ChildItem -LiteralPath $cr -Filter *.txt -File -EA SilentlyContinue | Sort-Object LastWriteTime -Descending) | Select-Object -First 1
    if (-not $f) { return [PSCustomObject]@{ File = ""; Lines = @() } }
    $lines = @(Get-Content -LiteralPath $f.FullName -TotalCount 400 -EA SilentlyContinue)
    $out = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^[A-Za-z][\w.$]*(Exception|Error|Throwable)') {
            $out += $lines[$i].Trim()
            $n = 0
            for ($j = $i + 1; ($j -lt $lines.Count) -and ($n -lt 3); $j++) {
                if ($lines[$j] -match '^\s+at\s') { $out += $lines[$j].Trim(); $n++ }
                elseif ($n -gt 0) { break }
            }
            break
        }
    }
    return [PSCustomObject]@{ File = $f.Name; Lines = @($out) }
}

function Diagnose-Inst($dir) {
    $mc = Join-Path $dir.FullName "minecraft"
    $d = [PSCustomObject]@{
        Name = $dir.Name; Path = $dir.FullName; Mc = $mc
        Channel = "unknown"; PackUrl = $null
        PackName = "unknown"; PackVer = ""
        Tracked = 0; Jars = 0
        Orphans = @(); Corrupt = @(); Missing = @(); Unchecked = 0
        Tracking = "not checked"
        Boot = "missing"; Java = "unknown"; JavaMajor = 0; Alloc = 0
        CrashFile = ""; Crash = @()
        HasPack = $false; Changed = @(); Stamp = ""
    }
    Say "$($dir.Name):"

    $cfg = Join-Path $dir.FullName "instance.cfg"
    if (Test-Path -LiteralPath $cfg) {
        $lines = @(Get-Content -LiteralPath $cfg -EA SilentlyContinue)
        $pre = @($lines | Where-Object { $_ -like "PreLaunchCommand=*" }) | Select-Object -First 1
        if ($pre -and ($pre -match 'https?://\S+?pack\.toml')) {
            $d.PackUrl = $matches[0]
            if ($d.PackUrl -like "*/release/*") { $d.Channel = "release" }
            elseif ($d.PackUrl -like "*/main/*") { $d.Channel = "main" }
        }
        $ovm = @($lines | Where-Object { $_ -like "OverrideMemory=*" }) | Select-Object -First 1
        $max = @($lines | Where-Object { $_ -like "MaxMemAlloc=*" }) | Select-Object -First 1
        if (($ovm -like "*true*") -and $max) { try { $d.Alloc = [int]($max -replace '^MaxMemAlloc=','') } catch { } }
    }
    Say "  channel: $($d.Channel)"

    $jar = Join-Path $mc "packwiz-installer-bootstrap.jar"
    if (Test-Path -LiteralPath $jar) {
        if ((Get-Item -LiteralPath $jar).Length -gt 10000) { $d.Boot = "present" } else { $d.Boot = "damaged" }
    }

    $pwf = Join-Path $mc "packwiz.json"
    $pw = $null
    if (Test-Path -LiteralPath $pwf) {
        try { $pw = (Get-Content -LiteralPath $pwf -Raw -EA Stop | ConvertFrom-Json) } catch { $pw = $null }
    }
    if ($pw -and $pw.cachedFiles) { $d.HasPack = $true } else { $pw = $null }
    if (-not $pw) { Say "  no readable packwiz.json - this copy has never finished a sync" }

    $locs = New-Object 'System.Collections.Generic.HashSet[string]'
    if ($pw) {
        $props = @($pw.cachedFiles.PSObject.Properties)
        $d.Tracked = $props.Count
        $i = 0
        foreach ($p in $props) {
            $i++
            if (($i % 15) -eq 0) { Status "$($dir.Name): checking file $i of $($props.Count)" }
            $e = $p.Value
            # a side = "server" mod the client correctly never downloaded
            if ($e.onlyOtherSide -eq $true) { continue }
            $loc = $e.cachedLocation
            if (-not $loc) { continue }
            [void]$locs.Add($loc.Replace("\","/").ToLower())
            $full = Join-Path $mc ($loc.Replace("/","\"))
            if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { $d.Missing += $loc; continue }
            # a jar entry carries both: hash is of the .pw.toml, linkedFileHash of the jar
            $want = if ($e.linkedFileHash) { $e.linkedFileHash } else { $e.hash }
            if (-not $want) { $d.Unchecked++; continue }
            $got = Get-Sum $full $want.type
            if (-not $got) { $d.Unchecked++; continue }
            if ($got -ne "$($want.value)".ToLower()) { $d.Corrupt += $loc }
        }
    }

    $mods = Join-Path $mc "mods"
    if (Test-Path -LiteralPath $mods) {
        $jars = @(Get-ChildItem -LiteralPath $mods -Filter *.jar -File -Recurse -EA SilentlyContinue)
        $d.Jars = $jars.Count
        # Orphans are only meaningful against a tracking file. packwiz-installer
        # removes only what it recorded, so anything else in mods/ stays forever -
        # this is the real reason "a clean reinstall fixed it".
        if ($pw) {
            foreach ($j in $jars) {
                $rel = $j.FullName.Substring($mc.Length).TrimStart("\").Replace("\","/")
                if (-not $locs.Contains($rel.ToLower())) { $d.Orphans += $rel }
            }
        }
    }

    # Load-bearing: without this an unsynced copy reports zero problems, because
    # its packwiz.json still faithfully lists everything it once had.
    if ($pw) {
        Status "$($dir.Name): comparing against the published pack"
        $url = $d.PackUrl
        $tmp = Join-Path $env:TEMP "salvage-packcheck.toml"
        $got = $false
        if ($url) { try { Invoke-WebRequest $url -OutFile $tmp -UseBasicParsing -EA Stop; $got = $true } catch { } }
        if ($got) {
            $live = (Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash.ToLower()
            $txt = [string](Get-Content -LiteralPath $tmp -Raw)
            if ($txt -match '(?m)^\s*name\s*=\s*"([^"]*)"')    { $d.PackName = $matches[1] }
            if ($txt -match '(?m)^\s*version\s*=\s*"([^"]*)"') { $d.PackVer  = $matches[1] }
            # pack.toml declares the sha256 of the live index.toml, so there is no
            # need to fetch index.toml as well
            $idx = $null
            if ($txt -match '(?m)^\s*hash\s*=\s*"([0-9a-fA-F]+)"') { $idx = $matches[1].ToLower() }
            $hp = "$($pw.packFileHash.value)".ToLower()
            $hi = "$($pw.indexFileHash.value)".ToLower()
            if ($live -ne $hp) { $d.Tracking = "out of date" }
            elseif ($idx -and $hi -and ($idx -ne $hi)) { $d.Tracking = "out of date" }
            else { $d.Tracking = "up to date" }
            Remove-Item $tmp -Force -EA SilentlyContinue
        } elseif ($url) {
            $d.Tracking = "could not check, no network"
        } else {
            $d.Tracking = "could not check, no pack URL in the instance settings"
        }
    } else {
        $d.Tracking = "no tracking file"
    }

    Status "$($dir.Name): checking Java"
    $jv = Get-JavaVer $dir
    $d.Java = $jv[0]; $d.JavaMajor = $jv[1]
    $c = Get-LastCrash $mc
    $d.CrashFile = $c.File; $d.Crash = $c.Lines

    Say "  tracked $($d.Tracked), jars $($d.Jars), orphans $($d.Orphans.Count), corrupt $($d.Corrupt.Count), missing $($d.Missing.Count)"
    Say "  tracking: $($d.Tracking)   java: $($d.Java)"
    return $d
}

function Problem-Count($d) {
    $n = $d.Orphans.Count + $d.Corrupt.Count + $d.Missing.Count
    if ($d.Channel -eq "main") { $n++ }
    if ($d.Boot -ne "present") { $n++ }
    if ($d.Tracking -eq "out of date") { $n++ }
    if (($d.JavaMajor -gt 0) -and ($d.JavaMajor -lt 17)) { $n++ }
    if (-not $d.HasPack) { $n++ }
    return $n
}

function Write-Report($diags,$action,$noneText) {
    $desk = [Environment]::GetFolderPath("DesktopDirectory")
    if (-not $desk) { $desk = [Environment]::GetFolderPath("Desktop") }
    if ((-not $desk) -or (-not (Test-Path -LiteralPath $desk))) { $desk = Join-Path $env:USERPROFILE "Desktop" }
    if (-not (Test-Path -LiteralPath $desk)) { $desk = $env:TEMP }
    $path = Join-Path $desk ("salvage-report-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".txt")
    $o = New-Object System.Collections.Generic.List[string]
    $os = Get-CimInstance Win32_OperatingSystem -EA SilentlyContinue
    $hh,$ram = Heap
    $o.Add("Salvage repair report")
    $o.Add("Generated  " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
    $o.Add("Ran        $action")
    $o.Add("Computer   $($os.Caption) $($os.Version)")
    $o.Add("Memory     $ram MB physical")
    $o.Add("")
    foreach ($d in $diags) {
        $o.Add("--------------------------------------------------------------")
        $o.Add("Instance   $($d.Name)")
        $o.Add("Pack       $($d.PackName) $($d.PackVer)")
        $o.Add("Path       $($d.Path)")
        $o.Add("Channel    $($d.Channel)")
        if ($d.PackUrl) { $o.Add("Pack URL   $($d.PackUrl)") }
        $jn = ""
        if ($d.JavaMajor -eq 0) { $jn = "   (could not determine)" }
        elseif ($d.JavaMajor -lt 17) { $jn = "   TOO OLD - the pack needs 17 or newer" }
        $o.Add("Java       $($d.Java)$jn")
        if ($d.Alloc -gt 0) { $o.Add("Memory     $($d.Alloc) MB allocated of $ram MB physical") }
        else { $o.Add("Memory     using the Prism default of $ram MB physical") }
        $o.Add("Updater    packwiz-installer-bootstrap.jar $($d.Boot)")
        $o.Add("Tracking   $($d.Tracking)")
        $o.Add("")
        $o.Add("  tracked files   $($d.Tracked)")
        $o.Add("  jars on disk    $($d.Jars)")
        $o.Add("  orphans         $($d.Orphans.Count)")
        $o.Add("  corrupt         $($d.Corrupt.Count)")
        $o.Add("  missing         $($d.Missing.Count)")
        if ($d.Unchecked -gt 0) { $o.Add("  not checkable   $($d.Unchecked)") }
        $o.Add("")
        $o.Add("Problems found by the check")
        $n = 0
        if (-not $d.HasPack) { $o.Add("  tracking  no readable packwiz.json - this copy has never finished a sync"); $n++ }
        if ($d.Tracking -eq "out of date") { $o.Add("  tracking  this copy is behind the published pack"); $n++ }
        if ($d.Channel -eq "main") { $o.Add("  channel   on the main channel, should be release"); $n++ }
        if ($d.Boot -ne "present") { $o.Add("  updater   packwiz-installer-bootstrap.jar is $($d.Boot)"); $n++ }
        if (($d.JavaMajor -gt 0) -and ($d.JavaMajor -lt 17)) { $o.Add("  java      $($d.Java) is too old"); $n++ }
        foreach ($x in $d.Orphans) { $o.Add("  orphan    $x"); $n++ }
        foreach ($x in $d.Corrupt) {
            if (Locked $x) { $o.Add("  corrupt   $x  (left in place, no rung touches that folder)") }
            else { $o.Add("  corrupt   $x") }
            $n++
        }
        foreach ($x in $d.Missing) { $o.Add("  missing   $x"); $n++ }
        if ($n -eq 0) { $o.Add("  none") }
        $o.Add("")
        $o.Add("Changed by this run")
        if ($d.Changed.Count -eq 0) { $o.Add("  $noneText") }
        else {
            $o.Add("  moved to minecraft\.salvage-quarantine\$($d.Stamp)\  (nothing was deleted)")
            foreach ($x in $d.Changed) { $o.Add("    $x") }
        }
        $o.Add("")
        if ($d.CrashFile) {
            $o.Add("Last crash  $($d.CrashFile)")
            if ($d.Crash.Count -eq 0) { $o.Add("  no exception line found in that file") }
            foreach ($x in $d.Crash) { $o.Add("  $x") }
        } else {
            $o.Add("Last crash  none recorded")
        }
        $o.Add("")
    }
    $o.Add("Send this file to your server operator.")
    try { ($o -join "`r`n") | Set-Content -LiteralPath $path -Encoding UTF8 -EA Stop } catch { return $null }
    return $path
}

# Indexed by rung number, so slot 0 is a placeholder.
$RUNG_NAME = @("",
 "targeted repair",
 "resync",
 "full reset")
$RUNG_DESC = @("",
 "Moves the jars that do not belong and any file that failed its check into quarantine. The updater fetches the real ones next launch.",
 "The targeted repair, and also throws away the record of what is installed, so the updater re-checks every single file next launch.",
 "Moves the whole mods and config folders into quarantine and lets the updater rebuild them. Your world, settings and shaders stay.")

function Repair-Begin {
    $script:Phase = "repair"
    $script:OnPrimary = $null
    Hide-Secondary
    $btn.Enabled = $false
    $script:Steps = @(@{Name="Check for problems"},@{Name="Repair, if needed"})
    Draw-List
    Mark 0 "now"
    Card "Checking your install" "Reading every file the pack tracks and hashing it against what the pack says it should be.`r`n`r`nThis changes nothing. Give it a minute."
    $bar.Visible = $true
    Say ""
    Say "Checking $($script:Insts.Count) instance(s) - nothing will be changed."
    $list = New-Object System.Collections.Generic.List[object]
    foreach ($i in $script:Insts) {
        try { $list.Add((Diagnose-Inst $i)) }
        catch { Say "  could not check $($i.Name): $($_.Exception.Message)" }
    }
    $script:Diag = $list.ToArray()
    $bar.Visible = $false
    Status ""
    if ($script:Diag.Count -eq 0) {
        Mark 0 "fail"
        $lblHead.Text = "Nothing could be checked"; $lblHead.ForeColor = $C_BAD
        $lblBody.Text = "None of your instances could be read. Nothing was changed."
        $script:OnPrimary = { $form.Close() }
        Buttons "Close" $null
        return
    }
    Mark 0 "done"
    $script:Rung = 1
    Repair-Results "a check only, nothing was changed" "nothing (diagnose only)"
}

function Repair-Results($action,$noneText) {
    $total = 0
    foreach ($d in $script:Diag) { $total += (Problem-Count $d) }
    $path = Write-Report $script:Diag $action $noneText
    if ($path) { Say "Report written to $path" } else { Say "Could not write the report to your Desktop." }

    $sum = ""
    foreach ($d in $script:Diag) {
        $sum += "$($d.Name): $(Problem-Count $d) problem(s) - $($d.Orphans.Count) orphan, $($d.Corrupt.Count) corrupt, $($d.Missing.Count) missing.`r`n"
    }
    if ($total -gt 0) {
        $lblHead.Text = "Found $total problem(s)"; $lblHead.ForeColor = $C_BAD
    } else {
        $lblHead.Text = "No problems found"; $lblHead.ForeColor = $C_GOOD
    }
    if ($path) { $sum += "`r`nSaved to your Desktop as " + (Split-Path $path -Leaf) }
    else { $sum += "`r`nThe report could not be saved to your Desktop." }
    $lblBody.Text = $sum
    Status ""

    if ($script:Rung -gt 3) {
        $script:OnPrimary = { $form.Close() }
        $btn.BackColor = $C_GOOD
        Buttons "Close" $null
    } elseif ($total -gt 0) {
        $script:OnPrimary = { Repair-Run $script:Rung }
        $script:OnSecondary = { $form.Close() }
        $btn.BackColor = $C_ACC
        Buttons ("Run the " + $RUNG_NAME[$script:Rung]) "Close"
    } else {
        $script:OnPrimary = { $form.Close() }
        $script:OnSecondary = { Repair-Run $script:Rung }
        $btn.BackColor = $C_GOOD
        Buttons "Close" ("Run the " + $RUNG_NAME[$script:Rung])
    }
}

function Repair-Run($rung) {
    $script:OnPrimary = $null
    Hide-Secondary
    $btn.Enabled = $false
    $btn.BackColor = $C_ACC
    Mark 1 "now"
    Card ("Running the " + $RUNG_NAME[$rung]) ($RUNG_DESC[$rung] + "`r`n`r`nNothing is deleted. Everything moved keeps its original path inside a quarantine folder, so any of it can be put back by hand.")
    $bar.Visible = $true
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Say ""
    Say "Repair level $rung - quarantine folder .salvage-quarantine\$stamp"

    foreach ($d in $script:Diag) {
        $d.Stamp = $stamp
        $d.Changed = @()
        Say "$($d.Name):"
        $moved = 0
        if ($rung -le 2) {
            if (-not $d.HasPack) { Say "  no tracking file, so there is nothing targeted to move" }
            foreach ($rel in (@($d.Orphans) + @($d.Corrupt))) {
                if (Locked $rel) { Say "  left alone, this tool never touches $rel"; continue }
                if (Move-Quarantine $d.Mc $rel $stamp) { $d.Changed += $rel; $moved++ }
            }
        } else {
            foreach ($sub in @("mods","config")) {
                $p = Join-Path $d.Mc $sub
                if (-not (Test-Path -LiteralPath $p)) { continue }
                foreach ($f in @(Get-ChildItem -LiteralPath $p -File -Recurse -EA SilentlyContinue)) {
                    $rel = $f.FullName.Substring($d.Mc.Length).TrimStart("\").Replace("\","/")
                    if (Move-Quarantine $d.Mc $rel $stamp) { $d.Changed += $rel; $moved++ }
                    if (($moved % 20) -eq 0) { Status "$($d.Name): moved $moved files"; [Windows.Forms.Application]::DoEvents() }
                }
            }
        }
        # rung 2 and up drop the tracking file so the updater re-validates everything
        if ($rung -ge 2) {
            if (Move-Quarantine $d.Mc "packwiz.json" $stamp) { $d.Changed += "packwiz.json"; $moved++ }
        }
        Say "  moved $moved file(s) into quarantine"
    }

    $bar.Visible = $false
    Status ""
    Mark 1 "done"
    $name = $RUNG_NAME[$rung]
    $path = Write-Report $script:Diag "repair level $rung - $name" "nothing needed moving"
    if ($path) { Say "Report written to $path" } else { Say "Could not write the report to your Desktop." }
    $script:Rung = $rung + 1

    $lblHead.Text = "Repair done"; $lblHead.ForeColor = $C_GOOD
    $body = "Launch the game now. If it still crashes, run this again and pick the next option."
    if ($rung -ge 2) { $body += "`r`n`r`nThe next launch re-checks every file, so give it a few minutes. It may ask you about optional mods again." }
    if ($path) { $body += "`r`n`r`nReport on your Desktop: " + (Split-Path $path -Leaf) }
    $lblBody.Text = $body
    $btn.BackColor = $C_GOOD
    $script:OnPrimary = { $form.Close() }
    if ($script:Rung -le 3) {
        $script:OnSecondary = { Repair-Run $script:Rung }
        Buttons "Close" ("Run the " + $RUNG_NAME[$script:Rung])
    } else {
        Buttons "Close" $null
    }
}

$BLURB = @{
 "Get Prism Launcher" = "Prism Launcher is the app that runs modded Minecraft.`r`n`r`nIf you already have it, this does nothing. If not, it downloads and installs it for you."
 "Create the Salvage instance" = "Adds an entry in Prism called Salvage, set to Minecraft 1.20.1 with the Fabric mod loader.`r`n`r`nIt picks how much memory to give Minecraft based on how much your computer has."
 "Set up automatic updates" = "Adds a small file that checks the mod list every time you play.`r`n`r`nThat means you never have to reinstall or re-download anything when the pack changes."
 "Look at your current setup" = "Finds your existing Salvage instances and reports which update channel they're on.`r`n`r`nNothing is changed in this step."
 "Switch to stable updates" = "Points your copy at the stable release channel, so you only get changes once they've been tested.`r`n`r`nOne line in your settings file changes, and a backup is saved first. Your world is untouched."
 "Verify the updater" = "Checks the auto-update file is present and undamaged, and re-downloads it if needed."
}

function Present {
    Hide-Secondary
    if ($script:Idx -ge $script:Steps.Count) { Finish; return }
    $n = $script:Steps[$script:Idx].Name
    Mark $script:Idx "now"
    Card $n $BLURB[$n]
    $btn.Text = "Do this step"; $btn.Enabled = $true
    Status "step $($script:Idx + 1) of $($script:Steps.Count)"
}

function Finish {
    $lblHead.Text = "All done"; $lblHead.ForeColor = $C_GOOD
    if ($script:Mode -eq "install") {
        $lblBody.Text = "1.  Open Prism Launcher`r`n2.  Sign in with your Microsoft account, top right`r`n3.  Click Salvage, press Launch`r`n`r`nThe first launch downloads about 150 mods, so give it several minutes."
        Say ""; Say "Then try joining the server once. It will say you aren't"
        Say "whitelisted - that's expected, and it's how you get added."
    } else {
        $lblBody.Text = "Nothing else to do. Just launch as normal.`r`n`r`nYour world, settings, keybinds and shaders were left exactly as they were. A backup of each settings file is saved next to the original."
    }
    Status ""
    $btn.Text = "Close"; $btn.BackColor = $C_GOOD; $btn.Enabled = $true
    $script:Halted = $true
}

$btn.Add_Click({
    # Cleared before running so a second click during a long step cannot re-enter.
    if ($script:OnPrimary) { $a = $script:OnPrimary; $script:OnPrimary = $null; & $a; return }
    if ($script:Phase -eq "repair") { return }
    if ($script:Halted) { $form.Close(); return }
    if ($script:Starting) { $script:Starting = $false; Present; return }
    $btn.Enabled = $false; $btn.Text = "Working..."
    $bar.Visible = $true
    [Windows.Forms.Application]::DoEvents()
    $ok = & $script:Steps[$script:Idx].Action
    $bar.Visible = $false
    if ($script:Halted) { return }
    if ($ok -eq $false) { return }
    Mark $script:Idx "done"
    $script:Idx++
    Say ""
    Present
})

$btn2.Add_Click({
    if (-not $script:OnSecondary) { return }
    $a = $script:OnSecondary; $script:OnSecondary = $null; & $a
})

$form.Add_Shown({
    $form.Activate()
    Say "Checking your computer..."
    $h,$t = Heap
    Say "Memory: $t MB"
    $script:Prism = Find-Prism
    if ($script:Prism) { Say "Prism Launcher: found at $script:Prism" } else { Say "Prism Launcher: not installed" }

    # Broader than Find-Insts: a copy whose instance.cfg lost our URL still owns a
    # packwiz.json, and that is the copy most likely to need looking at.
    $script:Insts = @(Find-PackInsts)

    $existing = @(Find-Insts $OLD_URL) + @(Find-Insts $PACK_URL)
    if ($existing.Count -gt 0) {
        $script:Mode = "update"
        Say "Existing Salvage instances: $($existing.Count)"
        foreach ($c in $existing) { Say "  $($c.Directory.Name)" }
        $script:Steps = @(
            @{Name="Look at your current setup"; Action={ Step-Check }},
            @{Name="Switch to stable updates";   Action={ Step-Switch }},
            @{Name="Verify the updater";         Action={ Step-BootAll }})
        $head = "You already have Salvage"
        $body = "Switch to stable updates points your copy at the tested release channel.`r`n`r`nCheck for problems reads every file the pack installed and writes a report to your Desktop.`r`n`r`nYour world and settings are safe either way."
        $start = "Switch to stable"
    } else {
        $script:Mode = "install"
        Say "No existing Salvage instance - fresh install"
        $script:Steps = @(
            @{Name="Get Prism Launcher";          Action={ Step-Prism }},
            @{Name="Create the Salvage instance"; Action={ Step-Instance }},
            @{Name="Set up automatic updates";    Action={ Step-Boot }})
        $head = "Ready to install"
        $body = "Three steps. Each one explains itself before it runs, and nothing happens until you click.`r`n`r`nYour computer has $t MB of memory, so Minecraft will get $h MB."
        $start = "Start"
    }
    Say ""
    Draw-List
    Card $head $body
    Status ""
    if ($script:Insts.Count -gt 0) {
        Say "$($script:Insts.Count) copy(s) can be checked for problems."
        $script:OnSecondary = { Repair-Begin }
        Buttons $start "Check for problems"
    } else {
        Buttons $start $null
    }
})

[void]$form.ShowDialog()
