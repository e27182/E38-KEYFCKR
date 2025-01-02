import os
import time
import J2534
from J2534.Define import *

from Logging import *

endNoNewLine = os.linesep if showErr else ' '

def get_bytes(num):  # Split "word" to high and low byte
    return num >> 8, num & 0xFF


def mirrorByte(num):  # "mirror" byte order (12 -> 21)
    mHexStr = addZ(hex(num)[2:], 2)
    return int(mHexStr[1] + mHexStr[0], 16)


def addZ(s, n):  # add "0" x n in begining of hex value
    while len(s) < n:
        s = '0' + s
    return s.upper()


def strMsg(msg, msgLen):  # message to Hex
    s = ''
    for x in range(msgLen):
        hexbyte = hex(msg[x])[2:]
        s = s + addZ(hexbyte, 2) + ' '
    return s.upper()


def printECUid(name, msg):  # convert ECU id message to int value
    s = ''
    id = 0
    for i in range(6, msg.DataSize):
        if msg.Data[6] > 0: s = s + hex(msg.Data[i])[2:]
    if len(s) > 0:
        id = int(s, 16)
        print(dtn(), name, id)
    return id


def print_eta(start_time, total_iterations, current_iteration, print_on_each_iteration):
    if (current_iteration + 1) % print_on_each_iteration == 0:
        elapsed_time = time.time() - start_time
        completed_iterations = current_iteration + 1
        avg_time_per_iteration = elapsed_time / completed_iterations
        remaining_iterations = total_iterations - completed_iterations
        estimated_time_remaining = avg_time_per_iteration * remaining_iterations

        # Convert estimated time remaining to human-readable format
        hrs, rem = divmod(estimated_time_remaining, 3600)
        mins, secs = divmod(rem, 60)

        print(dtn(), f"ETA: {completed_iterations}/{remaining_iterations}/{total_iterations}/{int(hrs)}h {int(mins)}m {int(secs)}s left.")


def printECUidStr(name, msg):  # convert ECU id message to string value
    s = ''
    for i in range(6, msg.DataSize):
        if msg.Data[i] > 0: s = s + chr(msg.Data[i]).upper()
    if len(s) > 0: print(dtn(), name, s)
    return s

def clrb(ChannelID):
    J2534.ClearRxBuf(ChannelID)
    J2534.ClearTxBuf(ChannelID)

def send(ProtocolID, ChannelID, reqID, msgTxData, TxFlags = 0x00000000, skipTillMsgNum = 1, breakOnMsg = None, ReadTimeout = 600):
    clrb(ChannelID)

    msgTx = J2534.ptTxMsg(ProtocolID, TxFlags)
    msgTx.setIDandData(reqID, msgTxData)

    J2534.ptWriteMsgs(ChannelID, msgTx, 1, ReadTimeout)
    traceMsg(msgTx, intoBus=True)

    msgRx = J2534.ptRxMsg()
    for i in range(skipTillMsgNum):
        J2534.ptReadMsgs(ChannelID, msgRx, 1, ReadTimeout)
        traceMsg(msgRx, intoBus=False)

        # check if msgRx ends with breakOnMsg
        if breakOnMsg != None and msgRx[-len(breakOnMsg):] == breakOnMsg:
            break

    return msgRx

def sendOnly(ProtocolID, ChannelID, reqID, msgTxData, TxFlags = 0x00000000):
    msgTx = J2534.ptTxMsg(ProtocolID, TxFlags)
    msgTx.setIDandData(reqID, msgTxData)

    J2534.ptWriteMsgs(ChannelID, msgTx, 1, 0)
    traceMsg(msgTx, intoBus=True)

def readOnly(ChannelID, ReadTimeout = 500):
    msgRx = J2534.ptRxMsg()
    J2534.ptReadMsgs(ChannelID, msgRx, 1, ReadTimeout)
    traceMsg(msgRx, intoBus=False)
    return msgRx

