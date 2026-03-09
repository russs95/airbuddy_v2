#!/usr/bin/env bash

set -e

cat <<'BANNER'

        .  .  .   .  .  .   .  .  .   .  .  .
      .  .-~~~-.   .-~~~-.   .-~~~-.   .-~~~-.  .
     .  (       ) (       ) (       ) (       )  .
    .    '-~~~-'   '-~~~-'   '-~~~-'   '-~~~-'   .
      .  .  .   .  .  .   .  .  .   .  .  .  .

      ___  o  ____    ____  _   _  ____  ____  _   _
     / _ \   |  _ \  |  _ )| | | ||  _ \|  _ \\ \ / /
    / /_\ \  | |_) | | |_) | |_| || | | || | | |\ V /
   /_/   \_\ |_|__/  |____/ \___/ |_|_/_/|_|_/  \_/

                    ~  Know thy air  ~

BANNER

echo "Hey there, future air quality champion! Welcome to AirBuddy."
echo
echo "You're about to set up a real-time air quality monitor on your"
echo "Raspberry Pi Pico or ESP32. It reads CO2, TVOC, temp & humidity"
echo "and streams the data live to your Buwana dashboard."
echo
echo "This script will:"
echo "  1. check that Git is installed"
echo "  2. download the AirBuddy code to ~/Documents/AirBuddy"
echo "  3. hand things off to the device installer"
echo
echo "Estimated time: about 2-3 minutes. Let's breathe some data!"
echo

# --------------------------------------------------
# Check Git
# --------------------------------------------------

if ! command -v git >/dev/null 2>&1; then
    echo "Hmm, Git doesn't seem to be installed on this machine."
    echo "No worries — here's how to grab it:"
    echo
    echo "  Ubuntu / Debian:  sudo apt install git"
    echo "  Mac (Homebrew):   brew install git"
    echo
    exit 1
fi

# --------------------------------------------------
# Create workspace
# --------------------------------------------------

WORKDIR="$HOME/Documents/AirBuddy"

echo "Setting up your AirBuddy workspace at:"
echo "  $WORKDIR"
echo

mkdir -p "$WORKDIR"
cd "$WORKDIR"

# --------------------------------------------------
# Download repo
# --------------------------------------------------

if [ ! -d "airbuddy_v2" ]; then
    echo "Pulling down the AirBuddy repository..."
    git clone https://github.com/russs95/airbuddy_v2
else
    echo "AirBuddy repo already found here — skipping download."
fi

cd airbuddy_v2

echo
echo "Got the code! Handing off to the device installer now..."
echo

chmod +x scripts/install_airbuddy.sh
./scripts/install_airbuddy.sh
