## Multi-channel focuser daemon

`focusd` interfaces with and wraps a [Multi-channel Focus Controller](https://github.com/rockit-astro/focus-controller) and exposes it via Pyro.

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
  "serial_port": "/dev/focuser", # Serial FIFO for communicating with the focuser
  "serial_baud": 9600, # Serial baud rate (always 9600)
  "serial_timeout": 5, # Serial comms timeout
  "channels": 2, # Number of controllable focusers
  "idle_loop_delay": 5, # Delay in seconds between focuser status polls when idle
  "moving_loop_delay": 0.5, # Delay in seconds between focuser status polls when moving
  "move_timeout": 180 # Maximum time expected for a focus movement
}

```
## Initial Installation

The automated packaging scripts will push 5 RPM packages to the observatory package repository:

| Package                       | Description                                                                  |
|-------------------------------|------------------------------------------------------------------------------|
| rockit-focuser-server         | Contains the `focusd` server and systemd service file.                       |
| rockit-focuser-client         | Contains the `focus` commandline utility for controlling the focuser server. |
| rockit-focuser-data-clasp     | Contains the json configuration for the CLASP telescope.                     |
| rockit-focuser-data-halfmetre | Contains the json configuration for the half metre telescope.                |
| python3-rockit-focuser        | Contains the python module with shared code.                                 |

After installing packages, the systemd service should be enabled:

```
sudo systemctl enable --now focusd@<config>
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
sudo systemctl restart focusd@<config>
```

### Testing Locally

The camera server and client can be run directly from a git clone:
```
./focusd test.json
FOCUSD_CONFIG_PATH=./test.json ./focus status
```
