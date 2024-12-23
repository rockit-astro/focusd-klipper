## Focuser daemon

`klipper_focusd` interfaces with and wraps a COTS 3D printer motherboard running the [Klipper](https://github.com/Klipper3d/klipper) microcontroller firmware.

`focus` is a commandline utility for controlling the focusers.

### Configuration

Configuration is read from json files that are installed by default to `/etc/focusd`.
A configuration file is specified when launching the server, and the `focus` frontend will search this location when launched.

The configuration options are:
```python
{
  "daemon": "localhost_test", # Run the server as this daemon. Daemon types are registered in `rockit.common.daemons`.
  "log_name": "klipper_focusd@test", # The name to use when writing messages to the observatory log.
  "control_machines": ["LocalHost"], # Machine names that are allowed to control (rather than just query) state. Machine names are registered in `rockit.common.IP`.
  "state_path": "/var/tmp/focuser.json", # Path to store the last used focus positions across restarts
  "serial_port": "/dev/focuser", # Serial FIFO for communicating with the microcontroller
  "serial_baud": 250000, # Serial baud rate (usually 250000)
  "connect_timeout": 10,
  "home_timeout": 30,
  "move_timeout": 30,
  "controller_fan": { # Optional: enable a fan when the stepper motors are active
    "pin": "gpio17", # Pin to control the fan
    "idle_timeout": 30 # Run the fan for a time after stopping
  },
  "interfaces": { # Optional: Shared bus definitions (e.g. TMC uarts, DS2484 I2C-1wire bridges)
    "tmc_uart": {
      "type": "tmc2209",
      "uart_pin": "gpio9",
      "tx_pin": "gpio8"
    }
  },
  "probes": {
    "1": {
      "label": "Thermistor 1",
      "cadence": 5,
      "type": "3950NTC",
      "pin": "gpio27"
    },
    "mcu": {
      "label": "MCU",
      "cadence": 5,
      "type": "RP2040"
    }
  },
  "steppers": {
    "1": {
      "step_pin": "gpio19",
      "dir_pin": "gpio28",
      "enable_pin": "!gpio2",
      "rotation_microsteps": 3200,
      "rotation_distance": 0.75,
      "endstop_pin": "^gpio25",
      "position_min": 0,
      "position_max": 50,
      "speed": 2.5,
      "acceleration": 0.5,
      "homing_backoff": 1,
      "tracking_cadence": 0.1,
      "tracking_commit_buffer": 0.25,
      "interface": "tmc_uart",
      "uart_address": 1,
      "uart_microsteps": 16,
      "uart_run_current": 0.8
    }
  }
}
```
## Initial Installation

The automated packaging scripts will push 3 RPM packages to the observatory package repository:

| Package                       | Description                                                                  |
|-------------------------------|------------------------------------------------------------------------------|
| rockit-focuser-server         | Contains the `klipper_focusd` server and systemd service file.               |
| rockit-focuser-client         | Contains the `focus` commandline utility for controlling the focuser server. |
| python3-rockit-focuser        | Contains the python module with shared code.                                 |

After installing packages, the systemd service should be enabled:

```
sudo systemctl enable --now klipper_focusd@<config>
```

where `config` is the name of the json file for the appropriate telescope.

Now open a port in the firewall:
```
sudo firewall-cmd --zone=public --add-port=<port>/tcp --permanent
sudo firewall-cmd --reload
```
where `port` is the port defined in `rockit.common.daemons` for the daemon specified in the config.

### Upgrading Installation

New RPM packages are automatically created and pushed to the package repository for each push to the `master` branch.
These can be upgraded locally using the standard system update procedure:
```
sudo yum clean expire-cache
sudo yum update
```

The daemon should then be restarted to use the newly installed code:
```
sudo systemctl restart klipper_focusd@<config>
```

### Testing Locally

The focuser server and client can be run directly from a git clone:
```
./klipper_focusd test.json
FOCUSD_CONFIG_PATH=./test.json ./focus status
```
