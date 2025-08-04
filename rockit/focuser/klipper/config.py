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
from rockit.klippermcu.schema import gpio_schema, interfaces_schema, stepper_schema

CONFIG_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['daemon', 'log_name', 'control_machines', 'state_path', 'serial_port', 'serial_baud',
                 'connect_timeout', 'move_timeout', 'home_timeout', 'steppers'],
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
        'state_path': {
            'type': 'string',
        },
        'serial_port': {
            'type': 'string',
        },
        'serial_baud': {
            'type': 'integer',
            'minimum': 250000,
            'maximum': 250000
        },
        'connect_timeout': {
            'type': 'number',
            'minimum': 0
        },
        'move_timeout': {
            'type': 'number',
            'minimum': 0
        },
        'home_timeout': {
            'type': 'number',
            'minimum': 0
        },
        'controller_fan': gpio_schema(),
        'interfaces': interfaces_schema(tmc2209=True, ds2484=True),
        'probes': {
            'type': 'object',
            'additionalProperties': {
                'type': 'object',
                'oneOf': [
                    {
                        'properties': {
                            'label': {'type': 'string'},
                            'cadence': {'type': 'number'},
                            'type': {'enum': ['3950NTC']},
                            'pin': {'type': 'string'}
                        },
                        'required': ['label', 'cadence', 'type', 'pin'],
                        'additionalProperties': False
                    },
                    {
                        'properties': {
                            'label': {'type': 'string'},
                            'cadence': {'type': 'number'},
                            'type': {'enum': ['DS18B20']},
                            'address': {'type': 'string'},
                            'interface': {'type': 'string'}
                        },
                        'required': ['label', 'cadence', 'type', 'interface'],
                        'additionalProperties': False
                    },
                    {
                        'properties': {
                            'label': {'type': 'string'},
                            'cadence': {'type': 'number'},
                            'type': {'enum': ['RP2040']}
                        },
                        'required': ['label', 'cadence', 'type'],
                        'additionalProperties': False
                    }
                ]
            }
        },
        'steppers': {
            'type': 'object',
            'additionalProperties': stepper_schema()
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
        self.state_path = config_json['state_path']
        self.serial_port = config_json['serial_port']
        self.serial_baud = int(config_json['serial_baud'])
        self.connect_timeout = float(config_json['connect_timeout'])
        self.move_timeout = float(config_json['move_timeout'])
        self.home_timeout = float(config_json['home_timeout'])
        self.controller_fan = config_json.get('controller_fan', None)
        self.interfaces = config_json.get('interfaces', {})
        self.probes = config_json.get('probes', {})
        self.steppers = config_json['steppers']
