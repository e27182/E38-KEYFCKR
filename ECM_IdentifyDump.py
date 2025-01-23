import sys
import struct

def read_data(file_path, offset, length):
    """Reads and returns data from the file at the specified offset and length."""
    try:
        with open(file_path, 'rb') as file:
            file.seek(offset)
            return file.read(length)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

def parse_and_display_data(file_path):
    """Parses and displays the requested data from the ECM dump file."""
    try:
        data_points = {
            "3D02:2 - Seed": (0x3D02, 0x2),
            "3D04:2 - Key": (0x3D04, 0x2),
            "3D06:9 - System Supplier Id ($92)": (0x3D06, 0x9),
            "3D1E:4 - Base Model Number ($CC)": (0x3D1E, 0x4),
            "3F20:8 - ???": (0x3F20, 0x8),
            "3D36:A - ???": (0x3D36, 0xA),
            "3D44:4 - ???": (0x3D44, 0x4),
            "3F50:C - C?": (0x3F50, 0xC),
            "3F80:A - MF Code": (0x3F80, 0xA),
            "3FB0:E - Bootloader Version": (0x3FB0, 0xE),
            "3FDA:A - C?": (0x3FDA, 0xA),
            "6118:11 - VIN ($90)": (0x6118, 0x11),
            "10094:C - DID $71": (0x10094, 0xC),
            "10172:C - Software date": (0x10172, 0xC),
            "10184:4 - ID of Base Software": (0x10184, 0x4),
            "13913:8 - Some ID": (0x13913, 0x8),
            "E0000:8 - Hardware ID?": (0xE0000, 0x8),
            "E0040:C - Software ID": (0xE0040, 0xC),
            "E0054:C - ECU ROM ID": (0xE0054, 0xC),
            "E0069:2 - Diagnostic Data Identifier ($9A)": (0xE0069, 0x2),
            "E006D:4 - Software Id ($C2)": (0xE006D, 0x4),
            "E0071:0xD - Calibrations": (0xE0071, 0xD),
            "E007E:0x6 - System Name or Engine Type ($97)": (0xE007E, 0x6),
            "E0084:0x6 - ???": (0xE0084, 0x6),
            "E008A:0xC - Some version?": (0xE008A, 0xC),
            "FEFE2:0xA - Repair Shop Code or SN ($98)": (0xFEFE2, 0xA),
            "FEFEC:0x4 - Programming date ($99)": (0xFEFEC, 0x4),
        }

        print(f"Processing file: {file_path}\n")

        for description, (offset, length) in data_points.items():
            data = read_data(file_path, offset, length)
            if data:
                if isinstance(data, bytes):
                    # Print as hex and ASCII (if printable)
                    hex_repr = ' '.join(f"{b:02X}" for b in data)
                    ascii_repr = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data)
                    int_repr = int.from_bytes(data[0:5], 'big')
                    print(f"{description}:\n  Hex: {hex_repr}\n  Int: {int_repr}\n  ASCII: {ascii_repr}\n")
                else:
                    print(f"{description}: {data}\n")

    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python ECM_IdentifyDump.py <path_to_ecm_dump_file>")
        sys.exit(1)

    ecm_file_path = sys.argv[1]
    parse_and_display_data(ecm_file_path)