def traceMsg(msg, intoBus : bool):
    if showErr:
        print(dtn(), '<<' if intoBus else '>>', strMsg(msg.Data, msg.DataSize))

def isResponse(msg, rspID):
    return msg.DataSize >= 4 and int.from_bytes(msg[:4], "big") == rspID

def SW_PS_SetConfig(channelID, addLoopback=False):
    J2534.SetConfig(channelID, [(Parameter.J1962_PINS, 0x0100)])
    J2534.SetConfig(
        channelID,
        [
            (Parameter.SW_CAN_SPEEDCHANGE_ENABLE, 1),
            (Parameter.SW_CAN_RES_SWITCH, 2),
            (Parameter.SW_CAN_HS_DATA_RATE, BaudRate.B83K)
        ]
    )
    if addLoopback:
        J2534.SetConfig(channelID, [(Parameter.LOOPBACK, 1)])


def powerOn(deviceID, pause = 0.5):
    J2534.ptSetProgrammingVoltage(deviceID, 15, -2)
    print(dtn(), 'Power ON')
    time.sleep(pause)


def powerOff(deviceID, pause = 0.5):
    J2534.ptSetProgrammingVoltage(deviceID, 15, -1)
    print(dtn(), 'Power OFF')
    time.sleep(pause)

def powerCycle(deviceID, pauseOff = 0.5, pauseOn = 0.5):
    powerOff(deviceID, pauseOff)
    powerOn(deviceID, pauseOn)

def ISO15765_SetFilter(protocolId, channelId, reqId, rspId):
    maskMsg = J2534.ptTxMsg(protocolId, TxFlags.ISO15765_FRAME_PAD)
    maskMsg.setID(0xffffffff)
    patternMsg = J2534.ptTxMsg(protocolId, TxFlags.ISO15765_FRAME_PAD)
    patternMsg.setID(rspId)
    flowcontrolMsg = J2534.ptTxMsg(protocolId, TxFlags.ISO15765_FRAME_PAD)
    flowcontrolMsg.setID(reqId)

    return J2534.ptStartMsgFilter(channelId, FilterType.FLOW_CONTROL_FILTER, maskMsg, patternMsg, flowcontrolMsg)

def CAN_SetFilter(protocolId, channelId, reqId, rspId):
    maskMsg = J2534.ptTxMsg(protocolId, 0)
    maskMsg.setID(0xffffffff)
    patternMsg = J2534.ptTxMsg(protocolId, 0)
    patternMsg.setID(rspId)
    flowcontrolMsg = J2534.ptTxMsg(protocolId, 0)

    return J2534.ptStartMsgFilter(channelId, FilterType.PASS_FILTER, maskMsg, patternMsg, flowcontrolMsg)

## -------------------------------------- CAN Proto init --------------------------------------- ##
def SW_PS_HVWakeup(deviceID):
    protocolID = ProtocolID.SW_CAN_PS
    ret, channelID = J2534.ptConnect(deviceID, protocolID, 0x00000000, BaudRate.B33K)
    print(dtn(), '[ SW_CAN_PS Connected ]')

    SW_PS_SetConfig(channelID, addLoopback=True)

    maskMsg = J2534.ptTxMsg(protocolID, 0x00000000)
    maskMsg.setID(0x0000FFE0)
    patternMsg = J2534.ptTxMsg(protocolID, 0x00000000)
    patternMsg.setID(0x00000640) #rspCANId
    flowcontrolMsg = J2534.ptPatternMsgCAN(False)
    ret, filterID = J2534.ptStartMsgFilter(channelID, FilterType.PASS_FILTER, maskMsg, patternMsg, None)

    send(protocolID, channelID, 0x00000100, [], TxFlags.SW_CAN_HV_TX)
    send(protocolID, channelID, 0x00000101, [0xfd, 0x02, 0x10, 0x04, 0x00, 0x00, 0x00, 0x00])

    #clrb(channelID)
    J2534.ptStopMsgFilter(channelID, filterID)
    J2534.ptDisconnect(channelID)

    print(dtn(), '[ High Voltage Wakeup Completed ]')

