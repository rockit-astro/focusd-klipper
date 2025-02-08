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

"""Daemon for controlling a multi-channel focus controller via klipper and Pyro"""
import threading
import traceback
import sys
import zlib

from .constants import MCUStatus, StepperStatus
from .stepper import Stepper
from .tmc_uart import TMCUART

sys.path.append('/home/ops/src/klipper/klippy')
import reactor, serialhdl, clocksync


class SyncCallback:
    """Run a reactor callback and block until completion"""
    def __init__(self, mcu, cb):
        self._mcu = mcu
        self._cb = cb
        self._exception = None
        self._condition = threading.Condition()

    def run(self, timeout=None):
        def inner(_):
            try:
                self._cb()
            except Exception as e:
                self._exception = e
            finally:
                with self._condition:
                    self._condition.notify()

        self._mcu.reactor.register_async_callback(inner)
        with self._condition:
            if not self._condition.wait(timeout):
                raise TimeoutError()
            if self._exception is not None:
                raise self._exception

class MCU:
    """Daemon interface for multi-channel focuser"""
    def __init__(self, config):
        self._config = config
        self._oid_count = 0

        self.status = MCUStatus.Disconnected

        self.reactor = reactor.Reactor()
        self.serial = serialhdl.SerialReader(self.reactor)
        self.clocksync = clocksync.ClockSync(self.reactor)
        self.tmc_uarts = {}
        self.steppers = {}

        for name, c in self._config['tmc_uarts'].items():
            self.tmc_uarts[name] = TMCUART(c, self)

        for name, c in self._config['steppers'].items():
            self.steppers[name] = Stepper(c, self)

        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                self.reactor.run()
            except:
                traceback.print_exc(file=sys.stdout)

    def reserve_oid(self):
        ret = self._oid_count
        self._oid_count += 1
        return ret

    def initialize(self):
        def inner():
            self.serial.connect_uart(self._config['serial_port'], self._config['serial_baud'])
            self.clocksync.connect(self.serial)

            config = self.serial.send_with_response('get_config', 'config')

            # Reboot MCU if needed
            if config['is_shutdown'] or config['is_config']:
                self.serial.send('reset')
                return inner()

            commands = [f'allocate_oids count={self._oid_count}']
            for u in self.tmc_uarts.values():
                commands.extend(u.get_configure_commands())

            for s in self.steppers.values():
                commands.extend(s.get_configure_commands())

            config_crc = zlib.crc32('\n'.join(commands).encode()) & 0xffffffff
            commands.append(f'finalize_config crc={config_crc}')
            for c in commands:
                self.serial.send(c)

            for s in self.steppers.values():
                s.configure()

            self.status = MCUStatus.Connected

        return SyncCallback(self, inner).run()

    def stepper_home(self, stepper_names):
        """Home stepper motors"""
        if type(stepper_names) is str:
            stepper_names = [stepper_names]

        def inner():
            homing = []
            for name in stepper_names:
                s = self.steppers.get(name, None)
                if s is not None:
                    s.home_async()
                    homing.append(s)

            while True:
                self.reactor.pause(self.reactor.monotonic() + 0.1)
                if all(s.status > StepperStatus.Homing for s in homing):
                    break

        return SyncCallback(self, inner).run()

    def stepper_move(self, stepper_names, distance):
        if type(stepper_names) is str:
            stepper_names = [stepper_names]

        def inner():
            moving = []
            for name in stepper_names:
                s = self.steppers.get(name, None)
                if s is not None:
                    s.move_async(distance)
                    moving.append(s)

            while True:
                self.reactor.pause(self.reactor.monotonic() + 0.1)
                if all(s.status > StepperStatus.Homing for s in moving):
                    break

        return SyncCallback(self, inner).run()

    def stepper_stop(self, stepper_names):
        if type(stepper_names) is str:
            stepper_names = [stepper_names]

        def inner():
            for name in stepper_names:
                s = self.steppers.get(name, None)
                if s is not None:
                    s.stop()

        return SyncCallback(self, inner).run()

    def shutdown(self):
        """Disconnects from the device"""
        def inner():
            self.serial.disconnect()
            self.status = MCUStatus.Disconnected

        return SyncCallback(self, inner).run()