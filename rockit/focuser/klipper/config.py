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

"""Helper function to validate and parse the json config file"""

import json
from rockit.common import daemons, IP, validation

CONFIG_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['daemon', 'log_name', 'control_machines',
                 'loop_delay', 'move_speed', 'move_timeout', 'max_position', 'homing_coarse_step',
                 'homing_coarse_speed', 'homing_fine_step', 'homing_fine_speed', 'mcu'],
    'properties': {
        'daemon': {
            'type': 'string',
            'daemon_name': True
        },
        'log_name': {
            'type': 'string',
        },
        'control_machines': {
            'type': 'array',
            'items': {
                'type': 'string',
                'machine_name': True
            }
        },
        'loop_delay': {
            'type': 'number',
            'min': 0
        },
        'move_speed': {
            'type': 'number',
            'min': 0
        },
        'move_timeout': {
            'type': 'number',
            'min': 0
        },
        'max_position': {
            'type': 'number',
            'min': 0
        },
        'homing_coarse_step': {
            'type': 'number',
            'min': 0
        },
        'homing_coarse_speed': {
            'type': 'number',
            'min': 0
        },
        'homing_fine_step': {
            'type': 'number',
            'min': 0
        },
        'homing_fine_speed': {
            'type': 'number',
            'min': 0
        },
        'mcu': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['serial_port', 'serial_baud', 'serial_timeout', 'tmc_uarts', 'steppers'],
            'properties': {
                'serial_port': {
                    'type': 'string',
                },
                'serial_baud': {
                    'type': 'integer',
                    'min': 250000,
                    'max': 250000
                },
                'serial_timeout': {
                    'type': 'number',
                    'min': 0
                },
                'tmc_uarts': {
                    'type': 'object',
                    'additionalProperties': {
                        'type': 'object',
                        'additionalProperties': False,
                        'required': ['type', 'uart_pin', 'tx_pin'],
                        'properties': {
                            'type': {'type': 'string', 'enum': ['tmc2209']},
                            'uart_pin': {'type': 'string'},
                            'tx_pin': {'type': 'string'},
                        }
                    }
                },
                'steppers': {
                    'type': 'object',
                    'additionalProperties': {
                        'type': 'object',
                        'additionalProperties': False,
                        # endstop_pin and tmc_uart are optional
                        'required': ['step_pin', 'dir_pin', 'enable_pin', 'rotation_microsteps', 'rotation_distance',
                                     'position_min', 'position_max', 'speed', 'acceleration', 'homing_backoff'],
                        'properties': {
                            'step_pin': {'type': 'string'},
                            'dir_pin': {'type': 'string'},
                            'enable_pin': {'type': 'string'},
                            'endstop_pin': {'type': 'string'},
                            'rotation_microsteps': {'type': 'integer'},
                            'rotation_distance': {'type': 'number'},
                            'position_min': {'type': 'number'},
                            'position_max': {'type': 'number'},
                            'speed': {'type': 'number'},
                            'acceleration': {'type': 'number'},
                            'homing_backoff': {'type': 'number'},
                            'tmc_uart': {
                                'type': 'object',
                                'additionalProperties': False,
                                'required': ['uart', 'address', 'run_current'],
                                'properties': {
                                    "uart": {'type': 'string'},
                                    "address": {'type': 'integer', 'enum': [0, 1, 2, 3]},
                                    'microsteps': {'type': 'integer', 'enum': [1, 2, 4, 8, 16, 32, 64, 128, 256]},
                                    "run_current": {'type': 'number', 'minimum': 0}
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


class Config:
    """Daemon configuration parsed from a json file"""
    def __init__(self, config_filename):
        # Will throw on file not found or invalid json
        with open(config_filename, 'r', encoding='utf-8') as config_file:
            config_json = json.load(config_file)

        # Will throw on schema violations
        validation.validate_config(config_json, CONFIG_SCHEMA, {
            'daemon_name': validation.daemon_name_validator,
            'machine_name': validation.machine_name_validator,
        })

        self.daemon = getattr(daemons, config_json['daemon'])
        self.log_name = config_json['log_name']
        self.control_ips = [getattr(IP, machine) for machine in config_json['control_machines']]

        self.loop_delay = float(config_json['loop_delay'])
        self.move_speed = float(config_json['move_speed'])
        self.move_timeout = float(config_json['move_timeout'])
        self.max_position = float(config_json['max_position'])

        self.homing_coarse_step = float(config_json['homing_coarse_step'])
        self.homing_coarse_speed = float(config_json['homing_coarse_speed'])
        self.homing_fine_step = float(config_json['homing_fine_step'])
        self.homing_fine_speed = float(config_json['homing_fine_speed'])

        self.mcu = config_json['mcu']
