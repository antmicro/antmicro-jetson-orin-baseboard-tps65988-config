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
import struct

def initialize_argparse():
    parser = argparse.ArgumentParser(description='Flash the PD Controller SPI flash via I2C.')
    parser.add_argument('--bus', type=int, default=0x1, help='I2C bus number')
    parser.add_argument('--dump', type=str, help='Dump flash content into a file')
    parser.add_argument('--erase', action='store_true', help='Erase flash')
    parser.add_argument('--write', type=str, help='Write flash with the binary image')
    parser.add_argument('--truncate', type=int, help='Limit R/W operation to TRUNCATE bytes')
    parser.add_argument('-vi', '--verbose_i2c', action='store_true',help='print I2C transactions')
    parser.add_argument('-v4', '--verbose_4cc', action='store_true',help='print 4CC transactions')
    return parser.parse_args()

#def split_data_into_chunks(data, chunk_size):
#    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

def int32_to_bytes (x):
    return list(struct.Struct('<I').pack (x & 0XFFFFFFFF))

def lsbblock2hex (block):
    return " ".join(["{:02x}".format(byte) for byte in block[::-1]])

def block2hex (block):
    return " ".join(["{:02x}".format(byte) for byte in block])


class TPS65988:
    def __init__ (self, bus, i2c_addr1=0x23, i2c_addr2=0x27, debug_i2c=True, debug_4cc=False):
        self.bus       = bus
        self.i2c_addr  = i2c_addr1 # assume device 1 for 4CC
        self.i2c_addr1 = i2c_addr1
        self.i2c_addr2 = i2c_addr2
        self.debug_i2c     = debug_i2c
        self.debug_4cc     = debug_4cc

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
        if self.debug_i2c: print (" ".join(["{:02x}".format(o) for o in output]))
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
            response = self.i2c_read (cmd1_reg, 4,"CMD1")
            if response == [4, 0x21, 0x43, 0x4D, 0x44]:
                print ("4CC command rejected")
                self.debug_i2c = holddebug
                return None
            elif response == [4, 0, 0, 0, 0]:
                if self.debug_4cc: print ("4CC Ack")
                self.debug_i2c = holddebug
                return self.i2c_read (data_reg, outdatalen, "DataX")
            #time.sleep(0.001)
        print ("4CC Timeout")
        self.debug_i2c = holddebug
        return None

    def check_status (self):
        print ("Check GSC - MSB(b15) should be 1")
        out = self.i2c_read (0x27, 14, "Global System Configuration")
        print (lsbblock2hex(out))
        print ("Check Boot Flags - b12,13 RegionCRCErr, b7,6 RegionHeaderErr, b3 - SPI present")
        out = self.i2c_read (0x2D, 12, "Boot Flags")
        print (lsbblock2hex(out))
        print ("Check FW Version")
        out = self.i2c_read (0x0F, 4, "FW Version")
        print (lsbblock2hex(out))
        
    def SimulateDisconnect4CC (self):
        if self.debug_4cc: (f'4CC: simulate disconnect')
        self.command_4CC("DISC",[2],1,3)

    def Resume4CC (self):
        if self.debug_4cc: (f'4CC: resume operation')
        self.command_4CC("Gaid",[2],1,3)

    def FlashRead4CC (self, addr):
        if self.debug_4cc: (f'Read from Flash {hex(addr)}')
        dlen = 16
        data = self.command_4CC("FLrd",int32_to_bytes(addr),dlen)
        return bytearray(data[-dlen:])

    def FlashErase4CC (self, addr,sectors):
        if self.debug_4cc: print(f'Erase Flash from {hex(addr)} -> {sectors}*4K')
        code = self.command_4CC("FLem",int32_to_bytes(addr)+[sectors&0xFF],1,10)
        return code

    def FlashWrite4CC (self, addr, data):
        if self.debug_4cc: (f'Write Flash: {len(data)} bytes at {hex(addr)}')
        codec = self.command_4CC("FLad",int32_to_bytes(addr),1)
        coded = self.command_4CC("FLwd",data,1)
        return coded

if __name__ == "__main__":
    args = initialize_argparse()
    bus = SMBus(args.bus)
    time.sleep(0.2)
    print ("Connecting to the TPS65988 chip")
    PDC = TPS65988 (args.bus, debug_i2c = args.verbose_i2c, debug_4cc = args.verbose_4cc)
    PDC.check_status()
    #PDC.Resume4CC()
    
    if args.dump:
        print ("Performing 1MB memory dump")
        memtop = 1024*1024
        if args.truncate: memtop = min(memtop, args.truncate)
        memidx = 0
        memdump = []
        while memidx<memtop:
            if memidx % 0x1000 ==0: print (f'Read from Flash {hex(memidx)}', end="\r")
            memdump.append(PDC.FlashRead4CC(memidx))
            memidx+=16
        print (f"{memtop} bytes read. Saving to {args.dump}")
        with open(args.dump, "wb") as file:
            for block in memdump:
                file.write(block)
        with open(args.dump+".txt", "w") as file:
            for block in memdump:
                block = block2hex(block) + "\n"
                file.write(block)
    if args.erase:
        print ("Performing 1MB flash memory ERASE")
        memtop = 1024*1024
        sectors = int (1024 / 4)
        data = PDC.FlashErase4CC(0,int(sectors/2))
        data = PDC.FlashErase4CC(int(memtop/2),int(sectors/2))
        print (f"Returned code: {block2hex(data)}")
    if args.write:
        with open(args.write, 'rb') as file:
            data = file.read()
        print ("Performing 1MB memory WRITE")
        memtop = 1024*1024
        if args.truncate: memtop = min(memtop, args.truncate)
        memidx = 0
        memdump = []
        while memidx<memtop:
            # if memidx % 0x1000 ==0: print (f'WRITE Flash {hex(memidx)}', end="\r")
            code = PDC.FlashWrite4CC (memidx, data[memidx:memidx+64])
            memidx+=64
            print (f"Write at {hex(memidx)}, returned code: {block2hex(code)}")
        print (f"Write completed {memtop} bytes written")
    bus.close()
    #print("The PD Controller has been flashed successfully")

