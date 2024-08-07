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

# import json
import argparse
from smbus2 import SMBus
import time
import os

def initialize_argparse():
    parser = argparse.ArgumentParser(description='Flash the PD Controller SPI flash via I2C.')
    parser.add_argument('--bus', type=int, default=0x1, help='I2C bus number')
    parser.add_argument('-vi', '--verbose_i2c', action='store_true')
    parser.add_argument('flash_bin', type=str, help='Binary image of the flash')
    return parser.parse_args()

#def split_data_into_chunks(data, chunk_size):
#    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

class TPS65988:

    def __init__ (bus, i2c_addr1=0x23, i2c_addr2=0x27, debug_i2c=True):
        self.bus       = bus
        self.i2c_addr  = i2c_addr1 # assume device 1 for 4CC
        self.i2c_addr1 = i2c_addr1
        self.i2c_addr2 = i2c_addr2
        self.debug     = debug

    def i2c_write (self, reg, data, debugname=""):
        dlength = len(data)
        command =  f'i2ctransfer -y {self.bus} w{d_length+2}@0x{self.i2c_addr:x} {int(reg, 16):#02x}'
        command += f' {int(dlength, 16):#02x} ' f' '.join(f'{byte:#02x}' for byte in data)
        if self.debug_i2c: print (f'Write to {reg:#02x} {debugname} bytes: {dlength}')
        os.system(command)

    def i2c_read (self, reg, debugname=""):
        command =  f'i2ctransfer -y {self.bus} w1@0x{self.i2c_addr:x} {int(reg, 16):#02x} r?'  # or 256 ifnot supported
        output = os.popen(command).read()
        if self.debug_i2c: print (f'Read from to {reg:#02x} {debugname} bytes: {len(output)}')
        if self.debug_i2c: print (output)
        os.system(command)
        # return parsed output

    def command_4CC (self, command, data, timeout=1):
        cmd1_reg = 0x08 # protocol constant
        data_reg = 0x09 # protocol constant
        if len(data):
            self.i2c_write (data_reg, data, "DataX")
        self.i2c_write (cmd1_reg, command, "CMD1")
        timeout += time.time()
        while time.time()<time:
            time.sleep(0.1)
            self.i2c_read(command,"CMD1")
        out_data = i2c_read (data_red, "DataX")

    def check_status (self):
        print ("Check GSC - MSB(b15) should be 1")
        i2c_read (0x27, "Global System Configuration")
        print ("Check Boot Flags - b12,13 RegionCRCErr, b7,6 RegionHeaderErr, b3 - SPI present")
        i2c_read (0x2D, "Boot Flags")
        print ("Check FW Version")
        i2c_read (0x0F, "FW Version")
        
    def SimulateDisconnect (self):
        command_4CC("DISC",[2],3)

if __name__ == "__main__":
    args = initialize_argparse()

    with open(args.flash_bin, 'rb') as file:
        data = file.read
    # as array
    # from array import array
    # data = array('B')
    # with open('data/data0', 'rb') as f:
    #    data.fromfile(f, 784000)

    bus = SMBus(args.bus)
    time.sleep(0.2)
    PDC = TPS65988 (bus, data, debug_i2c = args.verbose_i2c)
    PDC.check_status()
    PDC.SimulateDisconnect()
    

    bus.close()
    #print("The PD Controller has been flashed successfully")

