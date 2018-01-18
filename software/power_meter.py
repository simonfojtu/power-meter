import argparse
import datetime
from itertools import count
import numpy as np
import os
import subprocess
# Import SPI library (for hardware SPI) and MCP3008 library.
import Adafruit_GPIO.SPI as SPI
import Adafruit_MCP3008


class ADC:
    def __init__(self, spi_port = 0, spi_device = 0):
        self.mcp = Adafruit_MCP3008.MCP3008(spi=SPI.SpiDev(spi_port, spi_device))

    def read(self, idx):
        """Return analog value on channel idx"""
        return self.mcp.read_adc(idx)


class RRD:
    def __init__(self, filename, *, graph_directory = '.', create=[], graph=[]):
        """Create rrd file if necessary"""
        # TODO Check that the existing rrd file is compatible with current channels
        self.filename = filename
        self.graph_args = graph
        self.graph_directory = graph_directory 
        if not os.path.isfile(filename):
            print('Creating RRD in {}'.format(filename))
            subprocess.call(['rrdtool', 'create', filename, *create])
        self.pid = None

    def update(self, values, timestamp='N'):
        # TODO handle error
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


class Channel:
    class Calibrated(BaseException):
        pass


    def __init__(self, adc, str_config):
        self.adc = adc
        self.id = 0
        self.phase = 0
        self.V = True
        self.zero = 0
        self.gain = 1
        self.colour = '#ff0000'
        self.description = ''
        args = str_config.split(':')
        length = len(args)
        
        self.id = int(args[0])
        if length == 3 and args[2] == '?':
            # print RMS
            self.zero = float(args[1])
            print('Channel {} calibration: measured {:.2f} units RMS'.format(
                self.id, self.get_rms()))
            raise Channel.Calibrated
        elif length == 7:
            self.phase = int(args[1])
            if args[2] not in ('V', 'C'):
                raise ValueError('{} not "V" or "C" for voltage and current respectively')
            self.V = 'V' == args[2]

            self.zero = float(args[3])
            self.gain = float(args[4])
            self.colour = args[5]
            self.description = args[6]
        else:
            raise ValueError('Invalid channel configuration: {}'.format(str_config))


    def __str__(self):
        return 'Channel  idx: {}, phase: {}, {}, zero: {}, gain: {}, color: {}, {}'.format(
            self.id, self.phase, 'V' if self.V else 'C', self.zero, self.gain, self.colour, self.description)


    def get_unit(self):
        return 'V' if self.V else 'A'


    def _read_raw(self):
        """Read data from ADC for this channel"""
        return adc.read(self.id)


    def read(self):
        """Return calibrated value for this channel"""
        self.value = (self._read_raw() - self.zero) * self.gain
        return self.value


    def get(self):
        """Return calibrated value for this channel without reading from the ADC if possible"""
        if self.value is not None:
           return self.value

        return self.read()


    def get_rms(self, num_periods=50*5):
        """Return RMS"""
        # TODO measure over whole periods
        assert num_periods > 0
        ssq = 0
        count = 0
        num_measurements = num_periods * 100
        data = np.zeros((num_measurements,))
        while count < num_measurements:
            x = self.read()
            data[count] = x
            ssq += x*x
            count += 1
        print('num_measurements = ', num_measurements)
        print('mean = ', np.mean(data))
        print('rms  = ', np.sqrt(np.dot(data, data) / num_measurements))
        print('max  = ', np.max(data))
        print('min  = ', np.min(data))
        print('PP   = ', np.max(data) - np.min(data))
        print('mean PP=', (np.max(data) + np.min(data))/2)
        return np.sqrt(ssq / count)


