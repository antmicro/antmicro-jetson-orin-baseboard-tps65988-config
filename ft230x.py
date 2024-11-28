import time
from pyftdi.ftdi import Ftdi
from pyftdi.eeprom import FtdiEeprom


def lsbblock2hex(block):
    return " ".join(["{:02x}".format(byte) for byte in block[::-1]])


class cbusBitBang:
    def __init__(self, ftdi_addr = "ftdi://ftdi/1",pin_number_sda=0x0, pin_number_scl=0x3,pin_number_switch=0x1, i2c_debug = False):
       
        self.cbus_mask = 0xF & (0x1 << pin_number_sda | 0x1 << pin_number_scl | 0x1 << pin_number_switch)

        self.cbus_sda_mask = 0xF & (0x1 << pin_number_sda)
        self.cbus_scl_mask = 0xF & (0x1 << pin_number_scl)
        self.cbus_switch_mask = 0xF & (0x1 << pin_number_switch)

        self.i2c_debug = i2c_debug
        # Set curr cbus configuration to all HIGH_Z
        self.curr_cbus_register = 0b0000   

        # Create and open an instance of FTDI
        self.ftdi = Ftdi()

        try:
            self.ftdi.open_from_url(ftdi_addr)
        except Exception as e:           
            raise FileNotFoundError(e)
            

        print("Connected to a FTDI device")

        # Validate CBUS feature with the current device
        assert self.ftdi.has_cbus, "This FTDI device has no CBUS"

        # Validate CBUS EEPROM configuration with the current device
        self.eeprom = FtdiEeprom()
        self.eeprom.connect(self.ftdi)
        self.eeprom.set_property("cbus_slow_slew", "FAST") #SDA

        # If curent eeprom does not have cbus pins conf as GPIO, modyfiy it
        if not self.eeprom.cbus_mask & self.cbus_mask == self.cbus_mask:

            self.eeprom.set_property("cbus_slow_slew", "FAST") #SDA
            self.eeprom.set_property("cbus_func_0", "GPIO") #SDA
            self.eeprom.set_property("cbus_func_1", "GPIO") #Enable signal
            self.eeprom.set_property("cbus_func_3", "GPIO") #SCL
            print("Reconfiguring the CBUS pins as GPIO")
            self.eeprom.commit(dry_run=False)            
            self.eeprom.reset_device()
            #self.eeprom.dump_config()

        self.drive_switch_low()
           
    def __exit__(self):
        self.close()
        
    def read_cbus_pin(self, pin_mask):
        #Prepare new mask by placing 0 in the register at the offset of pin_mask
        self.curr_cbus_register = self.curr_cbus_register & (~pin_mask)
        #Send new mask to the ftdi
        self.ftdi.set_cbus_direction(self.cbus_mask, self.curr_cbus_register)

        return self.ftdi.get_cbus_gpio() & pin_mask   

    def drive_cbus_pin_low(self, pin_mask):
        # Set selected pin as output and drive the bus low
        
        # Prepare new mask by placing 1 in the register at the offset of the pin_mask
        self.curr_cbus_register = self.curr_cbus_register | pin_mask
       
        self.ftdi.set_cbus_direction(self.cbus_mask, self.curr_cbus_register)
        
        #Drive the pin low
        self.ftdi.set_cbus_gpio(0b0000)    
    
    def read_SDA(self):
        # Set SDA as input and read the bus value
        # Also stops driving the line (sets HIGH_Z)
        return self.read_cbus_pin(self.cbus_sda_mask)

    def read_SCL(self):
        # Set SCL as input and stop driving the line (sets HIGH_Z)
        return self.read_cbus_pin(self.cbus_scl_mask)       

    def read_switch(self):
        # Set SCL as input and stop driving the line (sets HIGH_Z)
        return self.read_cbus_pin(self.cbus_switch_mask)   

    def drive_SDA_low(self):
        # Set SDA as output and drive the bus low
        self.drive_cbus_pin_low(self.cbus_sda_mask)

    def drive_SCL_low(self):
        # Set SCL as output and drive the bus low
        self.drive_cbus_pin_low(self.cbus_scl_mask)

    def drive_switch_low(self):
        # Set switch pin as output and drive the pin low    
        self.drive_cbus_pin_low(self.cbus_switch_mask)

    def write_i2c_bit(self, bit):
        if bit:
            self.read_SDA()

        else:
            self.drive_SDA_low()

        self.read_SCL()
        self.drive_SCL_low()
        self.read_SDA()

    def read_i2c_bit(self):
        self.read_SCL()
        bit = self.read_SDA()
        self.drive_SCL_low()

        return bit

    def stop_condition(self):
        # Master first releases the SCL and then the SDA line.
        self.drive_SDA_low()
        self.read_SCL()
        self.read_SDA()       

    def start_condition(self):
        # Sda goes low while scl is high
        while self.read_SDA() != 1:
            self.i2c_delay()
        self.read_SCL()
        self.drive_SDA_low()        
        self.drive_SCL_low()

    def i2c_delay(self):
        # Delay in between the frames for better synchronization        
        #time.sleep(0.002)
        pass

    def write_to_i2c(self, addres, data):
        driver.start_condition()
        for i in range(6, -1, -1):
            # Shift the bit to the rightmost position and mask with 1 to get its value
            self.write_i2c_bit((addres >> i) & 1)

        driver.write_i2c_bit(0)  # write

        if self.read_i2c_bit() != 0:
            print("[NACK] No response after sending device address")
            driver.stop_condition()
            return -1

        for i in range(7, -1, -1):
            # Shift the bit to the rightmost position and mask with 1 to get its value
            self.write_i2c_bit((data >> i) & 1)

        if self.read_i2c_bit() != 0:
            print("[NACK] No response after sending data")
            driver.stop_condition()

            return -1

        driver.stop_condition()

    def read_block_from_i2c(self, addres, register, len):
        if self.i2c_debug:
            print(f"Reading {len} bytes from {addres}@{register}")
        
        recieved_data = []
        self.start_condition()

        # Addr
        for i in range(6, -1, -1):
            # Shift the bit to the rightmost position and mask with 1 to get its value
            # print((addres >> i) & 1)
            self.write_i2c_bit((addres >> i) & 1)

        # Request Write
        self.write_i2c_bit(0)

        # Check for ACK
        if self.read_i2c_bit() != 0:
            if self.i2c_debug:
                print(f"[NACK] No response when trying to set up read from {addres}")
            self.stop_condition()
            return -1

        # Write Reg addr
        for i in range(7, -1, -1):
            # Shift the bit to the rightmost position and mask with 1 to get its value
            self.write_i2c_bit((register >> i) & 1)

        # Check for ACK
        if self.read_i2c_bit() != 0:
            print(f"[NACK] Device rejected reading from register {register}")
            self.stop_condition()
            return -1

        self.i2c_delay()
        # Restart condition
        self.start_condition()

        # Addr
        for i in range(6, -1, -1):
            self.write_i2c_bit((addres >> i) & 1)

        # READ
        self.write_i2c_bit(1)

        # Check for ACK
        if self.read_i2c_bit() != 0:
            print(f"[NACK] No response when trying to read from {addres}")
            driver.stop_condition()
            return -1

        self.i2c_delay()

        #Read requested data -1 byte
        for requested_byte in range(len - 1):
            self.byte_value = 0
            for i in range(8):
                self.byte_value = (self.byte_value << 1) | self.read_i2c_bit()
            recieved_data.append(self.byte_value)

            self.write_i2c_bit(0)  # ACK

            self.i2c_delay()

        #Read last byte
        self.byte_value = 0
        for i in range(8):
            self.byte_value = (self.byte_value << 1) | self.read_i2c_bit()
        recieved_data.append(self.byte_value)

        self.write_i2c_bit(1)  # NACK
        self.stop_condition()

        if self.i2c_debug:
            print("FTDI Response:", lsbblock2hex(recieved_data))
        return recieved_data

    def write_block_to_i2c(self, addres, register, data):
        data_len = len(data)
        if self.i2c_debug:
            print(
                f"Writing {data_len} bytes to {addres}@{register}, [{lsbblock2hex(data)}]"
            )

        self.start_condition()
       
        # Addr
        for i in range(6, -1, -1):
            # Shift the bit to the rightmost position and mask with 1 to get its value
            self.write_i2c_bit((addres >> i) & 1)

        # Request Write
        self.write_i2c_bit(0)

        # Check for ACK
        if self.read_i2c_bit() != 0:
            print(f"[NACK] No response when trying to write to device: {addres}")
            self.stop_condition()
            return -1

        # Reg addr
        for i in range(7, -1, -1):
            # Shift the bit to the rightmost position and mask with 1 to get its value
            self.write_i2c_bit((register >> i) & 1)

        # Check for ACK
        if self.read_i2c_bit() != 0:
            print(f"[NACK] No response after sending register address: {register}")
            self.stop_condition()
            return -1

        #Write data
        for byte in range(data_len):
            self.i2c_delay()
            for i in range(7, -1, -1):
                # Shift the bit to the rightmost position and mask with 1 to get its value
                self.write_i2c_bit((data[byte] >> i) & 1)

                # Check for ACK
            if self.read_i2c_bit() != 0:
                print(f"[NACK] No response after sending byte number: {byte}")
                self.stop_condition()
                return -1

        self.stop_condition()

    def close(self):
        self.read_SCL()
        self.read_SDA()
        self.read_switch()
        # Set curr cbus configuration to all HIGH_Z
        self.curr_cbus_register = 0b0000
        self.ftdi.set_cbus_direction(self.cbus_mask, self.curr_cbus_register)
        
        self.eeprom.connect(self.ftdi)            
        self.eeprom.set_property("cbus_func_1", "RXLED") #Revert to LED indicator    
        self.eeprom.set_property("cbus_func_2", "TXLED") #Revert to LED indicator              
        print("Reverting FT230X to UART configuration")
        self.eeprom.commit(dry_run=False)         
        self.eeprom.reset_device()
        #self.eeprom.dump_config()
        self.eeprom.close()

if __name__ == "__main__":
    # Example code for debug purposes
    # start default on SDA 0 SCL 3 
    driver = cbusBitBang(i2c_debug = True)

    # Release lines in case there is something leftover from other tests
    driver.read_SCL()
    driver.read_SDA()
    time.sleep(0.1)

    print(driver.read_block_from_i2c(0X23,0X27,15)[::-1])
    #driver.write_block_to_i2c(0X23,0X27,[0X1A,0X2B,0X3C,0X4D,0X5E,0X6F,0X1A,0X2B,0X3C,0X4D,0X5E,0X6F,0X1A,0X2B,0X3C])

    driver.close()
