import argparse
import numpy as np
# Import SPI library (for hardware SPI) and MCP3008 library.
import Adafruit_GPIO.SPI as SPI
import Adafruit_MCP3008


class Interface:
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



parser = argparse.ArgumentParser(description='AC power measurement')
parser.add_argument('-n', type=int, default=8, help='Number of channels to use')
parser.add_argument('-c', action='append', type=int, default=None, help='Return bias calibration value for given channel')
parser.add_argument('-C', action='append', type=float, default=[], help='Zero calibration for each channel')
parser.add_argument('-g', action='append', type=int, default=None, help='Return gain calibration value for given channel')
parser.add_argument('-G', action='append', type=float, default=[], help='Gain calibration for each channel')

args = parser.parse_args()

adc = Interface(num_channels = args.n)

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

print('Starting measurements')

counter = 0
sum_of_powers = 0
ssu = 0
ssi = 0

num_periods = 0

u = 0


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
        if num_periods == 50:
            real_power = sum_of_powers / counter
            vrms = np.sqrt(ssu / counter)
            irms = np.sqrt(ssi / counter)
            apparent_power = vrms * irms
            power_factor = real_power / apparent_power
            print('real power: {:3.1f}W, apparent power: {:3.1f}VA, power factor: {:2.1f}%, Vrms: {:3.1f}V, Irms: {:3.1f}A'.format(
                real_power, apparent_power, 100*power_factor, vrms, irms))

            counter = 0
            sum_of_powers = 0
            num_periods = 0
            ssu = 0
            ssi = 0

