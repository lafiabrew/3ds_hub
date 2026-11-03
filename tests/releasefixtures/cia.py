"""Original synthetic archive layout, NOT executable/retail/signature material."""
import hashlib
import struct


def cia(title='0004000000d3e703', product='CTR-P-PADT'):
    title = bytes.fromhex(title)
    ncch = bytearray(0x1000)
    ncch[0x100:0x104] = b'NCCH'
    struct.pack_into('<I', ncch, 0x104, len(ncch) // 0x200)
    ncch[0x108:0x110] = title[::-1]
    ncch[0x118:0x120] = title[::-1]
    ncch[0x150:0x150+len(product)] = product.encode()
    struct.pack_into('<I', ncch, 0x180, 0x400)
    ncch[0x18f] = 4
    ncch[0x400:0x408] = title[::-1]
    struct.pack_into('<II', ncch, 0x1a0, 5, 3)
    ticket = bytearray(0x350)
    ticket[:4] = bytes.fromhex('00010004')
    ticket[0x140+0x9c:0x140+0xa4] = title
    tmd = bytearray(0xb34)
    tmd[:4] = bytes.fromhex('00010004')
    tmd[0x140+0x4c:0x140+0x54] = title
    struct.pack_into('>H', tmd, 0x140+0x9e, 1)
    record = 0x140 + 0x9c4
    struct.pack_into('>IHHQ', tmd, record, 0, 0, 0, len(ncch))
    tmd[record+16:record+48] = hashlib.sha256(ncch).digest()
    header = bytearray(0x2020)
    struct.pack_into('<IHHIIIIQ', header, 0, len(header), 0, 0, 0xa00, len(ticket), len(tmd), 0, len(ncch))
    header[0x20] = 0x80
    pad = lambda b: bytes(b) + bytes((-len(b)) % 64)
    return pad(header) + pad(bytes(0xa00)) + pad(ticket) + pad(tmd) + bytes(ncch)


def smdh():
    return b'SMDH' + bytes(0x36c0 - 4)


def threedsx():
    data = bytearray(64)
    data[:4] = b'3DSX'
    struct.pack_into('<HH', data, 4, 32, 8)
    struct.pack_into('<IIII', data, 16, 32, 0, 0, 0)
    return data
