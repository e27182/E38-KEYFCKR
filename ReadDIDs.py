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

## -------------------------------- ISO Proto init / Get VIN ----------------------------------- ##

protocolID = ProtocolID.ISO15765
ret, channelID = J2534.ptConnect(deviceID, protocolID, 0x00000000, BaudRate.B500K)
print(dtn(), '[ ISO15765 Connected ]')

ret, filterID = ISO15765_SetFilter(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

## -------------------------------- Unlock access ----------------------------------- ##

# SW_PS_HVWakeup(deviceID)

# protocolID = ProtocolID.SW_CAN_PS
# ret, channelID = J2534.ptConnect(deviceID, protocolID, 0x00000800, BaudRate.B33K)
# print(dtn(), '[ CAN Connected ]')

# SW_PS_SetConfig(channelID, addLoopback=False)

# ret, filterID = CAN_SetFilter(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

# #send(protocolID, channelID, cfg.reqCANId, [0x02, 0x10, 0x02], skipTillMsgNum=3)
# #send(protocolID, channelID, cfg.reqCANId, [0x01, 0x28], skipTillMsgNum=3)

# clrb(channelID)
# J2534.ptStopMsgFilter(channelID, filterID)
# J2534.ptDisconnect(channelID)

##############################################################

# protocolID = ProtocolID.SW_ISO15765_PS
# ret, channelID = J2534.ptConnect(deviceID, protocolID, 0x00000000, BaudRate.B33K)
# print(dtn(), '[ SW_ISO15765_PS Connected ]')

##############################################################

#SW_PS_SetConfig(channelID)

# ## -------------------------------------- CAN Proto init --------------------------------------- ##

# protocolID = ProtocolID.CAN
# ret, channelID = J2534.ptConnect(deviceID, protocolID, 0x00000800, BaudRate.B500K)
# print(dtn(), '[ CAN Connected ]')

# CAN_SetFilter(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

## -------------------------------------- Authenticate --------------------------------------- ##

print(dtn(), 'Start diag')
if not startDiag(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
    quit(-1)

print(dtn(), 'Disable comm')
if not disableComm(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
    quit(-1)

seed = askSeed2(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.requestSeed)
tryKey2(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.sendKey, cfg.keys[cfg.secLevel - 1])

for did in range(0x00, 0x100):
    print(dtn(), did, "0x{:02x}".format(did), end=endNoNewLine)

    didData = readDID(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, did)

    if didData != None:
        sHex = ''
        sChr = ''
        sInt = "{:d}".format(int.from_bytes(didData)) if len(didData) == 4 else ''
        
        for d in didData:
            sHex += "{:02x} ".format(d)
            sChr += chr(d)

        print(sHex, sChr, sInt)

print(dtn(), 'ReturnToNormal')
ReturnToNormal(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

clrb(channelID)
J2534.ptStopMsgFilter(channelID, filterID)
powerOff(deviceID)
J2534.ptDisconnect(channelID)
J2534.ptClose(deviceID)
