import configparser
import os
import shutil

## -------------------------------------- Default Settings ------------------------------------- ##

devIndex = 4  # index of default J2534 interface
defaultKeyAlgo = 0x92  # Default algo for E38 ECU (proto gmlan)

secLevel = 1 # [1,2] - SPS, [3,4] - DevCtrl, [5,6][7,8][9,A] - Rsrvd, [B,C][D,E][F,10] - Rsrvd by manufacturer < FA
requestSeed = 2 * secLevel - 1
sendKey = 2 * secLevel

# Module
keys = {
    0x02: 0x1111,
    0x04: 0x2222
}

# uncomment what you need
# # reqCANId = 0x00000241 # HS-CAN, BCM
reqCANId = 0x00000243 # HS-CAN, EBCM/ABS
# # reqCANId = 0x00000244 # LS-CAN, 
# # reqCANId = 0x00000259 # LS-CAN, 
# # reqCANId = 0x00000251 # LS-CAN, 
# # reqCANId = 0x0000025D # LS-CAN, 
# # reqCANId = 0x00000247 # LS-CAN, 
# # reqCANId = 0x0000024C # LS-CAN, IPC
rspCANId = reqCANId + 0x400
# # OR
# # reqCANId = 0x000007E0 # HS-CAN, ECU
# # reqCANId = 0x000007E2 # HS-CAN, TCM
# rspCANId = reqCANId + 0x08

## -------------------------------------- Bruteforce config ------------------------------------- ##

cfg = configparser.ConfigParser()

global ikeyLast, ikBeg, ikEnd, ikEnc, swapByte, runForward, algoLast, bkeyLast, phase

phase = 0  # 0 = default key, 1 = 256 standard algos, 2 = bruteforce
runForward = False  # Key from 0000 to FFFF, or backward
swapByte = False  # Swap high and low Key Byte

if runForward:  # Forward order
    ikeyLast = 0
    ikBeg = 0
    ikEnd = 0xFFFF
    ikEnc = 1
    phase = 0
else:  # Reverse order
    ikeyLast = 0xFFFF
    ikBeg = 0xFFFF
    ikEnd = 0
    ikEnc = -1
    phase = 0

algoLast = 0
bkeyLast = 0

cfg['DEFAULT'] = {'ikeyLast': str(ikBeg),
                  'ikBeg': str(ikBeg),
                  'ikEnd': str(ikEnd),
                  'ikEnc': str(ikEnc),
                  'swapByte': str(swapByte),
                  'algoLast': str(algoLast),
                  'bkeyLast': str(bkeyLast),
                  'phase': str(0)}

def getFilePathCfg(fileName):
    return 'history\\' + fileName + '.last.ini'

def getBackupPathCfg(fileName):
    return 'history\\' + fileName + '.last.bak'

def readCfg(fileName):  # read config
    global ikeyLast, ikBeg, ikEnd, ikEnc, swapByte, runForward, algoLast, bkeyLast, phase

    if not os.path.exists('history'):
        os.mkdir('history')

    cfgFile = getFilePathCfg(fileName)

    if not os.path.exists(cfgFile):
        return False

    cfg.read(cfgFile)
    ikeyLast = int(cfg.get('DEFAULT', 'ikeyLast'))
    ikBeg = int(cfg.get('DEFAULT', 'ikBeg'))
    ikEnd = int(cfg.get('DEFAULT', 'ikEnd'))
    ikEnc = int(cfg.get('DEFAULT', 'ikEnc'))
    swapByte = eval(cfg.get('DEFAULT', 'swapByte'))
    algoLast = int(cfg.get('DEFAULT', 'algoLast'))
    bkeyLast = int(cfg.get('DEFAULT', 'bkeyLast'))
    phase = int(cfg.get('DEFAULT', 'phase'))
    if ikEnc > 0: 
        runForward = True
    else:
        runForward = False

    return True


def saveCfg(fileName):  # oh yea, save config
    global ikeyLast, ikBeg, ikEnd, ikEnc, swapByte, runForward, algoLast, bkeyLast, phase

    cfgFile = getFilePathCfg(fileName)

    if os.path.exists(cfgFile):
        shutil.copyfile(cfgFile, getBackupPathCfg(fileName))

    cfg.set('DEFAULT', 'ikeyLast', str(ikeyLast))
    cfg.set('DEFAULT', 'ikBeg', str(ikBeg))
    cfg.set('DEFAULT', 'ikEnd', str(ikEnd))
    cfg.set('DEFAULT', 'ikEnc', str(ikEnc))
    cfg.set('DEFAULT', 'swapByte', str(swapByte))
    cfg.set('DEFAULT', 'algoLast', str(algoLast))
    cfg.set('DEFAULT', 'bkeyLast', str(bkeyLast))
    cfg.set('DEFAULT', 'phase', str(phase))

    with open(cfgFile, 'w') as config_file:
        cfg.write(config_file)

def readLastStateCfg(fileName):
    global ikeyLast, ikBeg, ikEnd, ikEnc, swapByte, runForward, algoLast, bkeyLast, phase

    if readCfg(fileName):
        print('[ Read settings from:', fileName, ']')
        print('Last key: {:02x}\nStart key: {:02x}\nEnd key: {:02x}\nStep: {:02x}\nswapByte: {:02x}\nrunForward: {:02x}\nalgoLast: {:02x}\nbkeyLast: {:02x}\nphase: {:02x}'
              .format(ikeyLast, ikBeg, ikEnd, ikEnc, swapByte, runForward, algoLast, bkeyLast, phase))
    else:
        print('[ Begin from scratch (no config file) ]')