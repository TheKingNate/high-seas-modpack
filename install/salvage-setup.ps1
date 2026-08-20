# Salvage Setup -- a small window that walks you through installing
# or updating the Salvage modpack.
#
#   Right-click this file -> Run with PowerShell
#
# It works out whether you need a fresh install or just an update,
# tells you what each step will do before it does it, and waits for
# you to click.

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$REPO      = "TheKingNate/high-seas-modpack"
$PACK_URL  = "https://raw.githubusercontent.com/$REPO/release/pack.toml"
$OLD_URL   = "https://raw.githubusercontent.com/$REPO/main/pack.toml"
$BOOTSTRAP = "https://github.com/packwiz/packwiz-installer-bootstrap/releases/latest/download/packwiz-installer-bootstrap.jar"

$INSTANCE   = "Salvage"
$MC_VERSION = "1.20.1"
$FABRIC     = "0.19.3"

$SELF = $MyInvocation.MyCommand.Path

$BG     = [System.Drawing.Color]::FromArgb(30,33,40)
$FG     = [System.Drawing.Color]::FromArgb(230,230,230)
$DIM    = [System.Drawing.Color]::FromArgb(154,160,168)
$ACCENT = [System.Drawing.Color]::FromArgb(74,158,255)
$GOOD   = [System.Drawing.Color]::FromArgb(95,209,140)
$BAD    = [System.Drawing.Color]::FromArgb(255,107,107)

# ---------------------------------------------------------------- state
$script:Prism = $null
$script:Mode  = $null
$script:Steps = @()
$script:Idx   = 0
$script:Found = @()

# ----------------------------------------------------------------- form
$form = New-Object System.Windows.Forms.Form
$form.Text = "Salvage Setup"
$form.Size = New-Object System.Drawing.Size(640,580)
$form.StartPosition = "CenterScreen"
$form.BackColor = $BG
$form.FormBorderStyle = "FixedSingle"
$form.MaximizeBox = $false

function NewLabel($text,$size,$style,$colour,$top,$height) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $text
    $l.Font = New-Object System.Drawing.Font("Segoe UI",$size,$style)
    $l.ForeColor = $colour
    $l.BackColor = $BG
    $l.TextAlign = "MiddleCenter"
    $l.Location = New-Object System.Drawing.Point(30,$top)
    $l.Size = New-Object System.Drawing.Size(570,$height)
    $form.Controls.Add($l)
    return $l
}

$null      = NewLabel "Salvage" 24 ([System.Drawing.FontStyle]::Bold) $FG 20 44
$null      = NewLabel "Minecraft modpack setup" 10 ([System.Drawing.FontStyle]::Regular) $DIM 64 22
$lblStep   = NewLabel "" 9 ([System.Drawing.FontStyle]::Bold) $ACCENT 100 20
$lblTitle  = NewLabel "" 14 ([System.Drawing.FontStyle]::Bold) $FG 124 30
$lblDesc   = NewLabel "" 10 ([System.Drawing.FontStyle]::Regular) $DIM 158 76

$btn = New-Object System.Windows.Forms.Button
$btn.Text = ""
$btn.Font = New-Object System.Drawing.Font("Segoe UI",12,[System.Drawing.FontStyle]::Bold)
$btn.BackColor = $ACCENT
$btn.ForeColor = [System.Drawing.Color]::White
$btn.FlatStyle = "Flat"
$btn.FlatAppearance.BorderSize = 0
$btn.Size = New-Object System.Drawing.Size(260,44)
$btn.Location = New-Object System.Drawing.Point(185,244)
$form.Controls.Add($btn)

$log = New-Object System.Windows.Forms.TextBox
$log.Multiline = $true
$log.ScrollBars = "Vertical"
$log.ReadOnly = $true
$log.BackColor = [System.Drawing.Color]::FromArgb(21,23,28)
$log.ForeColor = $DIM
$log.BorderStyle = "None"
$log.Font = New-Object System.Drawing.Font("Consolas",9)
$log.Location = New-Object System.Drawing.Point(30,306)
$log.Size = New-Object System.Drawing.Size(570,210)
$form.Controls.Add($log)

