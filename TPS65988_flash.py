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
import struct
import register_definitions
import ft230x


def initialize_argparse():
    parser = argparse.ArgumentParser(description="Flash the PD Controller SPI flash via I2C.")
    parser.add_argument("--bus", type=int, default=0x1, help="I2C bus number")
    parser.add_argument("--dump", type=str, help="Dump flash content into a file")
    parser.add_argument("--erase", action="store_true", help="Erase flash")
    parser.add_argument("--write", type=str, help="Write flash with the binary image")
    parser.add_argument("--truncate", type=int, help="Limit R/W operation to TRUNCATE Kbytes")
    parser.add_argument("--force", action="store_true", help="Force write flash with the binary image")
    parser.add_argument("--ft230x", action="store_true", help="Use FT230X for flashing instead of internal I2C Bus")
    parser.add_argument("--debug_flash_config", action="store_true", help="Debug attempt of flash configuration loading")
    parser.add_argument("-vi", "--verbose_i2c", action="store_true", help="print I2C transactions")
    parser.add_argument("-v4", "--verbose_4cc", action="store_true", help="print 4CC transactions")
    return parser.parse_args()


def int32_to_bytes(x):
    return list(struct.Struct("<I").pack(x & 0xFFFFFFFF))


def lsbblock2hex(block):
    return " ".join(["{:02x}".format(byte) for byte in block[::-1]])


def block2hex(block):
    return " ".join(["{:02x}".format(byte) for byte in block])


def is_bit_set(byte, bit_index):
    return (byte & (1 << bit_index)) != 0


