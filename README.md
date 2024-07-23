# TPS65988-config

Copyright (c) 2024 [Antmicro](https://www.antmicro.com)


## Overview

TPS65988-config repository contains python script which allows basic TPS65988 configuration for [Jetson Orin Baseboard](https://github.com/antmicro/jetson-orin-baseboard)

## Operation
1. Download files `TPS65988_config.py` and `orin2.json` into one directory.
2. Install [PIP](https://pip.pypa.io/en/stable/installation/#get-pip-py)
3. Install `smbus2` with PIP
```
pip3 install smbus2
```
4. Change the permissions of the `/dev/i2c-1` device file on system with
```
sudo chmod 666 /dev/i2c-1
```
5. Run python script to flash configuration
```
python3 TPS65988_config.py
```


## Project structure
* `/.` -  contains the flashing script, config file, the licence and this readme file

## License
The project is included under the [Apache 2.0](/LICENSE) license.

