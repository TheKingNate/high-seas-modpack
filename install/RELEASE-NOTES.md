## Install

Download the file for your computer and run it. It sets up
everything for you and tells you what it's doing at each step.

**Windows** - download `salvage-setup.ps1`, right-click it,
choose **Run with PowerShell**.

**macOS / Linux** - download `salvage-setup.py`, then in a
terminal: `python3 ~/Downloads/salvage-setup.py`

It installs Prism Launcher if you don't have it, creates the
instance, sets your memory, and turns on automatic updates.
If you already have Salvage installed, it updates your setup
instead and leaves your world and settings alone.

Afterwards: open Prism, sign in with your Microsoft account,
click **Salvage**, press **Launch**. First launch downloads
about 150 mods.

## Joining the server

Try to connect once. It'll say you aren't whitelisted - that's
expected, and it's how you get added. Just say you tried.

## Already playing?

You don't need to do anything. The pack updates itself the next
time you launch.

## Running your own server

Download `setup-server.sh` onto a Linux box and run it:

Installs Fabric, pulls the server-side mods, and writes start,
update, backup and whitelist helper scripts. Prints the systemd
unit to paste when it finishes.
