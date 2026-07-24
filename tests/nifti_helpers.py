import struct


def valid_nifti_bytes(payload=b"test data"):
    data = bytearray(352)
    struct.pack_into("<I", data, 0, 348)
    struct.pack_into("<8h", data, 40, 3, 1, 1, max(1, len(payload)), 1, 1, 1, 1)
    struct.pack_into("<h", data, 70, 2)
    struct.pack_into("<h", data, 72, 8)
    struct.pack_into("<f", data, 108, 352.0)
    data[344:348] = b"n+1\x00"
    return bytes(data) + payload

