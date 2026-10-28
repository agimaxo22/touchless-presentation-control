#!/bin/bash
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "First create the environment using the installation steps in README.md."
  read -r -p "Press Enter to close."
  exit 1
fi
exec .venv/bin/python app.py