function Say($m) {
    $log.AppendText("$m`r`n")
    [System.Windows.Forms.Application]::DoEvents()
}

function Show-Step($stepText,$title,$desc,$button) {
    $lblStep.Text  = $stepText
    $lblTitle.Text = $title
    $lblTitle.ForeColor = $FG
    $lblDesc.Text  = $desc
    $btn.Text      = $button
    $btn.Enabled   = $true
    [System.Windows.Forms.Application]::DoEvents()
}

function Stop-Setup($what,$todo) {
    $lblStep.Text = ""
    $lblTitle.Text = "Something went wrong"
    $lblTitle.ForeColor = $BAD
    $lblDesc.Text = $what
    Say ""
    Say "STOPPED: $what"
    if ($todo) { Say $todo }
    Say "Nothing was broken. You can close this and try again."
    $btn.Text = "Close"
    $btn.BackColor = [System.Drawing.Color]::FromArgb(85,90,99)
    $btn.Enabled = $true
    $script:Halted = $true
}

# ------------------------------------------------------------- helpers
function Find-Prism {
    foreach ($c in @(
        "$env:APPDATA\PrismLauncher",
        "$env:USERPROFILE\Desktop\PrismLauncher",
        "$env:LOCALAPPDATA\Programs\PrismLauncher"
    )) { if (Test-Path (Join-Path $c "instances")) { return $c } }
    return $null
}

function Find-PackInstances($data,$url) {
    if (-not $data) { return @() }
    $root = Join-Path $data "instances"
    if (-not (Test-Path $root)) { return @() }
    return @(Get-ChildItem $root -Depth 1 -Filter instance.cfg -ErrorAction SilentlyContinue |
        Where-Object { (Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue) -like "*$url*" })
}

