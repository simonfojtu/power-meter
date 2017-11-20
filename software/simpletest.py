import argparse
from datetime import datetime
import numpy as np
import os.path
import subprocess
# Import SPI library (for hardware SPI) and MCP3008 library.
import Adafruit_GPIO.SPI as SPI
import Adafruit_MCP3008


class ADC:
    MAX_NUM_CHANNELS=8

    def __init__(self, spi_port = 0, spi_device = 0, *, num_channels = MAX_NUM_CHANNELS):
        self.mcp = Adafruit_MCP3008.MCP3008(spi=SPI.SpiDev(spi_port, spi_device))
        self.num_channels = num_channels
        self.calibrated_zero = np.zeros((self.num_channels,))
        self.calibrated_gain = np.zeros((self.num_channels,))


    def read_raw(self, idx):
        """Return analog value on channel idx"""
        return self.mcp.read_adc(idx)


    def read(self, idx):
        return (self.read_raw(idx) - self.calibrated_zero[idx]) * self.calibrated_gain[idx]


    def set_zero(self, idx, value):
        self.calibrated_zero[idx] = value


    def set_gain(self, idx, value):
        self.calibrated_gain[idx] = value


    def calibrate_zero(self, idx, count=1000):
        """Assuming a 'zero' signal on channel idx, compute the mean over count measurements"""
        x = 0
        for _ in range(count):
            x += self.read_raw(idx)
        self.calibrated_zero[idx] = x / count
        return self.calibrated_zero[idx]


    def calibrate_gain(self, idx, count=1000):
        x = np.zeros((count,))
        for i in range(count):
            x[i] = self.read(idx)
        return np.mean(np.sort(x)[-count//10:])


class RRD:
    def __init__(self, filename, *, graph_directory = '.', create=[], graph=[]):
        self.filename = filename
        self.graph_args = graph
        self.graph_directory = graph_directory 
        if not os.path.isfile(filename):
            subprocess.call(['rrdtool', 'create', filename, *args])

    def update(self, values, timestamp='N'):
        data=':'.join([str(v) for v in values])
        subprocess.Popen(['rrdtool', 'update', self.filename, str(timestamp) + ':' + data])

    def graph(self, *, start='1day', title='power consumption'):
        fname = os.path.join(self.graph_directory, 'graph_' + start + '.png')
        subprocess.Popen(
            [
                'rrdtool', 'graph', fname,
                '-s', '-' + start,
                '-t', title,
                *self.graph_args,
            ],
            stdout=subprocess.DEVNULL
            )


parser = argparse.ArgumentParser(description='AC power measurement')
parser.add_argument('-n', type=int, default=8, help='Number of channels to use')
parser.add_argument('-c', action='append', type=int, default=None, help='Return bias calibration value for given channel')
parser.add_argument('-C', action='append', type=float, default=[], help='Zero calibration for each channel')
parser.add_argument('-g', action='append', type=int, default=None, help='Return gain calibration value for given channel')
parser.add_argument('-G', action='append', type=float, default=[], help='Gain calibration for each channel')
parser.add_argument('--verbose', '-v', action='store_true', help='Be verbose')

# Add parser to channel parameters:
# #channel_number:#phase_number:<V/C>:zero:gain:description

args = parser.parse_args()

adc = ADC(num_channels = args.n)
rrd = RRD('power.rrd',
    graph_directory = 'www/',
    create=[
        '--step', '1s',
        'DS:watt:GAUGE:5m:0:U',
        'DS:va:GAUGE:5m:0:U', 
        'RRA:AVERAGE:0.5:1s:10d',
        'RRA:AVERAGE:0.5:1m:90d',
        'RRA:AVERAGE:0.5:1h:18M',
        'RRA:AVERAGE:0.5:1d:10y',
        'RRA:MAX:0.5:1s:10d',
        'RRA:MAX:0.5:1m:90d',
        'RRA:MAX:0.5:1h:18M',
        'RRA:MAX:0.5:1d:10y',
    ],
    graph=[
        '--lazy',
        '--border', '0',
        '-v', 'W',
        '--color', 'BACK#101010',
        '--color', 'CANVAS#000000',
        '--color', 'FONT#ffffff',
        '--font', 'LEGEND:7',
        'DEF:watt=power.rrd:watt:AVERAGE',
        'LINE1:watt#FF0000']
)

if len(args.C) not in (0, adc.num_channels):
    raise ValueError('Specify zero calibration either for all channels or for none')
for i in range(len(args.C)):
    adc.set_zero(i, args.C[i])
if args.c is not None:
    for channel in args.c:
        print('Calibrating zero of channel {}'.format(channel))
        print(adc.calibrate_zero(channel))
    exit()


if len(args.G) not in (0, adc.num_channels):
    raise ValueError('Specify gain either for all channels or for none')
for i in range(len(args.G)):
    adc.set_gain(i, args.G[i])
if args.g is not None:
    for channel in args.g:
        print('Calibrating gain of channel {}'.format(channel))
        print(adc.calibrate_gain(channel))
    exit()

if args.verbose:
    print('Starting measurements')

counter = 0
sum_of_powers = 0
ssu = 0
ssi = 0

average_over_N_periods = 50 # every second at 50Hz
num_periods = 0

u = 0
last_time = datetime.now()

while True:
    last_u = u
    i = adc.read(0)
    u = adc.read(1)

    sum_of_powers += i * u
    ssu += u * u
    ssi += i * i
    counter += 1
    if last_u <= 0 and u > 0:
        num_periods += 1
        now = datetime.now()
        if num_periods == average_over_N_periods and now.second != last_time.second:
            last_time = now

            real_power = sum_of_powers / counter
            vrms = np.sqrt(ssu / counter)
            irms = np.sqrt(ssi / counter)
            apparent_power = vrms * irms
            power_factor = real_power / apparent_power
            if args.verbose:
                print('real power: {:3.1f}W, apparent power: {:3.1f}VA, power factor: {:2.1f}%, Vrms: {:3.1f}V, Irms: {:3.1f}A'.format(
                real_power, apparent_power, 100*power_factor, vrms, irms))

            rrd.update([real_power, apparent_power])
            
            if now.second % 10 == 0:
                rrd.graph(start='1day')
                rrd.graph(start='1week')
                rrd.graph(start='1month')
                rrd.graph(start='1year')



            counter = 0
            sum_of_powers = 0
            num_periods = 0
            ssu = 0
            ssi = 0

