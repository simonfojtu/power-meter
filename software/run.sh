#!/bin/bash -e

LOG_FILE=/home/pi/power-meter.git/software/power_meter.log

pushd /home/pi/power-meter.git
source venv/bin/activate

pushd software
python power_meter.py 0:0:C:507.1:0.025:#ff0000:"L1" 1:0:V:500.196:0.75:: >> $LOG_FILE 2>&1 &
