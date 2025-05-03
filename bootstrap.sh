#!/usr/bin/env bash
cd "$(dirname "$0")"

# Setup Python dependencies
pip install -r requirements.txt
deactivate &> /dev/null
echo "Installing pip"
sudo apt install python3-pip
echo "Installing venv manager"
sudo apt install python3.12-venv
rm -rf venv/
python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Install HTML/CSS dependencies
if ! command -v npm >/dev/null 2>&1; then
    echo "Installing npm"
    sudo apt install npm
fi
npm install --save-dev \
  prettier \
  stylelint \
  stylelint-config-standard