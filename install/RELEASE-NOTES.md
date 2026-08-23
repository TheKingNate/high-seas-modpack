## Install

Download the file for your computer from the Assets list below
and run it. It sets up everything for you and tells you what
it's doing at each step.

**Windows** - `Salvage-Setup-Windows.bat`, double-click it.

**macOS** - `Salvage-Setup-Mac.command`. The first time,
right-click it and choose **Open**, so macOS allows it.

**Linux** - `Salvage-Setup-Linux.sh`, then in a terminal:
`bash ~/Downloads/Salvage-Setup-Linux.sh`

It installs Prism Launcher if you don't have it, creates the
instance, sets your memory, and turns on automatic updates.
If you already have Salvage installed, it updates your setup
instead and leaves your world and settings alone.

Afterwards: open Prism, sign in with your Microsoft account,
click **Salvage**, press **Launch**. First launch downloads
about 150 mods, so give it several minutes.

## Joining the server

Try to connect once. It'll say you aren't whitelisted - that's
expected, and it's how you get added. Just say you tried.

## Already playing?

You don't need to do anything. The pack updates itself the next
time you launch.

## Running your own server

Download `setup-server.sh` onto a Linux box and run it:

    bash setup-server.sh

Installs Fabric, pulls the server-side mods, and writes start,
update, backup and whitelist helper scripts. Prints the systemd
unit to paste when it finishes.

**Requires Java 21 or newer.** Java 17 runs the client fine but
is not enough for the server - one of the server-side mods needs
Java 21 and the server will abort during startup without it.

    Ubuntu/Debian:  sudo apt install -y openjdk-21-jre-headless
    Fedora:         sudo dnf install -y java-21-openjdk-headless
