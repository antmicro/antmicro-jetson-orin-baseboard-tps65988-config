#!/usr/bin/env python3

# Copyright 2024 Antmicro
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import argparse
from smbus2 import SMBus
import time

# Define I2C addresses for each port
i2c_address_mapping = {
    1: 0x23,
    2: 0x27
}

def initialize_argparse():
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--bus', type=int, default=0x1,
                        help='I2C bus')
    parser.add_argument('json_config', type=str,
                        help='A path to a json config file')
    return parser.parse_args()

def split_data_into_chunks(data, chunk_size):
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

def flash_controller(bus, data):
    for address in i2c_address_mapping:
        for register in data["host interface registers"]["port specific registers"][address - 1]["registers"]:
            length = register["length in bytes"]
            register_value = 0
            for bitfield in register["bitfields"]:
                bitfield_value = bitfield["value (EDITABLE)"] if "value (EDITABLE)" in bitfield else bitfield["value (NON EDITABLE)"]
                bitfield_value = int(bitfield_value, 16)
    
                register_value |= bitfield_value << bitfield["start position"]
            chunks = split_data_into_chunks([length] + [(register_value >> (i* 8)) & 0xff for i in range(length)], 32)
            for chunk in chunks:
                bus.write_i2c_block_data(i2c_address_mapping[address], int(register["address"], 16), chunk)


if __name__ == "__main__":
    args = initialize_argparse()

    with open(args.json_config, 'r') as file:
        data = json.load(file)

    # Using "with" syntax throws IOError, so we need a slight delay
    bus = SMBus(args.bus)
    time.sleep(0.2)

    flash_controller(bus, data)

    bus.close()
    print("The PD Controller has been flashed successfully")
