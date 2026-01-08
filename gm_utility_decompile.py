#!/usr/bin/env python3
"""
gm_utility_decompile.py

Decompile (decode) a GM SPS utility file from its binary form into a readable listing.

Implements the structure described in the GM "SPS Interpreter" specification:
- 24-byte header
- Interpreter instruction section: 16-byte records until "offset to routine section"
- Routine section: repeating (4-byte address, 2-byte length, <length> data)

Python: 3.10+
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --- Op-Code name maps (subset: extend as needed) ---
COMMON_OPCODES: Dict[int, str] = {
    0x50: "Compare Bytes",
    0x51: "Compare Checksum",
    0x53: "Compare Data",
    0x54: "Change Data",
    0x55: "Evaluate RPO (plant)",
    0x56: "Interpreter Identifier",
    0xEE: "End with ERROR",
    0xF1: "Set Global Memory Address",
    0xF2: "Set Global Memory Length",
    0xF3: "Set Global Header Length",
    0xF4: "Ignore Responses for Milliseconds",
    0xF5: "Override Utility File Message Length",
    0xF7: "No Operation",
    0xF8: "Goto Field continuation",
    0xFB: "Set and Decrement Counter",
    0xFC: "Delay (Seconds/Minutes)",
    0xFD: "Reset counter",
    0xFF: "End with SUCCESS",
}

GMLAN_OPCODES: Dict[int, str] = {
    0x01: "Setup Global Variables",
    0x10: "Mode 10 Initiate Diagnostic Operation",
    0x14: "Mode 04 Clear DTCs",
    0x1A: "Mode 1A Read Data by Identifier (DID)",
    0x20: "Mode 20 Return to Normal Mode",
    0x22: "Mode 22 Read Data by Parameter Identifier (PID)",
    0x25: "Mode AE Security Code",
    0x27: "Mode 27 Security Access",
    0x34: "Mode 34 Request Download",
    0x3B: "Mode 3B Write Data by Identifier",
    0x84: "Set Communications Parameters",
    0xA2: "Mode A2 Report Programmed State (save response)",
    0xAA: "Mode AA Read Data by Packet Identifier",
    0xAE: "Mode AE Request Device Control",
    0xB0: "Mode 36 Block Transfer to RAM",
}

UART_OPCODES: Dict[int, str] = {
    0x00: "Enable Normal Communications",
    0x01: "Request message from device",
    0x02: "Request memory dump (Mode 2)",
    0x03: "Verify EEPROM programming (Mode 3)",
    0x04: "Device control (Mode 4)",
    0x05: "RAM download request (Mode 5)",
    0x08: "Disable Normal Communications",
    0x09: "Enable Normal Communications",
    0x0A: "Clear Trouble Codes (Mode 10)",
    0x0C: "Program EEPROM (Mode 12)",
    0x0D: "Perform Security (Mode 13)",
}

CLASS2_OPCODES: Dict[int, str] = {
    0x01: "Setup Global Variables",
    0x10: "Initiate Diagnostic Operation",
    0x14: "Clear Diagnostic Information",
    0x20: "Return to Normal Mode",
    0x27: "Perform Security (Mode 27)",
    0x34: "Request Block Transfer (Mode 34)",
    0x3B: "Write block of memory",
    0x84: "Set Communications Parameters (Add Delay)",
    0xB0: "Block Transfer to RAM and Execute (Mode 36)",
}

KWP_OPCODES: Dict[int, str] = {
    0x01: "Setup KWP2000 Programming",
    0x10: "Start Diagnostic Session (SR 10)",
    0x11: "ECU Reset (SR 11)",
    0x14: "Clear DTCs (SR 14)",
    0x20: "Stop Diagnostic Session (SR 20)",
    0x23: "Read Memory by Address (SR 23)",
    0x27: "Security Access Request (SR 27)",
    0x34: "Download Request (SR 34)",
    0x3B: "Write Data by Local ID (SR 3B)",
    0x3D: "Write Memory by Address (SR 3D)",
    0x83: "Access Communications Parameters (SR 83)",
    0x84: "Set Communications Parameters (SR 83)",
    0x90: "Transfer Routine to ECU (SR 36)",
    0x93: "Transfer Calibration File to ECU (SR 36)",
}

INTERPRETER_NAMES = {0: "UART", 1: "Class 2", 2: "KWP2000", 3: "GMLAN"}

GMLAN_DID_NAMES = {
    0x90: "VehicleIdentificationNumber",
    0x98: "RepairShopCodeOrTesterSerial",
    0x99: "ProgrammingDate",
    0xCB: "EndModelPartNumber",
}

# Internal Data Specifiers used with Mode 3B when AC3=0x03 (plant-only).
GMLAN_INTERNAL_DATA_SPECIFIERS = {
    0x45: "TPM Placard data",
    0x46: "Diesel Injector IMA/IQA data",
    0x47: "TCCM B-Cal value",
    0x48: "Key Fob data",
    0x49: "Engine Serial Number",
}

def bytes_spaced(hexstr: str) -> str:
    # "010203" -> "01 02 03"
    return " ".join(hexstr[i:i+2] for i in range(0, len(hexstr), 2))

def opcode_name(interpreter_type: int, opcode: int) -> str:
    if opcode in COMMON_OPCODES:
        return COMMON_OPCODES[opcode]
    if interpreter_type == 0:
        return UART_OPCODES.get(opcode, "Unknown/Unmapped")
    if interpreter_type == 1:
        return CLASS2_OPCODES.get(opcode, "Unknown/Unmapped")
    if interpreter_type == 2:
        return KWP_OPCODES.get(opcode, "Unknown/Unmapped")
    if interpreter_type == 3:
        return GMLAN_OPCODES.get(opcode, "Unknown/Unmapped")
    return "Unknown/Unmapped"


def fmt_rc(rc: int, interpreter_type: int, opcode: int) -> str:
    if rc == 0xFD:
        return "FD (NO_COMM)"
    if rc == 0xFF:
        return "FF (ANY)"
    
    suffix = ""
    if interpreter_type == 3 and opcode is not None:
        expected_pos = (opcode + 0x40) & 0xFF
        if rc == expected_pos:
            suffix = " (POS_RSP)"

    return f"{rc:02X}{suffix}"


# --- GOTO field interpretation -------------------------------------------------
# Most instructions use the 10-byte GOTO area as five (RC, STEP) pairs:
#   (G0,G1), (G2,G3), (G4,G5), (G6,G7), (G8,G9)
# and are printed as:  <RC> -> <STEP>.
#
# Some "compare"/flow-control opcodes instead use those bytes as *conditional branches*
# where the RC bytes are unused and particular STEP bytes have semantic meaning.
#
# Customize per-opcode rules here: each rule is (label, pair_index, element_index)
# where element_index=1 selects the STEP byte inside the (RC,STEP) pair.
#
# Example (0x50 Compare Bytes): G1 = "match" branch, G3 = "mismatch" branch.
GOTO_RULES: Dict[int, List[Tuple[str, int, int]]] = {
    0x50: [("match", 0, 1), ("mismatch", 1, 1)],   # G1, G3
    0x53: [("match", 0, 1), ("mismatch", 1, 1)],   # G1, G3
    0xFB: [("loop>0", 0, 1), ("expired", 1, 1)],   # G1, G3
    0xFC: [("after_delay", 0, 1)],                 # G1
}

def format_gotos_default(interpreter_type: int, opcode: int, gotos: List[Tuple[int, int]]) -> str:
    parts: List[str] = []
    for rc, st in gotos:
        if rc == 0 and st == 0:
            parts.append("00->00")
        else:
            parts.append(f"{fmt_rc(rc, interpreter_type, opcode=opcode)} -> 0x{st:02X}")
    return ", ".join(parts)

def format_gotos(interpreter_type: int, opcode: int, gotos: List[Tuple[int, int]]) -> str:
    rules = GOTO_RULES.get(opcode)
    if not rules:
        return format_gotos_default(interpreter_type, opcode, gotos)

    used = set()
    parts: List[str] = []
    for label, pair_i, elem_i in rules:
        if pair_i < 0 or pair_i >= len(gotos):
            continue
        step = gotos[pair_i][elem_i]
        used.add(pair_i)
        if step != 0:
            parts.append(f"{label} -> 0x{step:02X}")

    # If there are other non-zero pairs not covered by the rules, append them in default form.
    extras: List[str] = []
    for i, (rc, st) in enumerate(gotos):
        if i in used:
            continue
        if rc != 0 or st != 0:
            extras.append(f"{fmt_rc(rc, interpreter_type, opcode)} -> 0x{st:02X}")
    if extras:
        parts.append("extra: " + ", ".join(extras))

    return ", ".join(parts) if parts else format_gotos_default(interpreter_type, opcode, gotos)

@dataclass(frozen=True)
class UtilityHeader:
    checksum: int
    module_id: int
    part_number: int
    design_level_suffix: int
    header_utility_type: int
    interpreter_type: int
    offset_to_routines: int
    addressing_type: int
    data_address_info: int
    num_data_bytes_msg: int

    @staticmethod
    def parse(buf: bytes) -> "UtilityHeader":
        if len(buf) < 24:
            raise ValueError("File too small: cannot read 24-byte header.")
        u16 = lambda off: int.from_bytes(buf[off : off + 2], "big")
        u32 = lambda off: int.from_bytes(buf[off : off + 4], "big")
        return UtilityHeader(
            checksum=u16(0),
            module_id=u16(2),
            part_number=u32(4),
            design_level_suffix=u16(8),
            header_utility_type=u16(10),
            interpreter_type=u16(12),
            offset_to_routines=u16(14),
            addressing_type=u16(16),
            data_address_info=u32(18),
            num_data_bytes_msg=u16(22),
        )


@dataclass(frozen=True)
class Instruction:
    step: int
    opcode: int
    action: Tuple[int, int, int, int]  # AC0..AC3
    gotos: List[Tuple[int, int]]       # (G0,G1)...(G8,G9)
    raw: bytes

    @staticmethod
    def parse(buf16: bytes) -> "Instruction":
        if len(buf16) != 16:
            raise ValueError("Instruction record must be exactly 16 bytes.")
        step = buf16[0]
        opcode = buf16[1]
        action = tuple(buf16[2:6])
        gotos = [(buf16[i], buf16[i + 1]) for i in range(6, 16, 2)]
        return Instruction(step=step, opcode=opcode, action=action, gotos=gotos, raw=buf16)


def explain_action(interpreter_type: int, opcode: int, ac: Tuple[int, int, int, int]) -> Optional[str]:
    """Lightweight decoding for common patterns. Extend per op-code definitions if needed."""
    ac0, ac1, ac2, ac3 = ac
    u16 = lambda a, b: (a << 8) | b
    if opcode == 0x50:
        # 0x50 Compare Bytes:
        # Compare 2 bytes stored in 2-byte buffer ID=AC0 against literal bytes AC1(high), AC2(low). AC3 unused.
        return f"compare storage2[id=0x{ac0:02X}] == 0x{u16(ac1, ac2):04X}"
    if opcode == 0x53:
        # 0x53 Compare Data:
        # Compares up to 256 bytes of stored info (buffer AC0) against:
        #   - internal data (VIT2) selected by AC1 (AC3=00), OR
        #   - data from routine AC1 (AC3=01), OR
        #   - another 256-byte storage buffer AC1 (AC3=02).
        #
        # AC2 conversion:
        #   00 = not used
        #   01 = ASCII -> 4-byte USN
        #
        # Spec: AC0 is 0x00..0x13 (256-byte buffers).
        conv = {0x00: "none", 0x01: "ASCII->u32(USN)"}.get(ac2, f"0x{ac2:02X}")

        if ac3 == 0x00:
            rhs = f"internal(VIT2)[id=0x{ac1:02X}]"
        elif ac3 == 0x01:
            rhs = f"routine[id=0x{ac1:02X}]"
        elif ac3 == 0x02:
            rhs = f"storage256[id=0x{ac1:02X}]"
        else:
            rhs = f"unknown_source(ac3=0x{ac3:02X}, ac1=0x{ac1:02X})"

        return f"compare storage256[id=0x{ac0:02X}] with {rhs} (conv={conv})"
    if opcode == 0x54:
        # 0x54 Change Data (Common / supported by Class2-1 and GMLAN-3)
        # Spec (pp.183-184): manipulates bytes within a 256-byte storage buffer (AC0),
        # or loads routine/internal data into it, or copies one buffer to another.
        # Note: flow always continues via G1. :contentReference[oaicite:5]{index=5}

        op = ac2

        ops = {
            0x00: "EQUAL",
            0x01: "AND",
            0x02: "OR",
            0x03: "XOR",
            0x04: "SHL",  # byte shift left, fill with 0
            0x05: "SHR",  # byte shift right, fill with 0
            0x06: "LOAD_ROUTINE",
            0x07: "LOAD_INTERNAL",  # plant programming only
            0x08: "COPY_BUFFER",
        }

        # Internal data specifiers valid for AC2==0x07 (per spec)
        internal_names = {
            0x41: "VIN",
            0x44: "TireType",
            0x45: "TPM_placard",
            0x46: "Diesel_Inj_Adjust(IMA/IQA)",
            0x47: "TransferCase_BCal",
            0x48: "KeyFob_Data",
            0x49: "Engine_Serial_Number",
        }

        buf = f"storage256[id=0x{ac0:02X}]"

        if op == 0x08:
            # Copy full buffer AC1 -> AC0 :contentReference[oaicite:6]{index=6}
            return f"copy storage256[id=0x{ac1:02X}] -> {buf}"

        if op == 0x06:
            # Load routine AC1 into buffer AC0 (max 256 bytes) :contentReference[oaicite:7]{index=7}
            return f"load routine[id=0x{ac1:02X}] -> {buf} (max 256 bytes)"

        if op == 0x07:
            # Load internal data (plant only) :contentReference[oaicite:8]{index=8}
            name = internal_names.get(ac1, f"0x{ac1:02X}")
            extra = ""
            # AC3 meaning for some internal data specifiers :contentReference[oaicite:9]{index=9}
            if ac1 == 0x46:
                extra = f", cylinder={ac3} (0=all)"
            elif ac1 == 0x48:
                extra = f", key_fob={ac3} (0=all)"
            elif ac3 != 0x00:
                extra = f", ac3=0x{ac3:02X}"
            return f"load internal[{name}] -> {buf} (plant-only){extra}"

        # Byte/bit operations: AC1 = byte index, AC3 = mask/value when AC2 < 04 :contentReference[oaicite:10]{index=10} :contentReference[oaicite:11]{index=11}
        if op in (0x00, 0x01, 0x02, 0x03):
            opname = ops[op]
            idx = ac1  # zero-based byte position
            val = ac3
            if op == 0x00:
                # EQUAL: set byte to value
                return f"{buf}[{idx}] = 0x{val:02X} ({opname})"
            if op == 0x01:
                return f"{buf}[{idx}] &= 0x{val:02X} ({opname})"
            if op == 0x02:
                return f"{buf}[{idx}] |= 0x{val:02X} ({opname})"
            # op == 0x03
            return f"{buf}[{idx}] ^= 0x{val:02X} ({opname})"

        # Shift operations: AC1 = number of bytes to shift :contentReference[oaicite:12]{index=12}
        if op in (0x04, 0x05):
            opname = ops[op]
            count = ac1
            direction = "left" if op == 0x04 else "right"
            return f"shift {buf} {direction} by {count} bytes, fill=0 ({opname})"

        # Fallback
        return f"change_data {buf}, ac1=0x{ac1:02X}, op=0x{op:02X}, ac3=0x{ac3:02X}"

    if interpreter_type == 3 and opcode == 0xFB:
        # FB Set and Decrement Counter (GMLAN)
        # Counters start/reset at 0xFF; on first use load AC1 then decrement immediately. :contentReference[oaicite:5]{index=5}
        note = "AC1 should be > 1 (decrement happens before branch)"  # :contentReference[oaicite:6]{index=6}
        return f"counter_id=0x{ac0:02X}, loop_limit={ac1} ({note})"

    if interpreter_type == 3 and opcode == 0xFC:
        # FC Delay (GMLAN)
        unit = "seconds" if ac3 == 0x00 else ("minutes" if ac3 == 0x01 else f"unit=0x{ac3:02X}")
        # For Class 2, AC1 controls tester-present; for others (incl. GMLAN) AC1 not used and tester-present sent by default. :contentReference[oaicite:7]{index=7}
        tp = "tester_present=default(on)" if ac1 == 0 else f"tester_present=default(on); AC1=0x{ac1:02X} ignored"
        return f"delay={ac0} {unit}, {tp}"
    
    if interpreter_type == 3 and opcode == 0x22:
        # 0x22 Mode 22 Read Data by Parameter Identifier (PID):
        # AC0: PID high byte
        # AC1: PID low byte
        # AC2: storage location ID (0x00–0x13)
        # AC3: 00=use 256-byte buffer, 01=use 2-byte buffer
        pid = u16(ac0, ac1)
        if ac3 == 0x01:
            buf = "2-byte"
        elif ac3 == 0x00:
            buf = "256-byte"
        else:
            buf = f"unknown(0x{ac3:02X})"
        return f"PID=0x{pid:04X}, store_id=0x{ac2:02X}, buf={buf}"
    if interpreter_type == 3 and opcode == 0x01:
        return f"target_id=0x{ac0:02X}, source_id=0x{ac1:02X}"
    if interpreter_type == 3 and opcode == 0xA2:
        return f"report_programmed_state: save resp.byte2 -> storage2[id=0x{ac0:02X}]. Unused: ac1=0x{ac1:02X}, ac2=0x{ac2:02X}, ac3=0x{ac3:02X}"
    if interpreter_type == 3 and opcode == 0x1A:
        return f"DID=0x{ac0:02X}, storage{256 if ac3 == 0 else 2}[id=0x{ac1:02X}]"
    if interpreter_type == 3 and opcode == 0x3B:
        # Mode 3B Write Data by Identifier (GMLAN Interpreter 3)
        did = ac0
        did_name = GMLAN_DID_NAMES.get(did, "(unknown DID)")
        hi, lo = (ac3 >> 4) & 0xF, ac3 & 0xF
        expected_pos = (opcode + 0x40) & 0xFF  # typical goto uses 0x7B for 0x3B :contentReference[oaicite:8]{index=8}

        if ac3 == 0x00:
            src = "VIT internal data by DID (AC0)"
        elif ac3 == 0x03:
            spec_name = GMLAN_INTERNAL_DATA_SPECIFIERS.get(ac1, "(unknown spec)")
            extra = ""
            if ac1 == 0x46:
                extra = f", cylinder={ac2} (0=all)"
            elif ac1 == 0x48:
                extra = f", key_fob={ac2} (0=all)"
            src = f"VIT internal data by specifier AC1=0x{ac1:02X} {spec_name} (plant-only){extra}"
        elif ac3 == 0x10:
            src = f"routine AC1=0x{ac1:02X} provides data; DID from AC0"
        elif ac3 == 0x11:
            src = f"routine AC1=0x{ac1:02X} provides data; DID is first routine byte"
        elif ac3 == 0x22:
            src = f"calibration file AC2=0x{ac2:02X} (multiple DIDs; skip GlobalHeaderLength)"
        elif hi == 0x3:
            src = f"stored bytes id=0x{ac1:02X} (supported 0x00..0x13), count={ac2} (max 256)"
        elif hi == 0x4:
            src = "VIN digits 10-17 from internal data (simulate pos resp if all 0x00)"
        else:
            src = f"INVALID/unsupported AC3=0x{ac3:02X}"

        return (
            f"DID=0x{did:02X} ({did_name}), AC3=0x{ac3:02X} (hi=0x{hi:X}, lo=0x{lo:X}), "
            f"src={src}, expected_pos_rsp=0x{expected_pos:02X}"
        )
    if interpreter_type == 3 and opcode == 0x25:
        # 0x25 Op-Code: Mode AE Security Code (GMLAN Interpreter 3)
        # AC0: CPID number
        # AC1: Device Control:
        #   0x80 = Enter (e.g. unlock ECU)
        #   0x40 = Program security code (write security code)
        #   0x20 = Reset security code (write default security code)
        # AC2: 0x01 = Security Code 1 (vehicle security code)
        #      0x02 = Security Code 2 (unlock ECU with different code)
        # AC3: 0x01 = Security Code Format ASCII (default)
        # Note: security code bytes come from SPS(VIT2) or DPS(manual entry). :contentReference[oaicite:2]{index=2}

        dc = {0x80: "enter/unlock", 0x40: "program", 0x20: "reset"}.get(ac1, f"unknown(0x{ac1:02X})")
        sc = {0x01: "SecurityCode1(vehicle)", 0x02: "SecurityCode2(ecu)"}\
            .get(ac2, f"unknown(0x{ac2:02X})")
        fmt = "ASCII" if ac3 == 0x01 else f"unknown(0x{ac3:02X})"

        return f"modeAE security_code: cpid=0x{ac0:02X}, control={dc}, select={sc}, format={fmt}"
    if interpreter_type == 3 and opcode == 0x27:
        return f"security_algo=0x{ac0:02X}, level=0x{ac1:02X}"
    if interpreter_type == 3 and opcode == 0x34:
        # 0x34 Mode 34 Request Download (GMLAN Interpreter 3):
        # AC0: Data Format Identifier
        #   00 = unencrypted, uncompressed
        #   01..FF = high nibble: compression method, low nibble: encrypting method
        # AC1: Routine / Calibration Number
        # AC2: 00 = not used
        # AC3: Exceptions (nibble coded)
        #   high nibble:
        #     0 = use length from routine AC1 (2 bytes)
        #     1 = use length from utility file header (2 bytes)
        #     2 = use global length (see F2) (4 bytes)
        #     3 = use length based on calibration file AC1 size (4 bytes)
        #   low nibble:
        #     0 = use TypeOfAddressing bytes for length size
        #     2/3/4 = use 2/3/4 bytes for length size

        df = ac0
        if df == 0x00:
            df_desc = "uncompressed+unencrypted"
        else:
            df_desc = f"comp=0x{(df >> 4) & 0xF:X}, enc=0x{df & 0xF:X}"

        hi = (ac3 >> 4) & 0xF
        lo = ac3 & 0xF

        len_src = {
            0x0: "routine(AC1), 2B",
            0x1: "utility_header, 2B",
            0x2: "global_length(F2), 4B",
            0x3: "cal_file_size(AC1), 4B",
        }.get(hi, f"hi_nibble=0x{hi:X}")

        len_size = "TypeOfAddressing" if lo == 0x0 else f"{lo} bytes"

        return (
            f"dataFormat=0x{df:02X} ({df_desc}), "
            f"routine/cal=0x{ac1:02X}, "
            f"AC2=0x{ac2:02X} (unused), "
            f"len_src={len_src}, len_size={len_size}"
        )
    if interpreter_type == 3 and opcode == 0xB0:
        # GMLAN Interpreter 3 - B0 Op-Code: Mode 36 Block Transfer to RAM
        # Action fields per spec:
        #   AC0: Calibration ID (00 = not used; 01..FF = calibration ID)
        #   AC1: Routine Number
        #   AC2: Exceptions (nibble-coded)
        #       high nibble: 0=Download, 1=Download+Execute, 2=Execute Only (no data bytes)
        #       low  nibble: 0=Increment address, 1=Keep address constant
        #   AC3: Exceptions (nibble-coded)
        #       high nibble: 0=Use routine address(AC1), 1=Use header address, 2=Use global address(F1)
        #       low  nibble: 0=Use TypeOfAddressing (header), 2=2 bytes, 3=3 bytes, 4=4 bytes

        cal_id = ac0
        routine_no = ac1

        ac2_hi = (ac2 >> 4) & 0xF
        ac2_lo = ac2 & 0xF
        ac3_hi = (ac3 >> 4) & 0xF
        ac3_lo = ac3 & 0xF

        transfer_kind = {
            0x0: "download",
            0x1: "download_and_execute",
            0x2: "execute_only(no_data)",
        }.get(ac2_hi, f"unknown(0x{ac2_hi:X})")

        addr_update = {
            0x0: "increment",
            0x1: "constant",
        }.get(ac2_lo, f"unknown(0x{ac2_lo:X})")

        addr_src = {
            0x0: "routine_addr(AC1)",
            0x1: "header_addr",
            0x2: "global_addr(F1)",
        }.get(ac3_hi, f"unknown(0x{ac3_hi:X})")

        addr_len = {
            0x0: "typeOfAddressing(header)",
            0x2: "2_bytes",
            0x3: "3_bytes",
            0x4: "4_bytes",
        }.get(ac3_lo, f"unknown(0x{ac3_lo:X})")

        parts = []
        parts.append("cal_id=0x00(unused)" if cal_id == 0 else f"cal_id=0x{cal_id:02X}")
        parts.append(f"routine_no=0x{routine_no:02X}")
        parts.append(f"op={transfer_kind}")
        parts.append(f"addr_update={addr_update}")
        parts.append(f"addr_src={addr_src}")
        parts.append(f"addr_len={addr_len}")

        return ", ".join(parts)

    if interpreter_type == 3 and opcode == 0xAE:
        return f"cpid=0x{ac0:02X}, routine_no=0x{ac1:02X}. Unused: ac2=0x{ac2:02X} ac3=0x{ac3:02X}"

    return None


def decompile_utility_bytes(buf: bytes, filename: str = "<memory>") -> str:
    h = UtilityHeader.parse(buf[:24])
    interp_name = INTERPRETER_NAMES.get(h.interpreter_type, f"Unknown({h.interpreter_type})")
    part2_step = h.header_utility_type if (h.interpreter_type == 3 and h.header_utility_type != 0) else None

    start = 24
    end = min(h.offset_to_routines, len(buf))
    instr_area = buf[start:end]
    n = len(instr_area) // 16

    lines: List[str] = []
    lines.append("=== GM SPS Utility File Decompile ===")
    lines.append(f"Input file: {filename}")
    lines.append(f"File size: {len(buf)} bytes")
    lines.append("")
    lines.append("Header (24 bytes):")
    lines.append(f"  checksum (0x00-0x01):        0x{h.checksum:04X}")
    lines.append(f"  module_id (0x02-0x03):       0x{h.module_id:04X}")
    lines.append(f"  part_number (0x04-0x07):     0x{h.part_number:08X}")
    lines.append(f"  design_level (0x08-0x09):    0x{h.design_level_suffix:04X}")
    if part2_step is not None:
        lines.append(f"  header/utility (0x0A-0x0B):  0x{h.header_utility_type:04X}  (GMLAN part 2 starts at step 0x{part2_step:02X})")
    else:
        lines.append(f"  header/utility (0x0A-0x0B):  0x{h.header_utility_type:04X}")
    lines.append(f"  interpreter (0x0C-0x0D):     0x{h.interpreter_type:04X}  ({interp_name})")
    lines.append(f"  offset_to_routines:          0x{h.offset_to_routines:04X} ({h.offset_to_routines} dec)")
    lines.append(f"  TypeOfAddressing:            0x{h.addressing_type:04X}")
    lines.append(f"  data_address_info:           0x{h.data_address_info:08X}")
    nd = h.num_data_bytes_msg
    if nd > 0x0100 and (nd & 0x00FF) == 0:
        lines.append(f"  bytes_per_message:           0x{nd:04X}  (suspicious; if swapped -> {nd >> 8})")
    else:
        lines.append(f"  bytes_per_message:           0x{nd:04X} ({nd} dec)")
    lines.append("")
    if len(instr_area) % 16 != 0:
        lines.append(f"WARNING: interpreter section length {len(instr_area)} is not a multiple of 16; trailing bytes exist.")
    lines.append(f"Interpreter instructions: {n} lines (0x{start:04X}..0x{end-1:04X})")
    lines.append("")

    for i in range(n):
        rec = instr_area[i * 16 : (i + 1) * 16]
        ins = Instruction.parse(rec)
        if part2_step is not None and ins.step == part2_step:
            lines.append(f"--- Part 2 begins at step 0x{part2_step:02X} ---")

        name = opcode_name(h.interpreter_type, ins.opcode)
        ac0, ac1, ac2, ac3 = ins.action

        raw = ins.raw.hex().upper()
        lines.append(
            f"{raw[0:2]}    "
            f"{raw[2:4]}    "
            f"{bytes_spaced(raw[4:12])}    "
            f"{bytes_spaced(raw[12:32])}"
        )
        lines.append(f"    OP: 0x{ins.opcode:02X} - {name}")

        extra = explain_action(h.interpreter_type, ins.opcode, ins.action)
        if extra:
            lines.append(f"    AC: [{ac0:02X} {ac1:02X} {ac2:02X} {ac3:02X}]  ({extra})")
        else:
            lines.append(f"    AC: [{ac0:02X} {ac1:02X} {ac2:02X} {ac3:02X}]  (u32=0x{int.from_bytes(bytes(ins.action),'big'):08X})")
        lines.append("    GOTO: " + format_gotos(h.interpreter_type, ins.opcode, ins.gotos))

    # Routine section (address+length+data repeating)
    lines.append("")
    lines.append(f"Routine section @0x{h.offset_to_routines:04X}: {len(buf) - h.offset_to_routines} bytes")
    rbuf = buf[h.offset_to_routines:]
    off = 0
    idx = 0
    while off < len(rbuf):
        if off + 6 > len(rbuf):
            lines.append(f"  [trailing] {len(rbuf)-off} bytes: {rbuf[off:].hex().upper()}")
            break
        addr = int.from_bytes(rbuf[off : off + 4], "big")
        ln = int.from_bytes(rbuf[off + 4 : off + 6], "big")
        off += 6
        idx += 1
        if off + ln > len(rbuf):
            lines.append(f"  routine #{idx}: addr=0x{addr:08X}, len={ln} (TRUNCATED)")
            lines.append(f"    data: {rbuf[off:].hex().upper()}")
            break
        dat = rbuf[off : off + ln]
        off += ln
        lines.append(f"  routine #{idx}: addr=0x{addr:08X}, len={ln}")
        lines.append(f"    data: {dat.hex().upper()}")

    return "\n".join(lines)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Decompile a GM SPS utility file into a readable listing.")
    ap.add_argument("file", help="Path to the binary utility file")
    ap.add_argument("-o", "--out", help="Optional output text file")
    args = ap.parse_args()

    p = Path(args.file)
    buf = p.read_bytes()
    out = decompile_utility_bytes(buf, filename=p.name)

    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
