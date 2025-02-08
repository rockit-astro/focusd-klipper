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

import threading

# Helper functions copied from Klipper tmc_uart.py
# Copyright (C) 2018-2021  Kevin O'Connor <kevin@koconnor.net>

def _calc_crc8(data):
    # Generate a CRC8-ATM value for a bytearray
    crc = 0
    for b in data:
        for i in range(8):
            if (crc >> 7) ^ (b & 0x01):
                crc = (crc << 1) ^ 0x07
            else:
                crc = (crc << 1)
            crc &= 0xff
            b >>= 1
    return crc


def _add_serial_bits(data):
    # Add serial start and stop bits to a message in a bytearray
    out = 0
    pos = 0
    for d in data:
        b = (d << 1) | 0x200
        out |= (b << pos)
        pos += 10
    res = bytearray()
    for i in range((pos + 7) // 8):
        res.append((out >> (i * 8)) & 0xff)
    return res


def _encode_read(sync, addr, reg):
    # Generate a uart read register message
    msg = bytearray([sync, addr, reg])
    msg.append(_calc_crc8(msg))
    return _add_serial_bits(msg)


def _encode_write(sync, addr, reg, val):
    # Generate a uart write register message
    msg = bytearray([sync, addr, reg, (val >> 24) & 0xff,
                     (val >> 16) & 0xff, (val >> 8) & 0xff, val & 0xff])
    msg.append(_calc_crc8(msg))
    return _add_serial_bits(msg)


def _decode_read(reg, data):
    # Extract a uart read response message
    if len(data) != 10:
        return None

    # Convert data into a long integer for easy manipulation
    mval = pos = 0
    for d in bytearray(data):
        mval |= d << pos
        pos += 8

    # Extract register value
    val = ((((mval >> 31) & 0xff) << 24) | (((mval >> 41) & 0xff) << 16)
           | (((mval >> 51) & 0xff) << 8) | ((mval >> 61) & 0xff))

    # Verify start/stop bits and crc
    encoded_data = _encode_write(0x05, 0xff, reg, val)
    if data != encoded_data:
        return None
    return val

class TMCUART:
    def __init__(self, config_json, mcu):
        self._config = config_json
        self._mcu = mcu
        self._oid = mcu.reserve_oid()
        self._lock = threading.RLock()
        self._last_uart_response = None
        self._last_uart_response_count = 0

        def on_response(params):
            self._last_uart_response = params['read']
            self._last_uart_response_count += 1

        mcu.serial.register_response(on_response, 'tmcuart_response', self._oid)

        if config_json['type'] == 'tmc2209':
            self._register_map = {
                'GCONF': 0x00,
                'IFCNT': 0x02,
                'SLAVECONF': 0x03,
                'IHOLD_IRUN': 0x10,
                'TPOWERDOWN': 0x11,
                'CHOPCONF': 0x6C,
                'PWMCONF': 0x70
            }
        else:
            raise NotImplementedError(config_json['type'])

    def get_configure_commands(self):
        yield f'config_tmcuart oid={self._oid} rx_pin={self._config["uart_pin"]} pull_up=0 tx_pin={self._config["tx_pin"]} bit_time=300'

    def write_register(self, addr, register_name, value):
        reg = self._register_map[register_name]
        data = _encode_write(0xf5, addr, reg | 0x80, value).hex()
        cmd = f'tmcuart_send oid={self._oid} write={data} read=0'
        r = self._mcu.reactor

        with self._lock:
            ifcnt = self.read_register(addr, 'IFCNT')
            for retry in range(5):
                count = self._last_uart_response_count
                self._mcu.serial.send(cmd)
                while self._last_uart_response_count == count:
                    r.pause(r.monotonic() + 0.1)

                after = self.read_register(addr, 'IFCNT')
                if after == (ifcnt + 1) & 0xff:
                    return

        raise Exception(f'Unable to write tmc uart register {reg}')

    def read_register(self, addr, register_name):
        with self._lock:
            reg = self._register_map[register_name]
            data = _encode_read(0xf5, addr, reg).hex()

            count = self._last_uart_response_count
            self._mcu.serial.send(f'tmcuart_send oid={self._oid} write={data} read=10')

            r = self._mcu.reactor
            while self._last_uart_response_count == count:
                r.pause(r.monotonic() + 0.1)

            return _decode_read(reg, self._last_uart_response)