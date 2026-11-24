#!/usr/bin/env python3
"""make_dex.py — hand-rolled Dalvik DEX writer.

Генерирует classes.dex для MainActivity оболочки «Заметки»:
  class Lcom/zametki/notes/MainActivity; extends Landroid/app/Activity;
  <init>()V                     — вызывает super()
  onCreate(Landroid/os/Bundle;)V — WebView(file:///android_asset/index.html),
                                    JS + DOM storage включены.

DEX: magic dex\n035\0, little-endian, checksums (adler32 + sha1) вычисляются
корректно. Порядок секций id — по спецификации dex-format (string_ids по
содержимому, type_ids по индексу дескриптора, proto_ids по (ret, params),
method_ids по (class, name, proto)). Строки ASCII => MUTF-8 == UTF-8.
"""
import hashlib
import struct
import sys
import zlib

# ---------------------------------------------------------------- primitives


def uleb128(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def mutf8(s: str) -> bytes:
    out = bytearray()
    for ch in s:
        cp = ord(ch)
        if cp == 0:
            out += b"\xc0\x80"
        elif cp < 0x80:
            out.append(cp)
        elif cp < 0x800:
            out.append(0xC0 | (cp >> 6))
            out.append(0x80 | (cp & 0x3F))
        else:
            out.append(0xE0 | (cp >> 12))
            out.append(0x80 | ((cp >> 6) & 0x3F))
            out.append(0x80 | (cp & 0x3F))
    return bytes(out)


def align(buf: bytearray, n: int) -> None:
    while len(buf) % n:
        buf.append(0)


# ---------------------------------------------------------------- dex model

# Типы (дескрипторы)
ACT = "Landroid/app/Activity;"
CTX = "Landroid/content/Context;"
BND = "Landroid/os/Bundle;"
VIW = "Landroid/view/View;"
WST = "Landroid/webkit/WebSettings;"
WVW = "Landroid/webkit/WebView;"
MNC = "Lcom/zametki/notes/MainActivity;"
STR = "Ljava/lang/String;"
V = "V"
Z = "Z"

URL = "file:///android_asset/index.html"

# Методы: (class, name, proto) где proto = (shorty, ret, [params])
P_VOID = ("V", V, ())
P_BUNDLE = ("VL", V, (BND,))
P_VIEW = ("VL", V, (VIW,))
P_Z = ("VZ", V, (Z,))
P_CTX = ("VL", V, (CTX,))
P_WS = ("L", WST, ())
P_STR = ("VL", V, (STR,))

METHODS = [
    (ACT, "<init>", P_VOID),                      # super()
    (ACT, "onCreate", P_BUNDLE),                  # invoke-super
    (ACT, "setContentView", P_VIEW),              # invoke-virtual
    (WST, "setDomStorageEnabled", P_Z),
    (WST, "setJavaScriptEnabled", P_Z),
    (WVW, "<init>", P_CTX),
    (WVW, "getSettings", P_WS),
    (WVW, "loadUrl", P_STR),
    (MNC, "<init>", P_VOID),                      # наш конструктор
    (MNC, "onCreate", P_BUNDLE),                  # объявленный override
]


# ---- Полная пересборка с корректным layout (type_list в data) ----

def build() -> bytes:
    strings: set[str] = set()
    for d in (ACT, CTX, BND, VIW, WST, WVW, MNC, STR, V, Z):
        strings.add(d)
    for _, name, (shorty, ret, params) in METHODS:
        strings.add(name)
        strings.add(shorty)
        strings.add(ret)
    strings.add(URL)

    str_list = sorted(strings, key=mutf8)
    sidx = {s: i for i, s in enumerate(str_list)}

    type_descs = sorted({ACT, CTX, BND, VIW, WST, WVW, MNC, STR, V, Z},
                        key=lambda d: sidx[d])
    tidx = {d: i for i, d in enumerate(type_descs)}

    protos = {(s, r, tuple(p)) for _, _, (s, r, p) in METHODS}
    proto_list = sorted(protos, key=lambda p: (tidx[p[1]], tuple(tidx[x] for x in p[2])))
    pidx = {p: i for i, p in enumerate(proto_list)}

    method_list = sorted({m for m in METHODS},
                         key=lambda m: (tidx[m[0]], sidx[m[1]], pidx[m[2]]))
    midx = {m: i for i, m in enumerate(method_list)}

    def uleb(n):
        return uleb128(n)

    def code_item(regs, ins, outs, insns):
        b = bytearray(struct.pack("<HHHHII", regs, ins, outs, 0, 0, len(insns)))
        for u in insns:
            b += struct.pack("<H", u & 0xFFFF)
        if len(insns) % 2:
            b += b"\x00\x00"
        return bytes(b)

    mi = lambda m: midx[m]
    ti = lambda d: tidx[d]

    onCreate_insns = [
        0x206E, mi((ACT, "onCreate", P_BUNDLE)), 0x0054,
        0x0022, ti(WVW),
        0x206F, mi((WVW, "<init>", P_CTX)), 0x0040,
        0x106E, mi((WVW, "getSettings", P_WS)), 0x0000,
        0x010A,
        0x1212,
        0x206E, mi((WST, "setDomStorageEnabled", P_Z)), 0x0021,
        0x206E, mi((WST, "setJavaScriptEnabled", P_Z)), 0x0021,
        0x011A, sidx[URL],
        0x206E, mi((WVW, "loadUrl", P_STR)), 0x0010,
        0x206E, mi((ACT, "setContentView", P_VIEW)), 0x0004,
        0x000E,
    ]
    init_insns = [
        0x106F, mi((ACT, "<init>", P_VOID)), 0x0000,
        0x000E,
    ]
    code_init = code_item(1, 1, 1, init_insns)
    code_create = code_item(6, 2, 2, onCreate_insns)

    # type_list для каждого прототипа с параметрами (4-aligned)
    type_lists = {}
    for p in proto_list:
        if p[2]:
            tl = struct.pack("<I", len(p[2])) + b"".join(
                struct.pack("<H", tidx[x]) for x in p[2])
            if len(p[2]) % 2:
                tl += b"\x00\x00"
            type_lists[p] = tl

    # class_data
    init_idx = midx[(MNC, "<init>", P_VOID)]
    create_idx = midx[(MNC, "onCreate", P_BUNDLE)]

    # layout
    n_str, n_type, n_proto, n_meth = len(str_list), len(type_descs), len(proto_list), len(method_list)
    off = 0x70
    string_ids_off = off; off += 4 * n_str
    type_ids_off = off; off += 4 * n_type
    proto_ids_off = off; off += 12 * n_proto
    field_ids_off = off
    method_ids_off = off; off += 8 * n_meth
    class_defs_off = off; off += 32
    data_off = off

    # data: type_lists (в порядке proto_list), string_data, code, class_data, map
    tl_offs = {}
    for p in proto_list:
        if p in type_lists:
            while off % 4:
                off += 1
            tl_offs[p] = off
            off += len(type_lists[p])

    str_data_offs = []
    for s in str_list:
        str_data_offs.append(off)
        off += len(uleb(len(s))) + len(mutf8(s)) + 1

    while off % 4:
        off += 1
    code_init_off = off; off += len(code_init)
    while off % 4:
        off += 1
    code_create_off = off; off += len(code_create)

    class_data_off = off
    class_data = (
        uleb(0) + uleb(0) + uleb(1) + uleb(1)
        + uleb(init_idx) + uleb(0x10001) + uleb(code_init_off)
        + uleb(create_idx) + uleb(0x4) + uleb(code_create_off)
    )
    off += len(class_data)
    while off % 4:
        off += 1
    map_off = off

    map_entries = [
        (0x0000, 1, 0),
        (0x0001, n_str, string_ids_off),
        (0x0002, n_type, type_ids_off),
        (0x0003, n_proto, proto_ids_off),
        (0x0005, n_meth, method_ids_off),
        (0x0006, 1, class_defs_off),
    ]
    # data-часть: type_lists (0x1c00) потом string_data, code, class_data
    for p in proto_list:
        if p in type_lists:
            map_entries.append((0x1001, 1, tl_offs[p]))
    map_entries.append((0x2002, n_str, str_data_offs[0]))
    map_entries.append((0x2001, 2, code_init_off))
    map_entries.append((0x2000, 1, class_data_off))
    map_entries.append((0x1000, 1, map_off))
    # сортировка по смещению
    map_entries.sort(key=lambda e: e[2])
    map_size = 4 + 12 * len(map_entries)
    file_size = map_off + map_size

    buf = bytearray()
    hdr = bytearray()
    hdr += b"dex\n035\x00"
    hdr += b"\x00" * 24  # checksum + signature
    hdr += struct.pack("<II", file_size, 0x70)
    hdr += struct.pack("<III", 0x12345678, 0, 0)  # endian, link_size, link_off
    hdr += struct.pack("<I", map_off)
    hdr += struct.pack("<II", n_str, string_ids_off)
    hdr += struct.pack("<II", n_type, type_ids_off)
    hdr += struct.pack("<II", n_proto, proto_ids_off)
    hdr += struct.pack("<II", 0, field_ids_off)
    hdr += struct.pack("<II", n_meth, method_ids_off)
    hdr += struct.pack("<II", 1, class_defs_off)
    hdr += struct.pack("<II", 0, 0)  # data_size, data_off
    assert len(hdr) == 0x70
    buf += hdr

    assert len(buf) == string_ids_off
    for i, s in enumerate(str_list):
        buf += struct.pack("<I", str_data_offs[i])
    for d in type_descs:
        buf += struct.pack("<I", sidx[d])
    for shorty, ret, params in proto_list:
        buf += struct.pack("<III", sidx[shorty], tidx[ret],
                           tl_offs.get((shorty, ret, tuple(params)), 0))
    assert len(buf) == method_ids_off
    for cls, name, (shorty, ret, params) in method_list:
        buf += struct.pack("<HHI", tidx[cls], pidx[(shorty, ret, tuple(params))], sidx[name])
    assert len(buf) == class_defs_off
    buf += struct.pack(
        "<IIIIIIII",
        tidx[MNC], 0x1, tidx[ACT], 0,
        0xFFFFFFFF, 0, class_data_off, 0,
    )
    assert len(buf) == data_off

    # data: type_lists, string_data, code, class_data, map
    cur = len(buf)
    for p in proto_list:
        if p in type_lists:
            while len(buf) % 4:
                buf.append(0)
            assert len(buf) == tl_offs[p]
            buf += type_lists[p]
    for i, s in enumerate(str_list):
        assert len(buf) == str_data_offs[i]
        buf += uleb(len(s)) + mutf8(s) + b"\x00"
    while len(buf) % 4:
        buf.append(0)
    assert len(buf) == code_init_off
    buf += code_init
    while len(buf) % 4:
        buf.append(0)
    assert len(buf) == code_create_off
    buf += code_create
    assert len(buf) == class_data_off
    buf += class_data
    while len(buf) % 4:
        buf.append(0)
    assert len(buf) == map_off
    buf += struct.pack("<I", len(map_entries))
    for t, sz, o in map_entries:
        buf += struct.pack("<HHII", t, 0, sz, o)

    assert len(buf) == file_size, (len(buf), file_size)

    # checksums
    sig = hashlib.sha1(bytes(buf[32:])).digest()
    buf[12:32] = sig
    checksum = zlib.adler32(bytes(buf[12:])) & 0xFFFFFFFF
    struct.pack_into("<I", buf, 8, checksum)
    return bytes(buf)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "classes.dex"
    data = build()
    with open(out, "wb") as f:
        f.write(data)
    print(f"wrote {out}: {len(data)} bytes")
    # самопроверка
    assert data[:8] == b"dex\n035\x00"
    assert zlib.adler32(data[12:]) & 0xFFFFFFFF == struct.unpack_from("<I", data, 8)[0]
    assert hashlib.sha1(data[32:]).digest() == data[12:32]
    print("checksums ok")
