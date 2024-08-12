# TPS65988-config

Copyright (c) 2024 [Antmicro](https://www.antmicro.com)


## Overview

TPS65988-config repository contains python script which allows programming TPS65988 configuration for [Jetson Orin Baseboard](https://github.com/antmicro/jetson-orin-baseboard). The configuration is written to a non-volatile SPI flash, connected to TPS65988.\
*Please note that the entire SPI flash is rewritten, so any previously programmed configurations or TPS65988 firmware patches will be erased*

## Operation
1. Download files `TPS65988_flash.py` and `JOBrev1_*_*.bin` into one directory.
2. Install [PIP](https://pip.pypa.io/en/stable/installation/#get-pip-py)
3. Install `smbus2` with PIP
```
pip3 install smbus2
```
4. Run python script to flash configuration
```
python3 TPS65988_flash.py --erase --write <image file>
```

## License
The project is included under the [Apache 2.0](/LICENSE) license.

