POWER METER
===========

### Run the power monitoring script

Start the virtual environment

    source venv/bin/activate

Calibration is done in two steps
1. Zero calibration

unplug any input and short the two contacts if necessary. Then run for channel X the following command

    python power_meter.py X:0:?

This will return

    Channel X calibration: measured 500.20 units RMS

The returned value is the zero (virtual ground) calibration value for the channel X.

2. Gain calibration

Insert the current or voltage transformer into the channel connector and run

    python power_meter.py X:ZERO:?

where X is the channel number and ZERO the calibration value from the previous step.

    Channel 1 calibration: measured 305.35 units RMS
    
Now the returned value is the RMS value of the measured signal. If there is a voltage transformer on channel X and the RMS voltage on its primary side is 230V, then the gain calibration value is 230/305.35=0.75


Repeat the calibration procedure for all used channels.


3. Run the power monitoring script

When all channels are calibrated, the monitoring script can be started like this

    python power_meter.py 0:0:C:507.1:0.025:#ff0000:"L1" 1:0:V:500.196:0.75::

where the channel 0 is on phase 0, measuring current, zero calibration value is 507.1, gain calibration value 0.025, graph colour red and description "L1". On channel 1 there is a voltage transformer on phase 0 as well with its calibrationi values. No colour or description is given for this channel.


### Run the power monitoring script on RPi startup

Add the following line to /etc/rc.local before the exit 0 command

    /home/pi/power-meter.git/software/run.sh

### Pushing web pages to a ftp server for public display

e.g. by cron every 5 minutes

    */5 * * * * for f in path/to/www/*; do curl -T $f ftp://remote.server/subdirectory/ --user username:password > /dev/null; done