class TPS65988:
    def __init__(self, bus_no, i2c_addr1 = 0x23, i2c_addr2 = 0x27, use_ft230x = False, debug_i2c = True, debug_4cc = False):
        self.bus_no = bus_no
        self.use_ft230x = use_ft230x
        self.i2c_addr = i2c_addr1  # assume device 1 for 4CC
        self.i2c_addr1 = i2c_addr1
        self.i2c_addr2 = i2c_addr2
        self.debug_i2c = debug_i2c
        self.debug_4cc = debug_4cc   
        
        if not use_ft230x:
            try:
                # Try to initialize using smbus2            
                self.bus = smbus2.SMBus(bus_no)
            except Exception:
                print("Claiming Internal I2C bus failed")
                exit()
        else:
            try:
                # Try to connect to FT230X   
                self.bus = ft230x.cbusBitBang(ftdi_addr = "ftdi://ftdi/1", i2c_debug = self.debug_i2c)
            except Exception as e:               
                print(e)
                print("Connecting to the FT230X failed")
                exit()
            
               
    def i2c_write(self, reg, data, debugname = ""):
        dlength = len(data)
        if isinstance(data, str):
            data = [ord(d) for d in data]
        if self.debug_i2c:
            print(f"Write to {reg:#02x} {debugname} bytes: {dlength}")

        if self.use_ft230x:
            msg = self.bus.write_block_to_i2c(self.i2c_addr,reg,[dlength & 0xFF]+ list(data))
        else:    
            msg = smbus2.i2c_msg.write(self.i2c_addr, [reg & 0xFF, dlength & 0xFF] + list(data))
            self.bus.i2c_rdwr(msg)

    def i2c_read(self, reg, dlen = 255, debugname = ""):
        dlen += 1  # accomodate for data length header

        if self.use_ft230x:
            msg = self.bus.read_block_from_i2c(self.i2c_addr,reg,dlen)
        else:    
            msgw = smbus2.i2c_msg.write(self.i2c_addr, [reg])
            msg = smbus2.i2c_msg.read(self.i2c_addr, dlen)
            self.bus.i2c_rdwr(msgw, msg)
            
        if msg != -1:
            output = list(msg)
        else:
            raise ValueError("Device unresponsive")
        if self.debug_i2c:
            print(f"Read from to {reg:#02x} {debugname} bytes: {len(output) - 1} / {output[0]}")
        if self.debug_i2c:
            print(" ".join(["{:02x}".format(o) for o in output]))
        return output

    def command_4CC(self, command, data, outdatalen, timeout = 1):
        if len(data):
            self.i2c_write(register_definitions.data1.address, data, register_definitions.data1.name)
        self.i2c_write(register_definitions.command1.address, command, register_definitions.command1.name)
        timeout += time.time()
        holddebug = self.debug_i2c
        self.debug_i2c = False
        successfull_reponse = [4, 0, 0, 0, 0]
        unrecognized_command_response = [4, 0x21, 0x43, 0x4D, 0x44]
        while time.time() < timeout:
            response = self.i2c_read(register_definitions.command1.address, register_definitions.command1.size, register_definitions.command1.name)
            if response == unrecognized_command_response:
                print("4CC command rejected")
                self.debug_i2c = holddebug
                return None
            elif response == successfull_reponse:
                if self.debug_4cc:
                    print("4CC Ack")
                self.debug_i2c = holddebug
                return self.i2c_read(register_definitions.data1.address, outdatalen, register_definitions.data1.name)
        if outdatalen > 0:
            print("4CC Timeout")
        self.debug_i2c = holddebug
        return None

    def check_status(self):
        print("Check GSC - (MSB.b15 - flash access locked)")
        out = self.i2c_read(register_definitions.global_system_configuration.address, register_definitions.global_system_configuration.size, register_definitions.global_system_configuration.name)
        print(lsbblock2hex(out))
        print("Check Boot Flags - (b12,13 RegionCRCErr) (b7,6 RegionHeaderErr) (b3 - SPI present)")
        out = self.i2c_read(register_definitions.boot_flags.address, register_definitions.boot_flags.size, register_definitions.boot_flags.name)
        print(lsbblock2hex(out))
        print("Check FW Version")
        out = self.i2c_read(register_definitions.firmware_version.address, register_definitions.firmware_version.size, register_definitions.firmware_version.name)
        print(lsbblock2hex(out))

    def SimulateDisconnect4CC(self):
        if self.debug_4cc:
            (f"4CC: simulate disconnect")
        self.command_4CC("DISC", [2], 1, 3)

    def SimulateDisconnect4CC(self):
        if self.debug_4cc:
            (f"4CC: simulate disconnect")
        self.command_4CC("DISC", [2], 1, 3)

    def Resume4CC(self):
        if self.debug_4cc:
            (f"4CC: resume operation")
        self.command_4CC("Gaid", [], 0, 0)

    def ColdReset4CC(self):
        if self.debug_4cc:
            (f"4CC: cold reset")
        self.command_4CC("GAID", [], 0, 0)

    def FlashRead4CC(self, addr):
        if self.debug_4cc:
            (f"Read from Flash {hex(addr)}")
        dlen = 16
        data = self.command_4CC("FLrd", int32_to_bytes(addr), dlen)
        return bytearray(data[-dlen:])

    def FlashErase4CC(self, addr, sectors):
        if self.debug_4cc:
            print(f"Erase Flash from {hex(addr)} -> {sectors}*4K")
        code = self.command_4CC("FLem", int32_to_bytes(addr) + [sectors & 0xFF], 1, 10)
        return code

    def FlashWrite4CC(self, addr, data):
        if self.debug_4cc:
            (f"Write Flash: {len(data)} bytes at {hex(addr)}")
        codec = self.command_4CC("FLad", int32_to_bytes(addr), 1)
        coded = self.command_4CC("FLwd", data, 1)
        return coded

    def Print4CCRCode(self, code, prefix = ""):
        success_code = [0x40, 00]
        res = "OK" if code == success_code else "Returned code: " + block2hex(code)
        
        if len(res) > 100:
            with open("4CCRCode.txt", "a") as file:
                file.write(res)
            print("4CCRCode is longer than 100 characters and has been dumped into '4CCRCode.txt'.")
        else:
            print(res)

    def IsConfigured(self, debug_mode_enabled = False):
        boot_flags_register_read_byte_count = 2
        boot_flags_register_value = self.i2c_read(register_definitions.boot_flags.address, boot_flags_register_read_byte_count)
        config_bytes = boot_flags_register_value[1:]

        spi_flash_present = is_bit_set(config_bytes[0], 3)

        region0_read_attempt = is_bit_set(config_bytes[0], 4)
        region1_read_attempt = is_bit_set(config_bytes[0], 5)

        region0_header_invalid = is_bit_set(config_bytes[0], 6)
        region1_header_invalid = is_bit_set(config_bytes[0], 7)

        region0_read_invalid = is_bit_set(config_bytes[1], 0)
        region1_read_invalid = is_bit_set(config_bytes[1], 1)

        patch_download_error = is_bit_set(config_bytes[1], 2)

        region0_crc_fail = is_bit_set(config_bytes[1], 4)
        region1_crc_fail = is_bit_set(config_bytes[1], 5)

        if debug_mode_enabled:
            print(f"SPI flash present: {spi_flash_present}")

            print(f"Region 0 read attempt: {region0_read_attempt}")
            print(f"Region 0 header invalid: {region0_header_invalid}")
            print(f"Region 0 CRC fail: {region0_crc_fail}")

            print(f"Region 1 read attempt: {region1_read_attempt}")
            print(f"Region 1 header invalid: {region1_header_invalid}")
            print(f"Region 1 CRC fail: {region1_crc_fail}")

            print(f"Patch download occurred: {patch_download_error}")

        if not spi_flash_present:
            return False

        if region0_read_attempt and (region0_header_invalid or region0_read_invalid or region0_crc_fail):
            return False

        if region1_read_attempt and (region1_header_invalid or region1_read_invalid or region1_crc_fail):
            return False

        return not patch_download_error