## -------------------------------------- Operations --------------------------------------- ##

powerOffPause = 0.5
powerOnPause = 0.5  # pause between power off and on
startDiagPause = 0.5
disableCommPause = 0.5
seedPause = 10  # pause between askSeed commands
didPause = 1
cpidPause = 1

def startDiag(protocolID, channelID, reqID, rspID):  # start diagnostic session
    message = [0x10, 0x02] if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else [0x02, 0x10, 0x02]

    sendOnly(protocolID, channelID, reqID, message)
    
    i = 0
    while i < 10:
        i += 1
        msgRx = readOnly(channelID)
        if not isResponse(msgRx, rspID):
            continue

        if msgRx[-1:] == [0x50] or msgRx[-2:] == [0x10, 0x22]:
            return True
        elif msgRx[-3:-1] == [0x7F, 0x10]:
            error = msgRx[-1:][0]

            errorRsp = ISO14229_ErrorHandler(error, msgRx, responsePendingTimer=startDiagPause)
            if errorRsp == ErrorResponse.ContinueAfterResponsePending:
                sendOnly(protocolID, channelID, reqID, message)
                continue
            else:
                return False

    return False


def disableComm(protocolID, channelID, reqID, rspID):  # disable normal communication
    message = [0x28] if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else [0x01, 0x28]

    sendOnly(protocolID, channelID, reqID, message)

    i = 0
    while i < 10:
        i += 1
        msgRx = readOnly(channelID)
        if isResponse(msgRx, rspID) and msgRx[-1:] == [0x68]:
            return True

    return False

def ReturnToNormal(protocolID, channelID, reqID, rspID):  # disable normal communication
    message = [0x20] if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else [0x01, 0x20]

    sendOnly(protocolID, channelID, reqID, message)

    i = 0
    while i < 10:
        i += 1
        msgRx = readOnly(channelID)
        if isResponse(msgRx, rspID) and msgRx[-1:] == [0x60]:
            return True

    return False

# Should be used only as a "broadcast" 01 01 FE, and should not be sent directly to the device but....
def ProgrammingMode_requestProgrammingMode(protocolID, channelID, reqID, rspID):
    message = [0xA5, 0x01] if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else [0x02, 0xA5, 0x01]

    sendOnly(protocolID, channelID, reqID, message)

    i = 0
    while i < 10:
        i += 1
        msgRx = readOnly(channelID)

        if not isResponse(msgRx, rspID):
            continue

        responseCode = msgRx[-1:][0]

        errorRsp = ISO14229_ErrorHandler(responseCode, msgRx, responsePendingTimer=didPause)
        if errorRsp == ErrorResponse.ContinueAfterResponsePending:
            continue
        elif errorRsp == ErrorResponse.Success:
            return True
        else:
            return False

    return False

# Should be used only as a "broadcast" 01 01 FE, and should not be sent directly to the device but....
def ProgrammingMode_enableProgrammingMode(protocolID, channelID, reqID, rspID):
    message = [0xA5, 0x03] if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else [0x02, 0xA5, 0x03]

    sendOnly(protocolID, channelID, reqID, message)

    i = 0
    while i < 10:
        i += 1

        if readOnly(channelID, ReadTimeout=100).DataSize == 0: # wait at least 100ms
            return True

    return False
    

