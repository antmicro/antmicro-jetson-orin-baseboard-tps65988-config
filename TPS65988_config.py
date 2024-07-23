import json
from smbus2 import SMBus

def collect_register_data(data):
    register_data = {}
    
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "port specific registers":
                for port in value:
                    port_number = port.get("port number")
                    if port_number not in register_data:
                        register_data[port_number] = {}

                    for register in port.get("registers", []):
                        register_address = register.get("address")
                        if register_address not in register_data[port_number]:
                            register_data[port_number][register_address] = []

                        bitfields = register.get("bitfields", [])
                        for bitfield in bitfields:
                            start_position = bitfield.get("start position")
                            end_position = bitfield.get("end position")
                            value_editable = bitfield.get("value (EDITABLE)")
                            value_noneditable = bitfield.get("value (NON EDITABLE)")
                            bitfield_value = value_editable if value_editable is not None else value_noneditable
                            
                            # Calculate the size of the bitfield in bits
                            bitfield_size_bits = end_position - start_position + 1

                            # Convert the bitfield value to an integer
                            bitfield_value = int(str(bitfield_value), 16)

                            # Add bitfield data to the corresponding register
                            register_data[port_number][register_address].append((start_position, end_position, bitfield_value, bitfield_size_bits))
            else:
                nested_data = collect_register_data(value)
                for port, registers in nested_data.items():
                    if port not in register_data:
                        register_data[port] = {}
                    for address, bitfields in registers.items():
                        if address not in register_data[port]:
                            register_data[port][address] = []
                        register_data[port][address].extend(bitfields)
    elif isinstance(data, list):
        for item in data:
            nested_data = collect_register_data(item)
            for port, registers in nested_data.items():
                if port not in register_data:
                    register_data[port] = {}
                for address, bitfields in registers.items():
                    if address not in register_data[port]:
                        register_data[port][address] = []
                    register_data[port][address].extend(bitfields)
                
    return register_data

def split_data_into_chunks(data, chunk_size):
    """Helper function to split data into chunks of specified size."""
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

def print_register_info_and_smbus_commands(data, i2c_address_mapping):
    register_data = collect_register_data(data)
    
    for port, registers in register_data.items():
        i2c_address = i2c_address_mapping.get(port)
        print(f"Port number: {port}, I2C address: {hex(i2c_address)}")
        for register_address, bitfields in registers.items():
            # Initialize a byte array for the register value
            max_end_position = max(end_position for _, end_position, _, _ in bitfields)
            byte_length = (max_end_position + 8) // 8  # Round up to nearest byte
            register_value = [0] * (byte_length + 1)  # Initialize with extra space for size
            
            # Prepend the size of the list of data at the beginning
            register_value[0] = len(register_value) - 1  # Size of data excluding the size byte
            
            for start_position, end_position, value, bitfield_size_bits in bitfields:
                # Insert the value into the correct position in the byte array
                for bit in range(bitfield_size_bits):
                    byte_index = (start_position + bit) // 8
                    bit_index = (start_position + bit) % 8
                    if value & (1 << bit):
                        register_value[byte_index + 1] |= (1 << bit_index)  # Shifted by 1 due to size byte
            
            # Convert the register address to an integer
            command = int(register_address, 16)
            
            # Convert the register value to binary format for printing
            binary_register_value = [bin(byte) for byte in register_value]

            # Print the SMBus command
            print(f"Register address: {register_address}, Values: {binary_register_value}")
            print(f"bus.write_i2c_block_data({hex(i2c_address)}, {hex(command)}, {register_value})")
            
            # Split register value into chunks if it exceeds 32 bytes
            chunks = split_data_into_chunks(register_value, 32)

            # Send the SMBus command for each chunk
            with SMBus(1) as bus:
                for chunk in chunks:
                    bus.write_i2c_block_data(i2c_address, command, chunk)

# Load JSON data from a file
with open('orin2.json', 'r') as file:
    data = json.load(file)

# Define I2C addresses for each port
i2c_address_mapping = {
    1: 0x23,
    2: 0x27
}

# Print register information and SMBus commands
print_register_info_and_smbus_commands(data, i2c_address_mapping)
