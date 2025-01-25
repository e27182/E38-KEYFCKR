import os
from ctypes import *

import J2534
from J2534.Define import *
from Common import *
import Config as cfg

## ----------------------------------------- MAIN CODE ----------------------------------------- ##

deviceID = device_open(cfg.devIndex)

powerCycle(deviceID, powerOffPause, powerOnPause)

## -------------------------------- ISO Proto init / Get VIN ----------------------------------- ##

protocolID, channelID, filterID = ISO15765_Connect(deviceID, cfg.reqCANId, cfg.rspCANId)

## -------------------------------- Unlock access ----------------------------------- ##

# SW_PS_HVWakeup(deviceID)

# protocolID = ProtocolID.SW_CAN_PS
# ret, channelID = J2534.ptConnect(deviceID, protocolID, 0x00000800, BaudRate.B33K)
# print(dtn(), '[ CAN Connected ]')

# SW_PS_SetConfig(channelID, addLoopback=False)

# ret, filterID = CAN_SetFilter(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

# # send(protocolID, channelID, cfg.reqCANId, [0x02, 0x10, 0x02], skipTillMsgNum=3)
# # send(protocolID, channelID, cfg.reqCANId, [0x01, 0x28], skipTillMsgNum=3)

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

seed = askSeed(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.requestSeed)
tryKey(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.sendKey, cfg.keys[cfg.sendKey])

## -------------------------------------- Iterate CPIDs --------------------------------------- ##

for cpid in range(0x00, 0x100):
    print(dtn(), cpid, "0x{:02x}".format(cpid))

    if AEMode(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cpid, [0x80, 0x30, 0x33, 0x31, 0x39]):
        print('success')

print(dtn(), 'ReturnToNormal')
ReturnToNormal(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

clrb(channelID)
J2534.ptStopMsgFilter(channelID, filterID)
powerOff(deviceID)
J2534.ptDisconnect(channelID)
J2534.ptClose(deviceID)
