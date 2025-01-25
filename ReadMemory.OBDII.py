import os
from ctypes import *

import J2534
from J2534.Define import *
from Common import *
import Config as cfg

## ----------------------------------------- MAIN CODE ----------------------------------------- ##

deviceID = device_open(cfg.devIndex)

powerCycle(deviceID, powerOffPause, powerOnPause)

## -------------------------------- ISO Proto init ----------------------------------- ##

protocolID, channelID, filterID, testerPresentMsgID = ISO15765_Connect(deviceID, cfg.reqCANId, cfg.rspCANId, startTesterPresent=True)

## -------------------------------- SW ISO Proto init ----------------------------------- ##

# SW_PS_HVWakeup(deviceID)

# protocolID = ProtocolID.SW_ISO15765_PS
# ret, channelID = J2534.ptConnect(deviceID, protocolID, 0x00000000, BaudRate.B33K)
# print(dtn(), '[ SW_ISO15765_PS Connected ]')

# SW_PS_SetConfig(channelID)

# ret, filterID = ISO15765_SetFilter(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

##############################################################

print(dtn(), 'Start diag')
# IPC: comment it, it's okay to have false here
if not startDiag(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
    quit(-1)

print(dtn(), 'Disable comm')
if not disableComm(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
    quit(-1)

# print(dtn(), 'Programming mode')
# if not ProgrammingMode_requestProgrammingMode(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
#     quit(-1)

# if not ProgrammingMode_enableProgrammingMode(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
#     quit(-1)

print(dtn(), 'Unlock lvl 1 (seed\key)')
seed = askSeed(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.requestSeed)
tryKey(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.sendKey, cfg.keys[cfg.sendKey])

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

## TCM
memoryAddressSize = 4 # bytes
startAddress = 0x000000
endAddress = 0x200000
#endAddress = 0x000500
memorySize = 0x10 #getMemorySizeByMemoryAddressSize(memoryAddressSize)

### IPC
# memoryAddressSize = 4 # bytes
# startAddress = 0x000000
# endAddress = 0x200000
# memorySize = 0x08#getMemorySizeByMemoryAddressSize(memoryAddressSize)

# ### ECM
# memoryAddressSize = 3 # bytes
# startAddress = 0x00C300
# endAddress = 0x00C45F + 1
# #endAddress = 0x0FFFFF + 1
# memorySize = 0xFB # ECM, experimentally identified

#memorySize = getMemorySizeByMemoryAddressSize(memoryAddressSize)

######## Search for proper memorySize
# for memorySize in range(0x0000, 0xFFFF):
#     print(memorySize)
#     data = readMemoryByAddress(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, memoryAddressSize, 0, memorySize)
#     if data != None:
#         break
###################################

with open("ECU_DUMP.bin", "wb") as f:
    for memoryAddress in range(startAddress, endAddress, memorySize):
        if endAddress <= memoryAddress + memorySize:
            memorySize = endAddress - memoryAddress
            
        print(dtn(), "[0x{:04X} - 0x{:04X}]".format(memoryAddress, memoryAddress + memorySize))

        reconnectCount = 0
        while reconnectCount < 2:
            data = readMemoryByAddress(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, memoryAddressSize, memoryAddress, memorySize)

            # should not be the case
            # if data == None:
            #     # break # timeout or incorrect memorySize
            #     f.write(bytearray([0xC0] * memorySize))
            #     print(dtn(), 'EMPTY result written: 0xC0')
            #     continue

            if data != False:
                break # continue processing

            f.flush()

            reconnectCount += 1
            if reconnectCount == 2:
                break

            # print(dtn(), 'ReturnToNormal')
            # ReturnToNormal(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

            # clrb(channelID)
            # J2534.ptStopMsgFilter(channelID, filterID)
            # J2534.ptStopPeriodicMsg(channelID, testerPresentMsgID)
            # J2534.ptDisconnect(channelID)

            # powerCycle(deviceID, powerOffPause, powerOnPause)
            # protocolID, channelID, filterID, testerPresentMsgID = ISO15765_Connect(deviceID, cfg.reqCANId, cfg.rspCANId, startTesterPresent=True)

            # print(dtn(), 'Start diag')
            # # IPC: comment it, it's okay to have false here
            # if not startDiag(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
            #     quit(-1)

            # print(dtn(), 'Disable comm')
            # if not disableComm(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
            #     quit(-1)

            print(dtn(), 'Unlock lvl 1 (seed\key)')
            seed = askSeed(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.requestSeed)
            tryKey(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.sendKey, cfg.keys[cfg.sendKey])

        if reconnectCount == 2:
            print(dtn(), 'Read was unsuccessful. Terminating...')
            break

        data = data[memoryAddressSize:] # cut address

        # TCM special
        if data == [0x00, 0x00] and memorySize > len(data):
            f.write(bytearray([0xDE] * memorySize))
            print(dtn(), 'Protected region written: 0xDE')
            continue

        sHex = ''
        f.write(bytes(data))

        for d in data:
            sHex += "{:02X} ".format(d)

        print(sHex)

print(dtn(), 'ReturnToNormal')
ReturnToNormal(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

clrb(channelID)
J2534.ptStopMsgFilter(channelID, filterID)
J2534.ptStopPeriodicMsg(channelID, testerPresentMsgID)
powerOff(deviceID)
J2534.ptDisconnect(channelID)
J2534.ptClose(deviceID)