def askSeed2(protocolID, channelID, reqID, rspID, requestSeed):  # Asking the Seed
    message = [0x27, requestSeed] if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else [0x02, 0x27, requestSeed]

    print(dtn(), 'Ask seed')

    sendOnly(protocolID, channelID, reqID, message)

    aseed = 0
    while aseed == 0:
        msgRx = readOnly(channelID)
        
        if not isResponse(msgRx, rspID):
            continue

        if msgRx[-4:-2] == [0x67,  requestSeed]:
            aseed = int.from_bytes(msgRx[-2:], "big")
            print('Seed: ' + addZ(hex(aseed)[2:], 4))
            clrb(channelID)
            return aseed

        if msgRx[-3:-1] == [0x7F, 0x27]:
            error = msgRx[-1:][0]

            errorRsp = ISO14229_ErrorHandler(error, msgRx, delayTimer=seedPause)
            if errorRsp == ErrorResponse.ContinueAfterTimeDelay:
                sendOnly(protocolID, channelID, reqID, message)
                continue
            else:
                return False


def tryKey2(protocolID, channelID, reqID, rspID, sendKey, key):
    keyH, keyL = int.to_bytes(key, 2, "big")
    message = [0x27, sendKey, keyH, keyL] if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else [0x04, 0x27, sendKey, keyH, keyL]

    sendOnly(protocolID, channelID, reqID, message)

    i = 0
    while i < 10:
        i += 1
        msg = readOnly(channelID)

        if not isResponse(msg, rspID):
            continue

        if msg[-2:] == [0x67, sendKey]:  # 00 00 07 e8 02 [67 sendKey] - Key accepted
            print(f'KEY ACCEPTED: {addZ(hex(key)[2:], 4)}')
            return True
        
        if msg[-3:-1] == [0x7F, 0x27]:
            error = msg[-1:][0]

            errorRsp = ISO14229_ErrorHandler(error, msg, responsePendingTimer=didPause)
            if errorRsp == ErrorResponse.ContinueAfterResponsePending:
                continue
            else:
                return False
    
    return False

def readDID(protocolID, channelID, reqID, rspID, did):
    message = [0x1a, did] if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else [0x02, 0x1a, did]

    sendOnly(protocolID, channelID, reqID, message)
    
    i = 0
    while i < 10:
        i += 1
        msg = readOnly(channelID)

        if not isResponse(msg, rspID):
            continue

        if protocolID == ProtocolID.ISO15765 and msg[4:6] == [0x5A, did]: # successful response
            return msg[6:]
        
        if protocolID == ProtocolID.CAN and msg[4:7] == [0x02, 0x5A, did]: # successful response
            return msg[7:]

        if msg[-3:-1] == [0x7F, 0x1A]:
            error = msg[-1:][0]

            errorRsp = ISO14229_ErrorHandler(error, msg, responsePendingTimer=didPause)
            if errorRsp == ErrorResponse.ContinueAfterResponsePending:
                continue
            else:
                return None
    
    return None

def writeDID(protocolID, channelID, reqID, rspID, did, data : list):
    message = [0x3B, did] + data if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else [0x02, 0x3B, did] + data

    sendOnly(protocolID, channelID, reqID, message)
    
    i = 0
    while i < 10:
        i += 1
        msg = readOnly(channelID)

        if not isResponse(msg, rspID):
            continue

        if protocolID == ProtocolID.ISO15765 and msg[4:6] == [0x7B, did]: # successful response
            return msg[6:]
        
        if protocolID == ProtocolID.CAN and msg[4:7] == [0x02, 0x7B, did]: # successful response
            return msg[7:]

        if msg[-3:-1] == [0x7F, 0x1A]:
            error = msg[-1:][0]

            errorRsp = ISO14229_ErrorHandler(error, msg, responsePendingTimer=didPause)
            if errorRsp == ErrorResponse.ContinueAfterResponsePending:
                continue
            else:
                return None
    
    return None

MaxMemorySize = {
    2: 4092, # 0xFFC
    3: 4091, # 0xFFB
    4: 4090  # 0xFFA
}

def getMemorySizeByMemoryAddressSize(memoryAddressSize:int):
    return MaxMemorySize.get(memoryAddressSize, None)

