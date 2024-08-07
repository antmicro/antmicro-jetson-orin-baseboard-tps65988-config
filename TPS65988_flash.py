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
    def __init__ (self, bus, i2c_addr1=0x23, i2c_addr2=0x27, debug_i2c=True):
        self.bus       = bus
        self.i2c_addr  = i2c_addr1 # assume device 1 for 4CC
        self.i2c_addr1 = i2c_addr1
        self.i2c_addr2 = i2c_addr2
        self.debug_i2c     = debug_i2c

    def i2c_write (self, reg, data, debugname=""):
        dlength = len(data)
        if isinstance(data,str):
            data = [ord(d) for d in data]
        command =  f'i2ctransfer -y {self.bus} w{dlength+2}@0x{self.i2c_addr:x} {reg:#02x}'
        command += f' {dlength:#02x} '+f' '.join(f'{byte:#02x}' for byte in data)
        if self.debug_i2c: print (f'Write to {reg:#02x} {debugname} bytes: {dlength}')
        os.system(command)
        #print (command)

    def i2c_read (self, reg, dlen=255, debugname=""):
        dlen +=1 # accomodate for data length header
        command =  f'i2ctransfer -y {self.bus} w1@0x{self.i2c_addr:x} {reg:#02x} r{dlen}'  # or 256 ifnot supported
        output = os.popen(command).read()
        output = output.rstrip("\r\n")
        output = output.rpartition("\r")[2]
        output = output.split()
        output = [int(o,0) for o in output]
        if self.debug_i2c: print (f'Read from to {reg:#02x} {debugname} bytes: {len(output)-1}/{output[0]}')
        if self.debug_i2c: print (" ".join([hex(o) for o in output]))
        return output
        # return parsed output

    def command_4CC (self, command, data, outdatalen, timeout=1):
        cmd1_reg = 0x08 # protocol constant
        data_reg = 0x09 # protocol constant
        if len(data):
            self.i2c_write (data_reg, data, "DataX")
        self.i2c_write (cmd1_reg, command, "CMD1")
        timeout += time.time()
        holddebug = self.debug_i2c
        self.debug_i2c = False
        while time.time() < timeout:
            time.sleep(0.1)
            response = self.i2c_read (cmd1_reg, 4,"CMD1")
            if response == [4, 0x21, 0x43, 0x4D, 0x44]:
                print ("4CC command rejected")
                self.debug_i2c = holddebug
                return None
            elif response == [4, 0, 0, 0, 0]:
                print ("4CC ack")
                self.debug_i2c = holddebug
                return self.i2c_read (data_reg, outdatalen, "DataX")
        print ("4CC timeout")
        self.debug_i2c = holddebug
        return None

    def check_status (self):
        print ("Check GSC - MSB(b15) should be 1")
        self.i2c_read (0x27, 14, "Global System Configuration")
        print ("Check Boot Flags - b12,13 RegionCRCErr, b7,6 RegionHeaderErr, b3 - SPI present")
        self.i2c_read (0x2D, 12, "Boot Flags")
        print ("Check FW Version")
        self.i2c_read (0x0F, 4, "FW Version")
        
    def SimulateDisconnect (self):
        print ('testing 4CC')
        self.command_4CC("DISC",[2],1,3)

    def Resume (self):
        print ('testing 4CC')
        self.command_4CC("Gaid",[2],1,3)

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
    print ("> connecting")
    PDC = TPS65988 (args.bus, debug_i2c = args.verbose_i2c)
    PDC.check_status()
    PDC.Resume()
    

    bus.close()
    #print("The PD Controller has been flashed successfully")

