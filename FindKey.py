# coding:utf-8

##  GM AcDelco E38 ECU KeyFCKR
##               by Flash/Tune
##               t.me/obd2help
##
## Power control - LLine (pin15)
## Use PowerBox or similar devce
##
## PS. Use x32 Python (3.12)
## PPS.Code written by my monkey
##       danсing on the keyboard

import os
from ctypes import *

import J2534
from J2534.Define import *
from Common import *
import Config as cfg

## -------------------------------------- Default Settings ------------------------------------- ##

so_file = os.path.dirname(__file__) + "\\gm-seed-key-so\\gm-seed-key.so"  # connect GM algo's Key gen
so = CDLL(so_file)

## ----------------------------------------- MAIN CODE ----------------------------------------- ##

deviceID = device_open(cfg.devIndex)

powerCycle(deviceID, powerOffPause, powerOnPause)

## -------------------------------- ISO Proto init / Get VIN ----------------------------------- ##

##############################################################

protocolID, channelID, filterID = ISO15765_Connect(deviceID, cfg.reqCANId, cfg.rspCANId)

##############################################################

# SW_PS_HVWakeup(deviceID)

# protocolID = ProtocolID.SW_ISO15765_PS
# ret, channelID = J2534.ptConnect(deviceID, protocolID, 0x00000000, BaudRate.B33K)
# print(dtn(), '[ SW_ISO15765_PS Connected ]')

#SW_PS_SetConfig(channelID)

##############################################################

vinMsg = readDID(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, 0x90)
VIN = ''.join(map(chr, vinMsg))

print(f'VIN: {VIN}')

if VIN is None:
    print(dtn(), 'VIN READ ERROR! Check connection and ECU!')
    #clrb(channelID)
    #powerOff(deviceID)
    #exit(666)

## --------------------------- Try to read last State (with this VIN) -------------------------- ##

configFileName = f"{VIN} {cfg.reqCANId:2x}"
cfg.readLastStateCfg(configFileName)

## --------------------------------- Generate Seed-Key list ------------------------------------ ##

print(dtn(), '[ Generate Seed-Key list ]')

keyAllgmlan = []
keyAllclass2 = []
keyAllothers = []

