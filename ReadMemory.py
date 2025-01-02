import os
from ctypes import *

import J2534
from J2534.Define import *
from Common import *
import Config as cfg

## ----------------------------------------- MAIN CODE ----------------------------------------- ##

devices = J2534.getDevices()
for id in devices:  # List of J2534 devices
    if id + 1 == cfg.devIndex:
        print('> ', end='')
    else:
        print('  ', end='')
    print(id + 1, devices[id])
    path = devices[id]['FunctionLibrary'].rsplit('\\', 1)[0] + '\\'
    os.add_dll_directory(path)  # Add .dll path to python searh for dependencies

while not cfg.devIndex in range(1, len(devices) + 1):  # if default devIndex not in list - choose device
    print('Select: ', end='')
    devIndexStr = input()
    if devIndexStr.isnumeric(): cfg.devIndex = int(devIndexStr)

J2534.setDevice(cfg.devIndex - 1)
ret, deviceID = J2534.ptOpen()

powerCycle(deviceID, powerOffPause, powerOnPause)

## -------------------------------- ISO Proto init ----------------------------------- ##

# protocolID = ProtocolID.ISO15765
# ret, channelID = J2534.ptConnect(deviceID, protocolID, 0x00000000, BaudRate.B500K)
# print(dtn(), '[ ISO15765 Connected ]')

# ret, filterID = ISO15765_SetFilter(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

## -------------------------------- SW ISO Proto init ----------------------------------- ##

SW_PS_HVWakeup(deviceID)

protocolID = ProtocolID.SW_ISO15765_PS
ret, channelID = J2534.ptConnect(deviceID, protocolID, 0x00000000, BaudRate.B33K)
print(dtn(), '[ SW_ISO15765_PS Connected ]')

SW_PS_SetConfig(channelID)

ret, filterID = ISO15765_SetFilter(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

##############################################################

print(dtn(), 'Start diag')

# IPC: comment it, it's okay to have false here
# if not startDiag(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
#     quit(-1)

print(dtn(), 'Disable comm')
if not disableComm(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
    quit(-1)

seed = askSeed2(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.requestSeed)
tryKey2(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.sendKey, cfg.keys[cfg.secLevel - 1])

### EBCM
# memoryAddressSize = 2 # bytes
# startAddress = 0x0000
# endAddress = 0x07FF+1
# memorySize = 0x01

### BCM
# memoryAddressSize = 4 # bytes
# startAddress = 0x000000
# endAddress = 0x100001
# memorySize = getMemorySizeByMemoryAddressSize(memoryAddressSize)

### TCM
# memoryAddressSize = 4 # bytes
# startAddress = 0x000000
# endAddress = 0x200000
# memorySize = 0x10#getMemorySizeByMemoryAddressSize(memoryAddressSize)

### IPC
memoryAddressSize = 4 # bytes
startAddress = 0x000000
endAddress = 0x200000
memorySize = 0x08#getMemorySizeByMemoryAddressSize(memoryAddressSize)

### ECM
# memoryAddressSize = 3 # bytes
# startAddress = 0x000000
# endAddress = 0x0FFFFF + 1
# endAddress = 0x005FFF + 1
# memorySize = 0xFB # ECM, experimentally identified

#memorySize = getMemorySizeByMemoryAddressSize(memoryAddressSize)

for memorySize in range(41302, 0xFFFF):
    print(memorySize)
    data = readMemoryByAddress(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, memoryAddressSize, 0, memorySize, readTimeoutMs=10000)
    if data != None:
        break

with open("ECU_DUMP.bin", "wb") as f:
    for memoryAddress in range(startAddress, endAddress, memorySize):
        if endAddress <= memoryAddress + memorySize:
            memorySize = endAddress - memoryAddress

        print(dtn(), "[0x{:04X} - 0x{:04X}]".format(memoryAddress, memoryAddress + memorySize))

        data = readMemoryByAddress(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, memoryAddressSize, memoryAddress, memorySize, readTimeoutMs=10000)

        if data == None:
            break

        sHex = ''
        if data != None:
            f.write(bytes(data))

            for d in data:
                sHex += "{:02X} ".format(d)

            print(sHex)

print(dtn(), 'ReturnToNormal')
ReturnToNormal(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

clrb(channelID)
J2534.ptStopMsgFilter(channelID, filterID)
powerOff(deviceID)
J2534.ptDisconnect(channelID)
J2534.ptClose(deviceID)
