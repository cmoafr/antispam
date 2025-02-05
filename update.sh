#!/bin/bash

git pull

# Ensure venv and dependencies are good
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Restart the bot
set +e
pkill -TERM python3
set -e
screen -dmS antispam python3 main.py

# Disconnect
exit