print(dtn(), 'Start diag')
if not startDiag(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
    quit(-1)

print(dtn(), 'Disable comm')
if not disableComm(protocolID, channelID, cfg.reqCANId, cfg.rspCANId):
    quit(-1)

seed = askSeed(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.requestSeed)
for algo in range(000, 256):
    keyAllgmlan.append(abs(so.get_key(seed, algo, 1)))
    keyAllclass2.append(abs(so.get_key(seed, algo, 2)))
    keyAllothers.append(abs(so.get_key(seed, algo, 3)))

keyDefault = keyAllgmlan[cfg.defaultKeyAlgo]

## ---------------------------------- Phase 0 - Default KEY ------------------------------------ ##

if cfg.phase == 0:
    print(dtn(), '[ Phase', cfg.phase, '- Default KEY ]')
    print(dtn(), 'Default ')
    if tryKey(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.sendKey, keyDefault):
        exit(0)

    cfg.phase = 1
    cfg.saveCfg(configFileName)
    clrb(channelID)
    powerOff(deviceID, powerOffPause)

## ---------------------------------- Phase 1 - Seed = KEY ------------------------------------ ##

if cfg.phase == 1:
    print(dtn(), '[ Phase', cfg.phase, '- Seed = KEY ]')
    powerOn(deviceID, powerOnPause)

    print(dtn(), 'Start diag')
    startDiag(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

    print(dtn(), 'Disable comm')
    disableComm(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

    seed = askSeed(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.requestSeed)

    print(dtn(), 'Seed=Key')
    if tryKey(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.sendKey, seed):
        exit(0)

    cfg.phase = 2
    cfg.saveCfg(configFileName)
    clrb(channelID)
    powerOff(deviceID, powerOffPause)

## --------------------------------- Phase 2-4 - try all algo ---------------------------------- ##

while cfg.phase in range(2, 4 + 1):
    if cfg.phase == 2:
        keyAll = keyAllgmlan
        print(dtn(), '[ Phase', cfg.phase, '- try all GMlan algo ]')
    if cfg.phase == 3:
        keyAll = keyAllclass2
        print(dtn(), '[ Phase', cfg.phase, '- try all class2 algo ]')
    if cfg.phase == 4:
        keyAll = keyAllothers
        print(dtn(), '[ Phase', cfg.phase, '- try all other algo ]')

    startTime = time.time()
    algoLastLast = cfg.algoLast
    for algo in range(algoLastLast, 256):

        ikey = keyAll[algo]

        if ikey == keyDefault:  # Skip default Key
            continue
        if ikey == seed:  # Skip Seed = Key
            continue
        if cfg.phase == 3 and ikey in keyAllgmlan:  # skip gmlan keys on phase 2
            continue
        if cfg.phase == 4 and (ikey in keyAllgmlan or ikey in keyAllclass2):  # skip gmlan and class2 keys on phase 3
            continue

        powerOn(deviceID, powerOnPause)

        print(dtn(), 'Start diag')
        startDiag(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

        print(dtn(), 'Disable comm')
        disableComm(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

        seed = askSeed(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.requestSeed)

        if cfg.phase == 2:
            print(dtn(), f'Proto: GMlan; Algo: 0x{algo:2x} {algo}')
        if cfg.phase == 3:
            print(dtn(), f'Proto: Class2; Algo: 0x{algo:2x} {algo}')
        if cfg.phase == 4:
            print(dtn(), f'Proto: Others Algo: 0x{algo:2x} {algo}')

        if tryKey(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.sendKey, ikey):
            powerOff(deviceID, powerOffPause)
            J2534.ptDisconnect(channelID)
            J2534.ptClose(deviceID)
            exit(0)
        else:
            cfg.algoLast = algo
            cfg.saveCfg(configFileName)
            clrb(channelID)
            powerOff(deviceID, powerOffPause)

        if (algo - algoLastLast + 1) % 5 == 0 and algo > algoLastLast:
            runTime = (time.time() - startTime)
            estSec = (runTime / (algo - algoLastLast + 1) * (256 - algo))
            print(dtn(), 'Tested now:', (algo - algoLastLast + 1), 'total:', algo + 1, '/', 256)
            print(dtn(), 'Runing time:', str(datetime.timedelta(seconds=runTime // 1)), end='')
            print(' // Est:', str(datetime.timedelta(seconds=estSec // 1)), '( phase', cfg.phase, ')')

    cfg.phase += 1
    cfg.algoLast = 0
    cfg.saveCfg(configFileName)
    clrb(channelID)
    powerOff(deviceID, powerOffPause)

## ------------------- Phase 5, 6 - same High and Low byte and Mirror hi/lo byte --------------------- ##

while cfg.phase in range(5, 6 + 1):

    print(dtn(), '[ Phase', cfg.phase, '- same High and Low byte ]')

    startTime = time.time()
    bkeyLastLast = cfg.bkeyLast

    for bkey in range(cfg.bkeyLast, 256):

        if cfg.phase == 5:
            low = bkey
            high = bkey
        if cfg.phase == 6:
            low = bkey
            high = mirrorByte(bkey)
            if low == high: # skip phase 4 keys
                continue

        currKey = (high << 8) + low
        if (currKey == keyDefault
                or currKey == seed
                or currKey in keyAllgmlan
                or currKey in keyAllclass2
                or currKey in keyAllothers):  # skip algo and default keys
            continue

        powerOn(deviceID, powerOnPause)
        
        print(dtn(), 'Start diag')
        startDiag(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

        print(dtn(), 'Disable comm')
        disableComm(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

        seed = askSeed(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.requestSeed)

        print(dtn(), 'Key: ', addZ(str(bkey), 3))

        if tryKey(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.sendKey, currKey):
            clrb(channelID)
            powerOff(deviceID, powerOffPause)
            J2534.ptDisconnect(channelID)
            J2534.ptClose(deviceID)
            exit(0)
        else:
            cfg.bkeyLast = bkey
            cfg.saveCfg(configFileName)
            clrb(channelID)
            powerOff(deviceID, powerOffPause)

        if (bkey - bkeyLastLast + 1) % 5 == 0 and bkey > bkeyLastLast:
            runTime = (time.time() - startTime)
            estSec = (runTime / (bkey - bkeyLastLast + 1) * (256 - bkey))
            print(dtn(), 'Tested now:', (bkey - bkeyLastLast + 1), 'total:', bkey + 1, '/', 256)
            print(dtn(), 'Runing time:', str(datetime.timedelta(seconds=runTime // 1)), end='')
            print(' // Est:', str(datetime.timedelta(seconds=estSec // 1)), '( phase', cfg.phase, ')')

    cfg.phase += 1
    cfg.bkeyLast = 0
    cfg.saveCfg(configFileName)
    clrb(channelID)
    powerOff(deviceID, powerOffPause)

## ----------------------------------- Phase 7 - Bruteforce ------------------------------------ ##

print(dtn(), '[ Phase', cfg.phase, '- Bruteforce ]')

startTime = time.time()
ikeyLastLast = cfg.ikeyLast

for ikey in range(cfg.ikeyLast, cfg.ikEnd, cfg.ikEnc):

    if not cfg.swapByte:
        high, low = get_bytes(ikey)  # high и low in normal order
    else:
        low, high = get_bytes(ikey)  # high и low changed!

    if cfg.phase == 8: # we already did it, and dont find seed key :-(
        print('All phase completed. Key not found.')
        print('(damaged ECU? Bad connection? Bugs in this bruteforcer?)')
        print('To run again - delete:')
        print('history\\' + VIN + '.last.ini')
        break

    currKey = ((high << 8) + low)
    if (currKey in keyAllgmlan  # check Key repeat in 0-5 phase
            or currKey in keyAllclass2
            or currKey in keyAllothers
            or high == low
            or high == mirrorByte(low)
            or currKey == keyDefault
            or currKey == seed): continue

    powerOn(deviceID, powerOnPause)

    print(dtn(), 'Start diag')
    startDiag(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

    print(dtn(), 'Disable comm')
    disableComm(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

    seed = askSeed(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.requestSeed)

    print(dtn(), ' ', end='')

    if tryKey(protocolID, channelID, cfg.reqCANId, cfg.rspCANId, cfg.sendKey, currKey):
        break  # We found it!
    else:
        cfg.ikeyLast = ikey
        cfg.saveCfg(configFileName)
        clrb(channelID)
        powerOff(deviceID, powerOffPause)

    if cfg.runForward:
        ikeysPass = (ikey - ikeyLastLast) + 1
    else:
        ikeysPass = (ikeyLastLast - ikey) + 1

    if (ikeysPass % 5 == 0  # Calculate run and time left.
            and ikeysPass > 5
            and ikey != ikeyLastLast
            and ikey != cfg.ikEnd):
        runTime = (time.time() - startTime)
        if cfg.runForward:
            leftSec = (runTime / ikeysPass * (cfg.ikEnd - ikey) / cfg.ikEnc)
            print(dtn(), 'Tested now:', ikeysPass, 'total:', ikey + 1, '/', cfg.ikEnd + 1)
        else:
            leftSec = abs(runTime / ikeysPass * (ikey - cfg.ikEnd) / cfg.ikEnc)
            print(dtn(), 'Tested now:', ikeysPass, 'total:', cfg.ikBeg - ikey + 1 + 256*5, '/', cfg.ikBeg + 1)

        print(dtn(), 'Runing time:', str(datetime.timedelta(seconds=runTime // 1)), end='')
        print(' // Left:', str(datetime.timedelta(seconds=leftSec // 1)), '( phase', cfg.phase, ')')

## ---------------------------------------- Program END ---------------------------------------- ##

print(dtn(), 'ReturnToNormal')
ReturnToNormal(protocolID, channelID, cfg.reqCANId, cfg.rspCANId)

cfg.phase += 1 # We have't phase 8. So, we can not find Seed Key.
cfg.saveCfg(configFileName)
clrb(channelID)
powerOff(deviceID)
J2534.ptDisconnect(channelID)
J2534.ptClose(deviceID)
