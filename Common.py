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

def device_open(devIndex):
    devices = J2534.getDevices()
    for id in devices:  # List of J2534 devices
        if id + 1 == devIndex:
            print('> ', end='')
        else:
            print('  ', end='')
        print(id + 1, devices[id])
        path = devices[id]['FunctionLibrary'].rsplit('\\', 1)[0] + '\\'
        os.add_dll_directory(path)  # Add .dll path to python searh for dependencies

    while not devIndex in range(1, len(devices) + 1):  # if default devIndex not in list - choose device
        print('Select: ', end='')
        devIndexStr = input()
        if devIndexStr.isnumeric(): devIndex = int(devIndexStr)

    J2534.setDevice(devIndex - 1)
    ret, deviceID = J2534.ptOpen()
    return deviceID

def ISO15765_Connect(deviceID, reqCANId, rspCANId, startTesterPresent = False):
    protocolID = ProtocolID.ISO15765
    ret, channelID = J2534.ptConnect(deviceID, protocolID, 0x00000000, BaudRate.B500K)

    testerPresentMsgID = None
    if startTesterPresent:
        ret, testerPresentMsgID = StartTesterPresentMsg(protocolID, channelID)

    ret, filterID = ISO15765_SetFilter(protocolID, channelID, reqCANId, rspCANId)
    
    print(dtn(), '[ ISO15765 Connected ]')

    if startTesterPresent:
        return protocolID,channelID,filterID,testerPresentMsgID
    else:
        return protocolID,channelID,filterID

def ISO15765_SetFilter(protocolId, channelId, reqId, rspId):
    maskMsg = J2534.ptTxMsg(protocolId, TxFlags.ISO15765_FRAME_PAD)
    maskMsg.setID(0xffffffff)
    patternMsg = J2534.ptTxMsg(protocolId, TxFlags.ISO15765_FRAME_PAD)
    patternMsg.setID(rspId)
    flowcontrolMsg = J2534.ptTxMsg(protocolId, TxFlags.ISO15765_FRAME_PAD)
    flowcontrolMsg.setID(reqId)

    return J2534.ptStartMsgFilter(channelId, FilterType.FLOW_CONTROL_FILTER, maskMsg, patternMsg, flowcontrolMsg)

def CAN_Connect(deviceID, reqCANId, rspCANId, startTesterPresent = False):
    protocolID = ProtocolID.CAN
    ret, channelID = J2534.ptConnect(deviceID, protocolID, 0x00000800, BaudRate.B500K)

    testerPresentMsgID = None
    if startTesterPresent:
        ret, testerPresentMsgID = StartTesterPresentMsg(protocolID, channelID)

    ret, filterID = CAN_SetFilter(protocolID, channelID, reqCANId, rspCANId)

    print(dtn(), '[ CAN Connected ]')

    return protocolID,channelID,filterID,testerPresentMsgID

def CAN_SetFilter(protocolId, channelId, reqId, rspId):
    maskMsg = J2534.ptTxMsg(protocolId, 0)
    maskMsg.setID(0xffffffff)
    patternMsg = J2534.ptTxMsg(protocolId, 0)
    patternMsg.setID(rspId)
    flowcontrolMsg = J2534.ptTxMsg(protocolId, 0)

    return J2534.ptStartMsgFilter(channelId, FilterType.PASS_FILTER, maskMsg, patternMsg, flowcontrolMsg)

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

## -------------------------------------- Operations --------------------------------------- ##

powerOffPause = 0.5
powerOnPause = 0.5  # pause between power off and on
startDiagPause = 1
disableCommPause = 0.5
seedPause = 10  # pause between askSeed commands, 10 sec - normal mode, 16 sec - programming mode
memReadPause = 0.1
didPause = 1
cpidPause = 1

def standardCommRoutine(protocolID, channelID, reqID, rspID, operationAndParams, retries = 10, delayTimer=0.5, responsePendingTimer=0.5, successfulResponse = None):  # simple standard operation
    message = operationAndParams if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else [len(operationAndParams)].extend(operationAndParams) # for CAN
    operation = operationAndParams[0]
    successfulResponse = operation + 0x40 if successfulResponse == None else successfulResponse
    rspIdx = 4 if protocolID == ProtocolID.ISO15765 or ProtocolID.SW_ISO15765_PS else 5 # for CAN

    sendOnly(protocolID, channelID, reqID, message)

    i = 0
    while i < retries:
        i += 1
        msgRx = readOnly(channelID)

        if not isResponse(msgRx, rspID):
            continue
        elif msgRx[rspIdx:rspIdx+1] == [successfulResponse]:
            return True if msgRx.DataSize == rspIdx+1 else msgRx[rspIdx+1:]
        elif msgRx[rspIdx:rspIdx+2] == [0x7F, operation]:
            negativeResponse = msgRx[rspIdx+2:rspIdx+3][0]

            errorRsp = ISO14229_ErrorHandler(negativeResponse, msgRx, delayTimer, responsePendingTimer)
            if errorRsp == ErrorResponse.ContinueAfterResponsePending:
                continue
            elif errorRsp == ErrorResponse.ContinueAfterTimeDelay:
                sendOnly(protocolID, channelID, reqID, message)
                continue
            elif errorRsp == ErrorResponse.Success:
                return True
            else:
                return False

    return False    

def startDiag(protocolID, channelID, reqID, rspID):  # start diagnostic session
    return standardCommRoutine(protocolID, channelID, reqID, rspID, [0x10, 0x02])

def disableComm(protocolID, channelID, reqID, rspID):  # disable normal communications
    return standardCommRoutine(protocolID, channelID, reqID, rspID, [0x28])

