#!/usr/bin/env python3
"""
make-touchpad-dtbo.py — produce the gts7xlwifi dtbo with the Book Cover Keyboard
trackpad orientation fixed for Droidian's landscape coordinate system.

The Tab S7+ stock dtbo (an Android d7b7ab1e dt_table) sets, on the pogo_touchpad
(stm32_tpd / sec_touchpad_pogo) node:  touchpad,invert = <0 1 1>  (x_invert=0,
y_invert=1, xy_switch=1). That's correct for Samsung Android's orientation but on
Droidian (landscape-native) it rotates the trackpad 90deg (finger-up -> cursor-right).
The fix is identity:  touchpad,invert = <0 0 0>.  This patches every board-revision
FDT in the table that has the property, then re-adds the AVB hash footer matching the
stock dtbo (partition_name=dtbo, partition_size=10485760, SHA256_RSA4096, AOSP testkey),
so the BL accepts it under vbmeta flags=0x02.

Everything else (incl. secdp,redrv = "ps5169" for the DP re-driver) is left untouched.

Usage:
  python3 make-touchpad-dtbo.py <stock_dtbo.img> <out_dtbo.img> [--key testkey_rsa4096.pem]
Requires: dtc, avbtool in PATH; testkey next to this script (or via --key).
"""
import struct, subprocess, sys, os, argparse, tempfile

OLD = "touchpad,invert = <0x00 0x01 0x01>"   # stock <0 1 1>
NEW = "touchpad,invert = <0x00 0x00 0x00>"   # identity <0 0 0> (landscape-correct)
PART_SIZE = 10485760   # gts7xlwifi dtbo partition size

def align(x, a=4096): return (x + a - 1) // a * a

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stock"); ap.add_argument("out")
    ap.add_argument("--key", default=os.path.join(os.path.dirname(__file__), "..", "testkey_rsa4096.pem"))
    a = ap.parse_args()
    d = open(a.stock, "rb").read()
    magic, total, hsz, esz, ecnt, eoff, psz, ver = struct.unpack(">IIIIIIII", d[:32])
    assert magic == 0xd7b7ab1e, "not an Android dt_table dtbo"
    ents = [struct.unpack(">II", d[eoff + i*esz: eoff + i*esz + 8]) + (d[eoff + i*esz + 8: eoff + i*esz + esz],) for i in range(ecnt)]
    tmp = tempfile.mkdtemp()
    new, changed = [], 0
    for i, (sz, off, rest) in enumerate(ents):
        fdt = d[off:off + sz]
        fi = os.path.join(tmp, f"i{i}.dtb"); open(fi, "wb").write(fdt)
        dts = subprocess.run(["dtc", "-I", "dtb", "-O", "dts", fi], capture_output=True).stdout.decode("utf-8", "replace")
        if OLD in dts:
            dts = dts.replace(OLD, NEW); changed += 1
            fo = os.path.join(tmp, f"o{i}.dtb")
            subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", fo], input=dts.encode(), capture_output=True)
            new.append(open(fo, "rb").read())
        else:
            new.append(fdt)
    he = 32 + ecnt*esz; cur = align(he); eb = bytearray(); fa = bytearray()
    for i, fdt in enumerate(new):
        eb += struct.pack(">II", len(fdt), cur) + ents[i][2]
        fa += fdt + b"\x00" * (align(len(fdt)) - len(fdt)); cur += align(len(fdt))
    out = struct.pack(">IIIIIIII", magic, cur, hsz, esz, ecnt, eoff, psz, ver) + eb
    out += b"\x00" * (align(he) - len(out)); out += fa
    open(a.out, "wb").write(out)
    subprocess.run(["avbtool", "add_hash_footer", "--image", a.out, "--partition_name", "dtbo",
                    "--partition_size", str(PART_SIZE), "--algorithm", "SHA256_RSA4096",
                    "--key", a.key, "--rollback_index", "0"], check=True)
    print(f"OK: {a.out}  (patched {changed} FDTs, signed, {os.path.getsize(a.out)} bytes)")

if __name__ == "__main__":
    main()