if __name__ == "__main__":
    args = initialize_argparse()
    time.sleep(0.2)
    print("Connecting to the TPS65988 chip...")
    PDC = TPS65988(args.bus, use_ft230x = args.ft230x ,debug_i2c = args.verbose_i2c, debug_4cc = args.verbose_4cc)
    PDC.check_status()
    # PDC.Resume4CC()

    if args.debug_flash_config:
        postfix_when_invalid = (" not", "")[PDC.IsConfigured(args.debug_flash_config)]
        print(f"TPS65988 flash configuration is{postfix_when_invalid} valid.")

    if args.dump:
        memtop = 1024 * 1024
        if args.truncate:
            memtop = min(memtop, args.truncate * 1024)
        print(f"Performing {int(memtop / 1024)}KB memory dump")
        memidx = 0
        memdump = []
        while memidx < memtop:
            if memidx % 0x1000 == 0:
                percent = int(memidx * 100 / memtop)
                print(f"Read from Flash {percent:02d}% - {hex(memidx)}", end="\r")
            memdump.append(PDC.FlashRead4CC(memidx))
            memidx += 16
        print(f"{memtop} bytes read. Saving to {args.dump}")
        with open(args.dump, "wb") as file:
            for block in memdump:
                file.write(block)
        with open(args.dump + ".txt", "w") as file:
            for block in memdump:
                block = block2hex(block) + "\n"
                file.write(block)

    if args.erase:
        memtop = 1024 * 1024
        print(f"Performing {int(memtop / 1024)}KB memory ERASE")
        sectors = int(memtop / (4 * 1024))
        addr = 0
        data = PDC.FlashErase4CC(addr, int(sectors / 2))
        PDC.Print4CCRCode(data, f"Erase {hex(addr)}")
        addr = int(memtop / 2)
        data = PDC.FlashErase4CC(addr, int(sectors / 2))
        PDC.Print4CCRCode(data, f"Erase {hex(addr)}")
        print("Performing cold reset")
        code = PDC.ColdReset4CC()
        time.sleep(5)

    if args.write:
        if not args.force and PDC.IsConfigured():
            print("TPS65988 is already configured. Aborting...")
        else:
            with open(args.write, "rb") as file:
                data = file.read()
            data = list(data) + [0] * (len(data) % 64)  # padding
            memtop = min(1024 * 1024, len(data))
            if args.truncate:
                memtop = min(memtop, args.truncate * 1024)
            print(f"Writing {int(memtop / 1024)}KB to flash memory...")
            memidx = 0
            memdump = []
            success = True
            flash_write_successfull_code = [0x40, 0]

            while memidx < memtop:
                if memidx % 0x100 == 0:
                    percent = int(memidx * 100 / memtop)
                    print(f"Writing flash {percent:02d}% - {hex(memidx)}", end="\r")                   
                if len([x for x in data[memidx : memidx + 64] if x<0xFF]):
                    code = PDC.FlashWrite4CC(memidx, data[memidx : memidx + 64])
                if not code == flash_write_successfull_code:
                    PDC.Print4CCRCode(data, f"Write {hex(memidx)}")
                    success = False
                memidx += 64
            print(f"Write completed {memtop} bytes written")
            if success:
                print("The PD Controller has been flashed successfully")
            else:
                print("Flashing PD Controller failed.")
            print("Performing cold reset")
            code = PDC.ColdReset4CC()

    PDC.bus.close()