def readMemoryByAddress(protocolID, channelID, reqID, rspID, memoryAddressSize:int, memoryAddress:int, memorySize:int, readTimeoutMs: int):
    #if memorySize > getMemorySizeByMemoryAddressSize(memoryAddressSize):
        #raise Exception('memorySize too big for specified memoryAddressSize.')

    data = list(memoryAddress.to_bytes(memoryAddressSize, 'big')) + list(memorySize.to_bytes(2, 'big'))
    message = [0x23] + data if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else [0x01 + len(data), 0x23] + data

    sendOnly(protocolID, channelID, reqID, message)
    
    i = 0
    while i < 10:
        i += 1
        msg = readOnly(channelID, readTimeoutMs)

        if not isResponse(msg, rspID):
            continue

        if protocolID == ProtocolID.ISO15765 and msg[4:5] == [0x63]: # successful response
            return msg[5 + memoryAddressSize:]
        
        if protocolID == ProtocolID.CAN and msg[4:6] == [memorySize + memoryAddressSize, 0x63]: # successful response
            return msg[6 + memoryAddressSize:]

        if msg[-3:-1] == [0x7F, 0x23]:
            error = msg[-1:][0]

            errorRsp = ISO14229_ErrorHandler(error, msg, responsePendingTimer=didPause)
            if errorRsp == ErrorResponse.ContinueAfterResponsePending:
                continue
            else:
                return None
    
    return None

def AEMode(protocolID, channelID, reqID, rspID, cpid, cb):
    message = [0xAE, cpid] + cb if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else [0x07, 0xAE, cpid] + cb

    sendOnly(protocolID, channelID, reqID, message)
    
    i = 0
    while i < 10:
        i += 1
        msg = readOnly(channelID)

        if not isResponse(msg, rspID):
            continue

        if protocolID == ProtocolID.ISO15765 and msg[4:6] == [0xEE, cpid]: # successful response
            return True
        
        if protocolID == ProtocolID.CAN and msg[4:7] == [0x02, 0xEE, cpid]: # successful response
            return True

        error = 0

        if msg[-3:-1] == [0x7F, 0xAE]:
            error = msg[-1:][0]
        elif msg[-5:-2] == [0x7F, 0xAE, 0xE3]: # DeviceControlLimitsExceeded
            error = msg[-3:-2][0]
        
        errorRsp = ISO14229_ErrorHandler(error, msg, responsePendingTimer=cpidPause)
        if errorRsp == ErrorResponse.ContinueAfterResponsePending:
            continue
        else:
            return False
        
    return False

class ErrorResponse(int):
    Success = 0,
    Error = 1 << 0,
    ContinueAfterTimeDelay = 1 << 1,
    ContinueAfterResponsePending = 1 << 2,
    InvalidFormat = 1 << 3

