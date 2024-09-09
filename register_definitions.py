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

from collections import namedtuple

Register = namedtuple('Register', ['address', 'size', 'name'])

global_system_configuration = Register(0x27, 14, "Global System Configuration")
boot_flags = Register(0x2D, 12, "Boot Flags")
firmware_version = Register(0x0F, 4, "FW Version")
command1 = Register(0x08, 4, "CMD1")
data1 = Register(0x09, 64, "Data1")