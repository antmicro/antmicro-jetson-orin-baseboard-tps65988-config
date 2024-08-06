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
import os

# Define I2C addresses for each port
i2c_address_mapping = {
    1: 0x23,
    2: 0x27
}

def initialize_argparse():
    parser = argparse.ArgumentParser(description='Flash the PD Controller via I2C.')
    parser.add_argument('--bus', type=int, default=0x1, help='I2C bus number')
    parser.add_argument('json_config', type=str, help='Path to the JSON config file')
    return parser.parse_args()

def split_data_into_chunks(data, chunk_size):
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

def flash_controller(bus, data):
    for port, i2c_address in i2c_address_mapping.items():
        for register in data["host interface registers"]["port specific registers"][port - 1]["registers"]:
            length = register["length in bytes"]
            register_value = 0

            for bitfield in register["bitfields"]:
                bitfield_value = bitfield["value (EDITABLE)"] if "value (EDITABLE)" in bitfield else bitfield["value (NON EDITABLE)"]
                bitfield_value = int(bitfield_value, 16)
                register_value |= bitfield_value << bitfield["start position"]
            
            register_bytes = [(register_value >> (i * 8)) & 0xff for i in range(length)]
            data_to_send = [length] + register_bytes
            chunks = split_data_into_chunks(data_to_send, 70)  # Using 31 to account for the address byte

            for chunk in chunks:
                chunk_length = len(chunk)
                command = f'i2ctransfer -y {args.bus} w{chunk_length+1}@0x{i2c_address:x} {int(register["address"], 16):#02x} ' + ' '.join(f'{byte:#02x}' for byte in chunk)
                print(f"Executing: {command}")
                os.system(command)

if __name__ == "__main__":
    args = initialize_argparse()

    with open(args.json_config, 'r') as file:
        data = json.load(file)

    bus = SMBus(args.bus)
    time.sleep(0.2)

    flash_controller(bus, data)

    bus.close()
    print("The PD Controller has been flashed successfully")

