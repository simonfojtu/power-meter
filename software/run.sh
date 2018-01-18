#!/bin/bash -e

LOG_FILE=/home/pi/power-meter.git/software/power_meter.log

pushd /home/pi/power-meter.git
source venv/bin/activate

pushd software
#python power_meter.py \
#1:0:C:507.1:0.025:#ff0000:"L1" \
#7:0:V:500.196:0.75:: \
#2:0:C:507.1:0.025:#ff0000:"L2" \
#6:0:V:500.196:0.75:: \
#3:0:C:507.1:0.025:#ff0000:"L3" \
#5:0:V:500.196:0.75:: \

python power_meter.py -v \
1:0:C:336:0.15:#ff0000:"L1" \
7:0:V:336:-1.94:: \
2:1:C:336:0.15:#00ff00:"L2" \
6:1:V:336:-1.94:: \
3:2:C:336:0.15:#0000ff:"L3" \
5:2:V:336:-1.94:: 

