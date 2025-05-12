# TPS65988 configuration flasher

Copyright (c) 2024-2025 [Antmicro](https://www.antmicro.com)

## Overview

This project contains a Python script that allows for writing a configuration to a Texas Instruments [TPS65988](https://www.ti.com/product/TPS65988/part-details/TPS65988DHRSHR) USB-C Power Delivery (PD) controller located on Antmicro's [Jetson Orin Baseboard](https://github.com/antmicro/jetson-orin-baseboard).
The configuration is written to a non-volatile SPI flash, connected to the TPS65988.
Please note that in the present form the script will re-write the whole SPI flash content, so any previously programmed configurations or TPS65988 firmware patches will be erased.
Some reference configuration binaries are stored in the [tps-config-binaries](./tps-config-binaries) directory.
Those binaries are named after the Jetson Orin Baseboard revisions made available for purchasing via https://order.openhardware.antmicro.com/.

## Usage

You can use the TPS65988 flashing script with Jetson Orin Baseboard in two scenarios.
The following links will re-direct you to the relevant parts of the [documentation](https://antmicro.github.io/jetson-orin-baseboard/) provided for the [Jetson Orin Baseboard](https://github.com/antmicro/jetson-orin-baseboard) on GitHub.

* [Flashing from NVIDIA Jetson Orin SoM user space](https://antmicro.github.io/jetson-orin-baseboard/board_overview.html#tps65988-config-tool-from-jetson-orin-user-space)
* [Flashing from an external host connected to the debug console USB-C port of the Jetson Orin Baseboard](https://antmicro.github.io/jetson-orin-baseboard/board_overview.html#tps65988-config-tool-via-the-debug-console-interface-port)

Please note that while the TPS65988 flashing scripts were primarily created for the Jetson Orin Baseboard, they can be ported into other hardware designs which utilize the same USB-C PD controller.
If you plan to use the script with a different hardware platform/design, please verify the USB-C configuration you plan to use. 
The custom configuration profiles for the TPS65988 can be generated with the [TPS6598X-CONFIG](https://www.ti.com/tool/TPS6598X-CONFIG) tool provided by Texas Instruments.
Please note that writing a configuration file that will force the TPS65988 to negotiate too high or two low power supply voltage from the USB-C PD source can permanently damage the powered circuitry or make it behave unstable.  

## Licensing

The project is included under the [Apache 2.0](LICENSE) license.