function Heap-MB {
    $total = [int]((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1MB)
    $h = [int]($total / 2)
    if ($h -lt 4096)  { $h = 4096 }
    if ($h -gt 12288) { $h = 12288 }
    return @($h,$total)
}

function Get-Bootstrap($mcDir) {
    $jar = Join-Path $mcDir "packwiz-installer-bootstrap.jar"
    if ((Test-Path $jar) -and ((Get-Item $jar).Length -gt 10000)) {
        Say "  updater already present"
        return
    }
    New-Item -ItemType Directory -Force -Path $mcDir | Out-Null
    Say "  downloading the updater..."
    try { Invoke-WebRequest $BOOTSTRAP -OutFile $jar }
    catch {
        Stop-Setup "Couldn't download the updater from GitHub." `
            "Check your internet connection and try again. If GitHub is blocked on your network, that's why."
        return
    }
    if ((Get-Item $jar).Length -lt 10000) {
        Stop-Setup "The updater downloaded but looks damaged." `
            "Your network may be interfering with downloads. Try a different connection."
        return
    }
    try { Unblock-File $jar } catch { }
    Say "  updater ready"
}

# --------------------------------------------------------------- steps
function Step-Prism {
    if ($script:Prism) { Say "Prism already installed at $script:Prism"; return }
    Say "Downloading Prism Launcher (portable) to your Desktop..."
    try {
        $rel = Invoke-RestMethod "https://api.github.com/repos/PrismLauncher/PrismLauncher/releases/latest"
    } catch {
        Stop-Setup "Couldn't reach GitHub to download Prism Launcher." `
            "Check your internet connection, or install Prism yourself from https://prismlauncher.org/download and run this again."
        return
    }
    $asset = $rel.assets | Where-Object { $_.name -like "*Windows-MSVC-Portable*.zip" } | Select-Object -First 1
    if (-not $asset) {
        Stop-Setup "Couldn't find a Windows download in the latest Prism release." `
            "Install Prism yourself from https://prismlauncher.org/download, then run this again."
        return
    }
    $zip  = "$env:TEMP\prism.zip"
    $dest = "$env:USERPROFILE\Desktop\PrismLauncher"
    try {
        Invoke-WebRequest $asset.browser_download_url -OutFile $zip
        Expand-Archive $zip -DestinationPath $dest -Force
        Remove-Item $zip -Force
    } catch {
        Stop-Setup "The download or unzip failed." `
            "You may be out of disk space, or antivirus blocked it. Install Prism yourself from https://prismlauncher.org/download."
        return
    }
    $script:Prism = $dest
    Say "  installed to $dest"
}

function Step-Instance {
    $inst = Join-Path $script:Prism "instances\$INSTANCE"
    $mc   = Join-Path $inst "minecraft"
    Say "Creating instance at $inst"
    try { New-Item -ItemType Directory -Force -Path $mc | Out-Null }
    catch {
        Stop-Setup "Couldn't create a folder at $mc" `
            "Check you have permission to write there and that your disk isn't full."
        return
    }

@"
{
    "components": [
        { "important": true, "uid": "net.minecraft", "version": "$MC_VERSION" },
        { "uid": "net.fabricmc.fabric-loader", "version": "$FABRIC" }
    ],
    "formatVersion": 1
}
"@ | Set-Content (Join-Path $inst "mmc-pack.json") -Encoding UTF8

    $h,$total = Heap-MB
    Say "  allocating $h MB (your computer has $total MB)"

    $cfg = Join-Path $inst "instance.cfg"
    $keep = @()
    if (Test-Path $cfg) {
        $keep = Get-Content $cfg | Where-Object {
            $_ -notmatch '^(InstanceType|name|OverrideCommands|PreLaunchCommand|OverrideMemory|MinMemAlloc|MaxMemAlloc)='
        }
    }
    $keep += "InstanceType=OneSix"
    $keep += "name=$INSTANCE"
    $keep += "OverrideCommands=true"
    $keep += "PreLaunchCommand=`"`$INST_JAVA`" -jar `"`$INST_MC_DIR/packwiz-installer-bootstrap.jar`" -g -s client $PACK_URL"
    $keep += "OverrideMemory=true"
    $keep += "MinMemAlloc=4096"
    $keep += "MaxMemAlloc=$h"
    $keep | Set-Content $cfg -Encoding UTF8
    Say "  instance ready"
}

function Step-Bootstrap {
    Get-Bootstrap (Join-Path $script:Prism "instances\$INSTANCE\minecraft")
}

function Step-CheckUpdate {
    $script:Found = @(Find-PackInstances $script:Prism $OLD_URL) +
                    @(Find-PackInstances $script:Prism $PACK_URL)
    foreach ($c in $script:Found) { Say "  $($c.Directory.Name)" }
    Say "Found $($script:Found.Count) instance(s). Your world and settings stay exactly as they are."
}

function Step-Switch {
    $changed = 0
    foreach ($cfg in $script:Found) {
        $text = Get-Content $cfg.FullName -Raw
        if ($text -notlike "*$OLD_URL*") {
            Say "  $($cfg.Directory.Name): already correct"
            continue
        }
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        Copy-Item $cfg.FullName "$($cfg.FullName).backup-$stamp"
        $text.Replace($OLD_URL,$PACK_URL) | Set-Content $cfg.FullName -Encoding UTF8 -NoNewline
        Say "  $($cfg.Directory.Name): switched (backup saved)"
        $changed++
    }
    Say "Changed $changed instance(s)."
}

function Step-BootstrapAll {
    foreach ($cfg in $script:Found) {
        Get-Bootstrap (Join-Path $cfg.Directory.FullName "minecraft")
    }
}

# ----------------------------------------------------------- blurbs
$BLURB = @{
    "Get Prism Launcher" = "Prism Launcher is the program that runs modded Minecraft. If you already have it, this does nothing. If not, it downloads it for you."
    "Create the Salvage instance" = "This makes a new entry in Prism called Salvage, set to Minecraft 1.20.1 with Fabric, and picks a sensible amount of memory based on your computer."
    "Set up automatic updates" = "This adds a small file that fetches the mod list every time you play, so you never have to reinstall anything when the pack changes."
    "Check what you have" = "Looks at your existing Salvage setup. Your world, settings and keybinds will not be touched -- only where updates come from."
    "Point it at the right updates" = "Switches your copy to the stable release channel, so you only get changes once they've been tested. A backup of your settings file is kept."
    "Make sure the updater is there" = "Checks the auto-update file exists and isn't damaged, and re-downloads it if needed."
}

function Present {
    if ($script:Idx -ge $script:Steps.Count) { Finish; return }
    $name = $script:Steps[$script:Idx].Name
    Show-Step "Step $($script:Idx + 1) of $($script:Steps.Count)" $name $BLURB[$name] "Do this step"
}

function Finish {
    $lblStep.Text = ""
    $lblTitle.Text = "All done"
    $lblTitle.ForeColor = $GOOD
    if ($script:Mode -eq "install") {
        $lblDesc.Text = "Open Prism Launcher, sign in with your Microsoft account, then click Salvage and press Launch.`r`n`r`nThe first launch downloads about 150 mods, so give it several minutes."
        Say ""
        Say "Then try joining the server once. It will say you aren't"
        Say "whitelisted -- that's expected, and it's how you get added."
        Say "Just tell Josh you tried."
    } else {
        $lblDesc.Text = "Nothing else to do. Just launch as normal.`r`n`r`nYour world, settings, keybinds and shaders were not touched."
    }
    Say ""
    Say "Finished."

    if ($SELF -and (Test-Path $SELF)) {
        try {
            Start-Process powershell -WindowStyle Hidden -ArgumentList @(
                "-NoProfile","-Command",
                "Start-Sleep 3; Add-Type -AssemblyName Microsoft.VisualBasic; " +
                "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('$SELF','OnlyErrorDialogs','SendToRecycleBin')"
            )
            Say "(this setup file will move itself to the Recycle Bin)"
        } catch { }
    }

    $btn.Text = "Close"
    $btn.BackColor = $GOOD
    $btn.Enabled = $true
    $script:Halted = $true
}

$btn.Add_Click({
    if ($script:Halted) { $form.Close(); return }
    $btn.Enabled = $false
    $btn.Text = "Working..."
    [System.Windows.Forms.Application]::DoEvents()
    & $script:Steps[$script:Idx].Action
    if (-not $script:Halted) {
        $script:Idx++
        Present
    }
})

# ------------------------------------------------------------- detect
$form.Add_Shown({
    Say "Checking your computer..."
    $h,$total = Heap-MB
    Say "  memory: $total MB"

    $script:Prism = Find-Prism
    if ($script:Prism) { Say "  Prism Launcher: $script:Prism" }
    else { Say "  Prism Launcher: not installed" }

    $existing = @(Find-PackInstances $script:Prism $OLD_URL) +
                @(Find-PackInstances $script:Prism $PACK_URL)

    if ($existing.Count -gt 0) {
        $script:Mode = "update"
        Say "  found $($existing.Count) existing Salvage instance(s)"
        $script:Steps = @(
            @{ Name="Check what you have";              Action={ Step-CheckUpdate } },
            @{ Name="Point it at the right updates";    Action={ Step-Switch } },
            @{ Name="Make sure the updater is there";   Action={ Step-BootstrapAll } }
        )
    } else {
        $script:Mode = "install"
        $script:Steps = @(
            @{ Name="Get Prism Launcher";            Action={ Step-Prism } },
            @{ Name="Create the Salvage instance";   Action={ Step-Instance } },
            @{ Name="Set up automatic updates";      Action={ Step-Bootstrap } }
        )
    }
    Say ""
    Present
})

$script:Halted = $false
[void]$form.ShowDialog()