def ReturnToNormal(protocolID, channelID, reqID, rspID):  # enable normal communications
    return standardCommRoutine(protocolID, channelID, reqID, rspID, [0x20])

def CAN_BENCH_ReturnToNormal(protocolID, channelID, reqID, rspID):
    message = [0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

    sendOnly(protocolID, channelID, reqID, message)

    i = 0
    while i < 2:
        i += 1
        msgRx = readOnly(channelID)
        if isResponse(msgRx, rspID) and msgRx[4:5] == [0x01]:
            return True

    return False

# Should be used only as a "broadcast" 01 01 FE, and should not be sent directly to the device but....
def ProgrammingMode_requestProgrammingMode(protocolID, channelID, reqID, rspID):
    return standardCommRoutine(protocolID, channelID, reqID, rspID, [0xA5, 0x01])

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
    

def askSeed(protocolID, channelID, reqID, rspID, requestSeed):  # Asking the Seed
    ret = standardCommRoutine(protocolID, channelID, reqID, rspID, [0x27, requestSeed], delayTimer=seedPause)

    if isinstance(ret, list):
        seed = int.from_bytes(ret[1:], "big")
        print('Seed: ' + addZ(hex(seed)[2:], (len(ret) - 1) * 2))
        return seed
    
    return ret

def tryKey(protocolID, channelID, reqID, rspID, sendKey, key):
    byteLen = (int.bit_length(key) + 7) // 8
    byteLen = 2 if byteLen < 2 else byteLen
    
    keyData = list(int.to_bytes(key, byteLen, "big"))
    ret = standardCommRoutine(protocolID, channelID, reqID, rspID, [0x27, sendKey] + keyData, delayTimer=seedPause)

    if ret == [0x02]:
        print(f'KEY ACCEPTED: {addZ(hex(key)[2:], 4)}')
        return True

    return ret

def readDID(protocolID, channelID, reqID, rspID, did):
    return standardCommRoutine(protocolID, channelID, reqID, rspID, [0x1a, did], responsePendingTimer=didPause)

def writeDID(protocolID, channelID, reqID, rspID, did, data : list):
    return standardCommRoutine(protocolID, channelID, reqID, rspID, [0x3b, did], responsePendingTimer=didPause)

MaxMemorySize = {
    2: 4092, # 0xFFC
    3: 4091, # 0xFFB
    4: 4090  # 0xFFA
}

def getMemorySizeByMemoryAddressSize(memoryAddressSize:int):
    return MaxMemorySize.get(memoryAddressSize, None)

def readMemoryByAddress(protocolID, channelID, reqID, rspID, memoryAddressSize:int, memoryAddress:int, memorySize:int):
    #if memorySize > getMemorySizeByMemoryAddressSize(memoryAddressSize):
        #raise Exception('memorySize too big for specified memoryAddressSize.')

    data = list(memoryAddress.to_bytes(memoryAddressSize, 'big')) + list(memorySize.to_bytes(2, 'big'))
    return standardCommRoutine(protocolID, channelID, reqID, rspID, [0x23] + data, responsePendingTimer=memReadPause)

def writeMemoryByAddress(protocolID, channelID, reqID, rspID, alfid, memoryAddress, memorySize, data:list):
    msgData = list(alfid.to_bytes(1, 'big')) + list(memoryAddress.to_bytes(2, 'big')) + list(memorySize.to_bytes(1, 'big')) + data
    return standardCommRoutine(protocolID, channelID, reqID, rspID, [0x3D] + msgData, responsePendingTimer=didPause)

def routineControl(protocolID, channelID, reqID, rspID, routineId):
    return standardCommRoutine(protocolID, channelID, reqID, rspID, [0x31, routineId], responsePendingTimer=didPause, successfulResponse=0xFF)

def AEMode(protocolID, channelID, reqID, rspID, cpid, cb):
    return standardCommRoutine(protocolID, channelID, reqID, rspID, [0xAE, cpid], responsePendingTimer=cpidPause)

def StartTesterPresentMsg(protocolID, channelID, timeInterval = 500):
    testerPresentMsg = J2534.ptTxMsg(protocolID, TxFlags.ISO15765_FRAME_PAD | TxFlags.ISO15765_ADDR_TYPE)
    testerPresentMsg.setIDandData(0x0101, [0xFE, 0x3E, 0x00])
    ret, testerPresentMsgID = J2534.ptStartPeriodicMsg(channelID, testerPresentMsg, timeInterval)
    return ret, testerPresentMsgID

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

def ISO14229_ErrorHandler(rsp: int, msg, delayTimer: int = 0.5, responsePendingTimer: int = 0.5) -> ErrorResponse:
    message, code, action = ISO14229_ErrorMapping.get(rsp, (None, None, None))

    if message != None:
        print(dtn(), message)
        
        if action:
            action(delayTimer, responsePendingTimer, msg)

        return code
    elif 0x01 <= rsp <= 0x0F or \
       0x15 <= rsp <= 0x20 or \
       rsp == 0x23 or \
       0x27 <= rsp <= 0x30 or \
       rsp == 0x32 or \
       rsp == 0x34 or \
       0x50 <= rsp <= 0x6F or \
       0x74 <= rsp <= 0x77 or \
       0x79 <= rsp <= 0x7D or \
       rsp == 0x80 or \
       rsp == 0x8E or \
       rsp == 0xFF:
        print(dtn(), 'ISOSAEReserved')
    elif 0x38 <= rsp <= 0x4F:
        print(dtn(), 'reservedByExtendedDataLinkSecurityDocument')
    elif 0x94 <= rsp <= 0xEF:
        print(dtn(), 'reservedForSpecificConditionsNotCorrect')
    else:
        print(dtn(), 'UnknownError')

    return ErrorResponse.Error