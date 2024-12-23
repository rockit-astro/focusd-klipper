#
# This file is part of the Robotic Observatory Control Kit (rockit)
#
# rockit is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# rockit is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with rockit.  If not, see <http://www.gnu.org/licenses/>.

"""Logic to control a stepper motor using the Klipper MCU API"""

import math
from .constants import StepperStatus

HOMING_START_DELAY = 0.1
ENDSTOP_SAMPLE_TIME = .000015
ENDSTOP_SAMPLE_COUNT = 4

TRIGGER_ACTIVE = 0
TRIGGER_AT_LIMIT = 1
TRIGGER_MANUAL = 2
TRIGGER_TIMEOUT = 4

def parse_pin(value):
    pullup = invert = 0
    if value[0] in ['^', '~']:
        pullup = -1 if value[0] == '~' else 1
        value = value[1:]

    if value[0] == '!':
        invert = 1
        value = value[1:]
    return pullup, invert, value


def build_command(command, **kwargs):
    return command + ' ' + ' '.join(f'{k}={v}' for k, v in kwargs.items())

class Stepper:
    def __init__(self, config_json, mcu):
        self.status = StepperStatus.NotHomed
        self._config = config_json
        self._steps_per_distance = self._config['rotation_microsteps'] / self._config['rotation_distance']
        self._mcu = mcu
        self._stepper_oid = mcu.reserve_oid()
        self._enable_oid = mcu.reserve_oid()
        self._trigger_oid = mcu.reserve_oid()
        self._endstop_oid = mcu.reserve_oid() if 'endstop_pin' in self._config else -1
        self._pos_steps_at_origin = 0
        self._pos_steps = 0
        self._pos_steps_count = 0
        self._trigger_status = TRIGGER_ACTIVE
        self._trigger_status_count = 0

        self._uart = None
        if 'tmc_uart' in self._config:
            self._uart = mcu.tmc_uarts[self._config['tmc_uart']['uart']]

        def on_trigger(params):
            self._trigger_status = params['trigger_reason']
            self._trigger_status_count += 1

        mcu.serial.register_response(on_trigger, 'trsync_state', self._trigger_oid)

        def on_position(params):
            self._pos_steps = params['pos']
            self._pos_steps_count += 1

        mcu.serial.register_response(on_position, 'stepper_position', self._stepper_oid)

    @property
    def position(self):
        return (self._pos_steps - self._pos_steps_at_origin) / self._steps_per_distance

    def get_configure_commands(self):
        _, step_invert, step_pin = parse_pin(self._config['step_pin'])
        _, _, dir_pin = parse_pin(self._config['dir_pin'])
        _, enable_invert, enable_pin = parse_pin(self._config['enable_pin'])

        # TODO: This requires TMC drivers, add case for others
        yield build_command('config_stepper', oid=self._stepper_oid,
                            step_pin=step_pin, dir_pin=dir_pin,
                            invert_step=-1, step_pulse_ticks=0)

        # Enable motor by default (stepper driver will automatically go into low power mode when idle)
        # TODO: dual edge stepping requires TMC drivers, add case for others
        yield build_command('config_digital_out', oid=self._enable_oid,
                            pin=enable_pin, value=0 if enable_invert else 1,
                            default_value=enable_invert, max_duration=0)
        yield build_command('config_trsync', oid=self._trigger_oid)

        if 'endstop_pin' in self._config:
            endstop_pullup, endstop_inverted, endstop_pin = parse_pin(self._config['endstop_pin'])
            yield build_command('config_endstop', oid=self._endstop_oid,
                                pin=endstop_pin, pull_up=endstop_pullup)

    def configure(self):
        self.status = StepperStatus.NotHomed
        if self._uart is not None:
            addr = self._config['tmc_uart']['address']

            # enable pdn_disable, mstep_reg_select
            self._uart.write_register(addr, 'GCONF', 0xC0)

            # senddelay=2
            self._uart.write_register(addr, 'SLAVECONF', 0x200)

            # enable dedge, intpol, vsense, tbl=2, hstrt=5, toff=3
            chopconf = 0x30030053
            # set microsteps
            chopconf |= int(8 - math.log2(self._config['tmc_uart']['microsteps'])) << 24
            self._uart.write_register(addr, 'CHOPCONF', chopconf)

            # tpowerdown=20
            self._uart.write_register(addr, 'TPOWERDOWN', 0x14)

            # enable pasive breaking (HS drivers), pwm_autoscale, pwm_autograd
            # pwm_ofs=36 pwm_grad=14 pwm_freq=1 pwm_reg=8 pwm_lim=12
            self._uart.write_register(addr, 'PWMCONF', 0xC83D0E24)

            # iholddelay=8, ihold=0
            iholdirun = 0x80000
            # from TMCCurrentHelper, assuming a 0.11 ohm sense resistor
            rc = self._config['tmc_uart']['run_current']
            irun = max(0, min(31, int(32. * 0.130 * rc * math.sqrt(2.) / 0.18 + .5) - 1))
            iholdirun |= irun << 8
            self._uart.write_register(addr, 'IHOLD_IRUN', iholdirun)

    def calculate_move(self, distance, max_speed, accel):
        """Return one or more tuples of step interval and step count"""
        # Break the motion into three phases:
        # 1. Acceleration from rest either to the requested speed,
        #    or until 1/4 of the total distance has been travelled
        # 2. Constant velocity
        # 3. Deceleration to rest at the requested distance
        total_steps = int(distance * self._steps_per_distance + 0.5)

        # Reduce speed so that the coast phase always covers at least half of the total distance
        coast_speed = min(max_speed, math.sqrt(0.5 * distance * accel))
        coast_interval = int(self._mcu.clocksync.mcu_freq / (coast_speed * self._steps_per_distance))

        acceleration_time = coast_speed / accel
        acceleration_distance = 0.5 * accel * acceleration_time ** 2
        acceleration_steps = int(acceleration_distance * self._steps_per_distance + 0.5)
        coast_steps = total_steps - 2 * acceleration_steps
        coast_ticks = coast_steps * coast_interval

        acceleration_add = -int(2 * coast_interval / acceleration_steps)
        acceleration_interval = coast_interval - acceleration_steps * acceleration_add

        acceleration_ticks = deceleration_ticks = 0
        for i in range(acceleration_steps):
            acceleration_ticks += acceleration_interval + i * acceleration_add
            deceleration_ticks += coast_interval - i * acceleration_add

        yield acceleration_steps, acceleration_interval, acceleration_add, acceleration_ticks
        yield coast_steps, coast_interval, 0, coast_ticks
        yield acceleration_steps, coast_interval, -acceleration_add, deceleration_ticks

    def _move(self, distance, speed, acceleration, check_endstop):
        start_time = self._mcu.clocksync.estimated_print_time(self._mcu.serial.reactor.monotonic()) + HOMING_START_DELAY
        start_clock = self._mcu.clocksync.print_time_to_clock(start_time)
        step_dir = 1 if distance * speed > 0 else 0

        self._trigger_status = TRIGGER_ACTIVE
        self._mcu.serial.send(build_command('set_next_step_dir', oid=self._stepper_oid, dir=step_dir))
        self._mcu.serial.send(build_command('reset_step_clock', oid=self._stepper_oid, clock=start_clock))

        end_clock = start_clock
        for count, interval, add, ticks in self.calculate_move(abs(distance), speed, acceleration):
            while count > 0:
                # queue_step is limited to 16 bit counts
                c = min(65535, count)
                self._mcu.serial.send(build_command('queue_step', oid=self._stepper_oid, interval=interval, count=c, add=add))
                count -= c
                interval += c * add
            end_clock += ticks

        self._mcu.serial.send(build_command('trsync_start', oid=self._trigger_oid, report_clock=0, report_ticks=0, expire_reason=TRIGGER_TIMEOUT))
        self._mcu.serial.send(build_command('trsync_set_timeout', oid=self._trigger_oid, clock=end_clock))
        self._mcu.serial.send(build_command('stepper_stop_on_trigger', oid=self._stepper_oid, trsync_oid=self._trigger_oid))

        if check_endstop:
            sample_ticks = self._mcu.clocksync.print_time_to_clock(ENDSTOP_SAMPLE_TIME)
            rest_ticks = int(self._mcu.clocksync.mcu_freq / (5 * speed * self._steps_per_distance) + 0.5)

            _, endstop_inverted, _ = parse_pin(self._config['endstop_pin'])
            endstop_value = 0 if endstop_inverted else 1
            self._mcu.serial.send(build_command('endstop_home', oid=self._endstop_oid, clock=start_clock, sample_ticks=sample_ticks,
                                            sample_count=ENDSTOP_SAMPLE_COUNT, rest_ticks=rest_ticks, pin_value=endstop_value,
                                            trsync_oid=self._trigger_oid, trigger_reason=TRIGGER_AT_LIMIT))

        query_position_command = build_command('stepper_get_position', oid=self._stepper_oid)
        while self._trigger_status == TRIGGER_ACTIVE:
            self._mcu.serial.send(query_position_command)
            self._mcu.serial.reactor.pause(self._mcu.serial.reactor.monotonic() + 0.1)

        if self._trigger_status == TRIGGER_TIMEOUT:
            print('Homing timed out')
        else:
            # Ensure position is synchronised
            count = self._pos_steps_count
            self._mcu.serial.send(query_position_command)
            while self._pos_steps_count == count:
                self._mcu.serial.reactor.pause(self._mcu.serial.reactor.monotonic() + 0.1)

        #disable_time = self._mcu.clocksync.estimated_print_time(self._mcu.serial.reactor.monotonic()) + 0.1
        #disable_clock = self._mcu.clocksync.print_time_to_clock(disable_time)
        #self._serial.send(build_command('queue_digital_out', oid=self._enable_oid, clock=disable_clock, on_ticks=1))


    def home_async(self):
        def inner(_):
            # Move quickly to endstop
            self.status = StepperStatus.Homing
            distance_rough = self._config['position_min'] - self._config['position_max']
            self._move(distance_rough, self._config['speed'], self._config['acceleration'], True)

            # back off a bit
            self._move(self._config['homing_backoff'], self._config['speed'] / 2, self._config['acceleration'], False)

            # Move slowly to endstop
            self._move(-2 * self._config['homing_backoff'], self._config['speed'] / 10, self._config['acceleration'], True)
            self._pos_steps_at_origin = self._pos_steps
            self.status = StepperStatus.Idle

        self._mcu.serial.reactor.register_callback(inner)

    def move_async(self, distance):
        def inner(_):
            self.status = StepperStatus.Moving
            self._move(distance, self._config['speed'], self._config['acceleration'], False)
            self.status = StepperStatus.Idle

        self._mcu.serial.reactor.register_callback(inner)

    def stop(self):
        def inner(_):
            self._mcu.serial.send(f'trsync_trigger oid={self._trigger_oid} reason={TRIGGER_MANUAL}')
        self._mcu.serial.reactor.register_async_callback(inner)

    def set_speed(self, speed):
        if self._uart is not None:
            addr = self._config['tmc_uart']['address']
            self._uart.write_register(addr, 'VACTUAL', int(speed * self._steps_per_distance / 0.715))
