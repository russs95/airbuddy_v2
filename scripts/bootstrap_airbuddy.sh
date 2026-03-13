#!/usr/bin/env bash

set -e

cat <<'BANNER'

        .  .  .   .  .  .   .  .  .
      .  .-~~~-.   .-~~~-.   .-~~~-.  .
     .  (       ) (       ) (       )  .
    .    '-~~~-'   '-~~~-'   '-~~~-'   .
      .  .  .   .  .  .   .  .  .  .

      _    _      ____            _     _
     / \  (_)_ __| __ ) _   _  __| | __| |_   _
    / _ \ | | '__|  _ \| | | |/ _` |/ _` | | | |
   / ___ \| | |  | |_) | |_| | (_| | (_| | |_| |
  /_/   \_\_|_|  |____/ \__,_|\__,_|\__,_|\__, |
                                        |___/

                    ~  KNOW THY AIR  ~

BANNER

echo "Hey buddy, take a deep breath... it's installation time!"
echo
echo "You're about to set up a real-time air quality monitor on your"
echo "Raspberry Pi Pico or ESP32. It reads CO2, TVOC, temperature,"
echo "and humidity, and streams the data live to your Buwana dashboard."
echo
echo "This script will:"
echo "  1. check that Git is installed"
echo "  2. download the AirBuddy code to ~/Documents/AirBuddy"
echo "  3. hand things off to the device installer"
echo
echo "Estimated time: about 2-3 minutes. Let's breathe some data!"
echo

while true; do
    read -r -p "Ready to go? y/n: " READY
    case "${READY,,}" in
        y|yes)
            echo
            break
            ;;
        n|no)
            echo
            echo "Ok, maybe some other time then! Until next time."
            exit 0
            ;;
        *)
            echo "Please answer y or n."
            echo
            ;;
    esac
done

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