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
    $a = $rel.assets | Where-Object { $_.name -like "*Windows-MSVC-Portable*.zip" } | Select-Object -First 1
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

$BLURB = @{
 "Get Prism Launcher" = "Prism Launcher is the app that runs modded Minecraft.`r`n`r`nIf you already have it, this does nothing. If not, it downloads and installs it for you."
 "Create the Salvage instance" = "Adds an entry in Prism called Salvage, set to Minecraft 1.20.1 with the Fabric mod loader.`r`n`r`nIt picks how much memory to give Minecraft based on how much your computer has."
 "Set up automatic updates" = "Adds a small file that checks the mod list every time you play.`r`n`r`nThat means you never have to reinstall or re-download anything when the pack changes."
 "Look at your current setup" = "Finds your existing Salvage instances and reports which update channel they're on.`r`n`r`nNothing is changed in this step."
 "Switch to stable updates" = "Points your copy at the stable release channel, so you only get changes once they've been tested.`r`n`r`nOne line in your settings file changes, and a backup is saved first. Your world is untouched."
 "Verify the updater" = "Checks the auto-update file is present and undamaged, and re-downloads it if needed."
}

function Present {
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

$form.Add_Shown({
    $form.Activate()
    Say "Checking your computer..."
    $h,$t = Heap
    Say "Memory: $t MB"
    $script:Prism = Find-Prism
    if ($script:Prism) { Say "Prism Launcher: found at $script:Prism" } else { Say "Prism Launcher: not installed" }

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
        $body = "This points your copy at the stable release channel, so you only get changes once they've been tested.`r`n`r`nYour world, settings, keybinds, shaders and video options will NOT be touched."
    } else {
        $script:Mode = "install"
        Say "No existing Salvage instance - fresh install"
        $script:Steps = @(
            @{Name="Get Prism Launcher";          Action={ Step-Prism }},
            @{Name="Create the Salvage instance"; Action={ Step-Instance }},
            @{Name="Set up automatic updates";    Action={ Step-Boot }})
        $head = "Ready to install"
        $body = "Three steps. Each one explains itself before it runs, and nothing happens until you click.`r`n`r`nYour computer has $t MB of memory, so Minecraft will get $h MB."
    }
    Say ""
    Draw-List
    Card $head $body
    Status ""
    $btn.Text = "Start"; $btn.Enabled = $true
})

[void]$form.ShowDialog()
