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
import smbus2
import time
import os
import struct

def initialize_argparse():
    parser = argparse.ArgumentParser(description='Flash the PD Controller SPI flash via I2C.')
    parser.add_argument('--bus', type=int, default=0x1, help='I2C bus number')
    parser.add_argument('--dump', type=str, help='Dump flash content into a file')
    parser.add_argument('--erase', action='store_true', help='Erase flash')
    parser.add_argument('--write', type=str, help='Write flash with the binary image')
    parser.add_argument('--truncate', type=int, help='Limit R/W operation to TRUNCATE Kbytes')
    parser.add_argument('-vi', '--verbose_i2c', action='store_true',help='print I2C transactions')
    parser.add_argument('-v4', '--verbose_4cc', action='store_true',help='print 4CC transactions')
    return parser.parse_args()

def int32_to_bytes (x):
    return list(struct.Struct('<I').pack (x & 0XFFFFFFFF))

def lsbblock2hex (block):
    return " ".join(["{:02x}".format(byte) for byte in block[::-1]])

def block2hex (block):
    return " ".join(["{:02x}".format(byte) for byte in block])


class TPS65988:
    def __init__ (self, bus_no, i2c_addr1=0x23, i2c_addr2=0x27, debug_i2c=True, debug_4cc=False):
        self.bus_no    = bus_no
        self.bus       = smbus2.SMBus(bus_no)
        self.i2c_addr  = i2c_addr1 # assume device 1 for 4CC
        self.i2c_addr1 = i2c_addr1
        self.i2c_addr2 = i2c_addr2
        self.debug_i2c     = debug_i2c
        self.debug_4cc     = debug_4cc

    def i2c_write (self, reg, data, debugname=""):
        dlength = len(data)
        if isinstance(data,str):
            data = [ord(d) for d in data]
        if self.debug_i2c: print (f'Write to {reg:#02x} {debugname} bytes: {dlength}')
        msg = smbus2.i2c_msg.write(self.i2c_addr, [reg&0xFF, dlength&0xFF] + list(data))
        self.bus.i2c_rdwr(msg)

    def i2c_read (self, reg, dlen=255, debugname=""):
        dlen +=1 # accomodate for data length header
        msgw = smbus2.i2c_msg.write(self.i2c_addr,[reg])
        msg = smbus2.i2c_msg.read(self.i2c_addr,dlen)
        self.bus.i2c_rdwr(msgw,msg)
        output = list(msg)
        if self.debug_i2c: print (f'Read from to {reg:#02x} {debugname} bytes: {len(output)-1}/{output[0]}')
        if self.debug_i2c: print (" ".join(["{:02x}".format(o) for o in output]))
        return output

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
        print ("Check GSC - (MSB.b15 - flash access locked)")
        out = self.i2c_read (0x27, 14, "Global System Configuration")
        print (lsbblock2hex(out))
        print ("Check Boot Flags - (b12,13 RegionCRCErr) (b7,6 RegionHeaderErr) (b3 - SPI present)")
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

    def Print4CCRCode (self, code, prefix=""):
        res = "OK" if code == [0x40,00] else "Returned code: "+block2hex(code)
        print (res)

if __name__ == "__main__":
    args = initialize_argparse()
    time.sleep(0.2)
    print ("Connecting to the TPS65988 chip")
    PDC = TPS65988 (args.bus, debug_i2c = args.verbose_i2c, debug_4cc = args.verbose_4cc)
    PDC.check_status()
    #PDC.Resume4CC()
    
    if args.dump:
        memtop = 1024*1024
        if args.truncate: memtop = min(memtop, args.truncate*1024)
        print ("Performing {int(memtop)/1024}KB memory dump")
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
        memtop = 1024*1024
        print ("Performing {int(memtop)/1024}KB memory ERASE")
        sectors = int (memtop / (4*1024))
        addr = 0 
        data = PDC.FlashErase4CC(addr,int(sectors/2))
        PDC.Print4CCRCode (data,f"Erase {hex(addr)}")
        addr = int(memtop/2)
        data = PDC.FlashErase4CC(addr,int(sectors/2))
        PDC.Print4CCRCode (data,f"Erase {hex(addr)}")

    if args.write:
        with open(args.write, 'rb') as file:
            data = file.read()
        memtop = 1024*1024
        if args.truncate: memtop = min(memtop, args.truncate*1024)
        print ("Performing {int(memtop)/1024}KB memory WRITE")
        memidx = 0
        memdump = []
        success = True
        while memidx<memtop:
            if memidx % 0x1000 ==0: print (f'WRITE Flash {hex(memidx)}', end="\r")
            code = PDC.FlashWrite4CC (memidx, data[memidx:memidx+64])
            if not code == [0x40,0]:
                DC.Print4CCRCode (data,f"Write {hex(memidx)}")
                success = False
            memidx+=64
        print (f"Write completed {memtop} bytes written")
        if success:
            print("The PD Controller has been flashed successfully")
        else:
            print("There were some 4CC error codes")
    PDC.bus.close()