class Meter:
    class PowerMeter:
        def __init__(self, frequency, voltage_channel, current_channel):
            self.frequency = frequency
            self.voltage_chn = voltage_channel
            self.current_chn = current_channel

            self.sp = 0
            self.rmsv = 0
            self.rmsc = 0
            self.counter = 0
            self.num_periods = 0
            self.last_voltage = 0

            self.last_real_power = 0
            self.last_rmsv = 0
            self.last_rmsc = 0


        @property
        def description(self):
            return self.current_chn.description


        @property
        def colour(self):
            return self.current_chn.colour


        def getRealPower(self):
            voltage = self.voltage_chn.get()
            current = self.current_chn.get()
            self.sp += voltage * current
            self.rmsv += voltage * voltage
            self.rmsc += current * current
            self.counter += 1

            if self.last_voltage <= 0 and voltage > 0:
                self.num_periods += 1

            self.last_voltage = voltage
            fresh = False
            if self.num_periods == self.frequency:
                real_power = self.sp / self.counter
                rmsv = np.sqrt(self.rmsv / self.counter)
                rmsc = np.sqrt(self.rmsc / self.counter)
                self.last_real_power = real_power
                self.last_rmsv = rmsv
                self.last_rmsc = rmsc
                fresh = True

                self.sp = 0
                self.rmsv = 0
                self.rmsc = 0
                self.counter = 0
                self.num_periods = 0

            return self.last_real_power, self.last_rmsv, self.last_rmsc, fresh


            
    def __init__(self, adc, args):# ,channels_configs, *, frequency=50, verbose=False):
        self.adc = adc
        self.frequency = args.frequency
        self.verbose = args.verbose
        self.graphperiod = args.graphperiod
        self.last_graph = datetime.datetime.now()
        self.power_meters = tuple()
        self.channels = {}
        for cfg in args.channels:
            try:
                c = Channel(self.adc, cfg)
                if self.verbose:
                    print(c)
                self.channels[c.id] = c
            except Channel.Calibrated:
                exit(0)

        self.pairChannels()

        rrd_create = [
            '--step', '1s',
            'RRA:AVERAGE:0.5:1s:10d',
            'RRA:AVERAGE:0.5:1m:90d',
            'RRA:AVERAGE:0.5:1h:18M',
            'RRA:AVERAGE:0.5:1d:10y',
            'RRA:MAX:0.5:1s:10d',
            'RRA:MAX:0.5:1m:90d',
            'RRA:MAX:0.5:1h:18M',
            'RRA:MAX:0.5:1d:10y',
        ]
        for i in range(len(self.power_meters)):
            rrd_create += 'DS:ch{}:GAUGE:5m:0:U'.format(i),

        rrd_graph = [
            '--lazy',
            '--border', '0',
            '-v', 'W',
            '--color', 'BACK#101010',
            '--color', 'CANVAS#000000',
            '--color', 'FONT#ffffff',
            '--font', 'LEGEND:7',
        ]
        for i,m in enumerate(self.power_meters):
            rrd_graph += 'DEF:ch{0}={1}:ch{0}:AVERAGE'.format(i, args.rrdfile),
            # TODO make color parametrizable
            rrd_graph += 'LINE1:ch{}{}:{}'.format(i, m.colour, m.description),
        # TODO this is hardcoded..
        rrd_graph += 'CDEF:sum=ch0,ch1,+,ch2,+',
        rrd_graph += 'LINE1:sum#ffffff:sum',

        self.rrd = RRD(
            args.rrdfile,
            graph_directory = args.graphdir,
            create=rrd_create,
            graph=rrd_graph
        )

        if args.verbose:
            print('Meter initialized')


    
    def pairChannels(self):
        # phase -> (voltage_idx, (current_indices, ..))
        phase2voltage = {}
        for cid in self.channels:
            c = self.channels[cid]
            if c.V:
                if c.phase in phase2voltage:
                    raise ValueError(
                        'Only a single voltage measurement per phase is allowed. \
                         voltage channels for phase {} found on index {} and {}'.format(
                            c.phase, phase2voltage[c.phase], c.id))

                phase2voltage[c.phase] = c.id

        for cid in self.channels:
            c = self.channels[cid]
            if not c.V:
                if not c.phase in phase2voltage:
                    raise ValueError('Current channel {} on phase {} has no associated voltage channel.'.format(
                        c.id, c.phase))
                self.power_meters += (Meter.PowerMeter(
                    self.frequency,
                    self.channels[phase2voltage[c.phase]],
                    c
                )),

        if self.verbose:
            for meter in self.power_meters:
                print('Power measurement "{}" on channels:\n\t{} (voltage)\n\t{} (current)'.format(
                    meter.description,
                    meter.voltage_chn,
                    meter.current_chn))


    def measure(self):
        # Read current values on all channels
        for cid in self.channels:
            x = self.channels[cid].read()
            #if self.verbose:
            #    print('channel {}: {}'.format(cid, x))

        # compute power from previously read input values
        output = [0] * len(self.power_meters)
        do_update = False
        for i,meter in enumerate(self.power_meters):
            real_power, rmsv, rmsc, fresh = meter.getRealPower()
            output[i] = real_power
            if fresh:
                if self.verbose:
                    print('Meter {:}: {:6.1f}W, {:5.1f}VRMS, {:5.1f}ARMS'.format(i, real_power, rmsv, rmsc))
            # TODO fix this if for some reason the first channel is off
            if i==0 and fresh:
                do_update = True

        if do_update:
            if self.verbose:
                print('rrd update: ', output)
            self.rrd.update(output)


    def graph(self):
        now = datetime.datetime.now()
        if now > self.last_graph + datetime.timedelta(seconds=self.graphperiod):
            if args.verbose:
                print('do some graphing')
            self.last_graph = now
            # TODO parametrize the graphs
            self.rrd.graph(start='1day')
            self.rrd.graph(start='1week')
            self.rrd.graph(start='1month')
            self.rrd.graph(start='1year')

        

parser = argparse.ArgumentParser(description='AC power measurement')
parser.add_argument('--verbose', '-v', action='store_true', help='Be verbose')
parser.add_argument('--frequency', '-f', type=int, default=50, help='Line frequency (50/60Hz)')
parser.add_argument(type=str, nargs='+', dest='channels', help="Channel configuration in the following format: #channel_number:#phase_number:<V/C>:zero:gain:#RRGGBB[AA]:description")
parser.add_argument('--rrdfile', type=str, default='power.rrd', help='Name of the rrd file')
parser.add_argument('--graphdir', type=str, default='www/', help='Directory to store generated graphs')
parser.add_argument('--graphperiod', type=int, default=60, help='Plot graph at most every N seconds')

args = parser.parse_args()
adc = ADC()
meter = Meter(adc, args)

while True:
    meter.measure()
    meter.graph()
