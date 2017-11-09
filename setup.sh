#!/bin/bash -xe
# Replicate the setup on the Raspberry PI

./install_commons.sh fpd

mkdir power_meter
cd power_meter

virtualenv --python=python3.5 venv
. venv/bin/activate

pip install adafruit-mcp3008 numpy