ISO14229_ErrorMapping = {
    0x00: ("positiveResponse", ErrorResponse.Success, None),
    0x10: ("generalReject", ErrorResponse.Error, None),
    0x11: ("serviceNotSupported", ErrorResponse.Error, None),
    0x12: ("SubFunctionNotSupported-InvalidFormat", ErrorResponse.Error or ErrorResponse.InvalidFormat, None),
    0x13: ("incorrectMessageLengthOrInvalidFormat", ErrorResponse.Error, None),
    0x14: ("responseTooLong", ErrorResponse.Error, None),
    0x21: ("busyRepeatRequest", ErrorResponse.Error, None),
    0x22: ("ConditionsNotCorrectOrRequestSequenceError", ErrorResponse.Error, None),
    0x24: ("requestSequenceError", ErrorResponse.Error, None),
    0x25: ("noResponseFromSubnetComponent", ErrorResponse.Error, None),
    0x26: ("FailurePreventsExecutionOfRequestedAction", ErrorResponse.Error, None),
    0x31: ("RequestOutOfRange", ErrorResponse.Error, None),
    0x33: ("securityAccessDenied", ErrorResponse.Error, None),
    0x35: ("InvalidKey", ErrorResponse.Error, None),
    0x36: ("ExceededNumberOfAttempts", ErrorResponse.Error, None),
    0x37: ("RequiredTimeDelayNotExpired", ErrorResponse.ContinueAfterTimeDelay, lambda delayTimer, _, __: time.sleep(delayTimer)),
    0x70: ("uploadDownloadNotAccepted", ErrorResponse.Error, None),
    0x71: ("transferDataSuspended", ErrorResponse.Error, None),
    0x71: ("generalProgrammingFailure", ErrorResponse.Error, None),
    0x71: ("wrongBlockSequenceCounter", ErrorResponse.Error, None),
    0x78: ("RequestCorrectlyReceived-ResponsePending", ErrorResponse.ContinueAfterResponsePending, lambda _, responsePendingTimer, __: time.sleep(responsePendingTimer)),
    0x7E: ("sub-functionNotSupportedInActiveSession", ErrorResponse.Error, None),
    0x7F: ("serviceNotSupportedInActiveSession", ErrorResponse.Error, None),
    0x81: ("rpmTooHigh", ErrorResponse.Error, None),
    0x82: ("rpmTooLow", ErrorResponse.Error, None),
    0x83: ("engineIsRunning", ErrorResponse.Error, None),
    0x84: ("engineIsNotRunning", ErrorResponse.Error, None),
    0x85: ("engineRunTimeTooLow", ErrorResponse.Error, None),
    0x86: ("temperatureTooHigh", ErrorResponse.Error, None),
    0x87: ("temperatureTooLow", ErrorResponse.Error, None),
    0x88: ("vehicleSpeedTooHigh", ErrorResponse.Error, None),
    0x89: ("vehicleSpeedTooLow", ErrorResponse.Error, None),
    0x8A: ("throttle/PedalTooHigh", ErrorResponse.Error, None),
    0x8B: ("throttle/PedalTooLow", ErrorResponse.Error, None),
    0x8C: ("transmissionRangeNotInNeutral", ErrorResponse.Error, None),
    0x8D: ("transmissionRangeNotInGear", ErrorResponse.Error, None),
    0x8F: ("brakeSwitch(es)NotClosed (Brake Pedal not pressed or not applied)", ErrorResponse.Error, None),
    0x90: ("shifterLeverNotInPark", ErrorResponse.Error, None),
    0x91: ("torqueConverterClutchLocked", ErrorResponse.Error, None),
    0x92: ("voltageTooHigh", ErrorResponse.Error, None),
    0x93: ("voltageTooLow", ErrorResponse.Error, None),
    0xE3: ("DeviceControlLimitsExceeded", ErrorResponse.Error, lambda _, __, msg: print(f"Limits: {msg[-2:]} {[hex(x) for x in msg[-2:]]}")),  # AE Mode
    0xE5: ("ProgrammingMode Positive Response Service Id", ErrorResponse.Success, None), # A5 ProgrammingMode
}

def ISO14229_ErrorHandler(error: int, msg, delayTimer: int = 0.5, responsePendingTimer: int = 0.5) -> ErrorResponse:
    message, code, action = ISO14229_ErrorMapping.get(error, None)

    if message != None:
        print(dtn(), message)
        
        if action:
            action(delayTimer, responsePendingTimer, msg)

        return code
    elif 0x01 <= error <= 0x0F or \
       0x15 <= error <= 0x20 or \
       error == 0x23 or \
       0x27 <= error <= 0x30 or \
       error == 0x32 or \
       error == 0x34 or \
       0x50 <= error <= 0x6F or \
       0x74 <= error <= 0x77 or \
       0x79 <= error <= 0x7D or \
       error == 0x80 or \
       error == 0x8E or \
       error == 0xFF:
        print(dtn(), 'ISOSAEReserved')
    elif 0x38 <= error <= 0x4F:
        print(dtn(), 'reservedByExtendedDataLinkSecurityDocument')
    elif 0x94 <= error <= 0xEF:
        print(dtn(), 'reservedForSpecificConditionsNotCorrect')
    else:
        print(dtn(), 'UnknownError')

    return ErrorResponse.Error