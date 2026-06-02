#!/usr/bin/env python3
"""
build-bootimg.py — turn a raw Droidian/CI boot.img into a Samsung-ABL-acceptable,
bootable boot.img for the Galaxy Tab S7+ Wi-Fi (SM-T970 / gts7xlwifi).

This does the two things that took ~50 flash iterations to discover:
  1. Patch the boot.img v2 header to Samsung-accepted values.
  2. Set a kernel cmdline that (a) the BL accepts and (b) lets the Halium
     initramfs's klibc run-init open /dev/console (console=tty0, NOT console=null).
Then it adds an AVB hash footer (partition_name=boot, AOSP testkey) so Samsung
ABL accepts the unsigned image when the vbmeta partition has flags=0x02.

Usage:
  python3 build-bootimg.py <raw_boot.img> <output.img> [--rescue]

  <raw_boot.img>  the un-footered boot.img from the kernel-deb / CI release
                  (e.g. clang10-boot/extracted/boot/boot.img-4.19.113-samsung-gts7xlwifi)
  --rescue        use console=null instead of console=tty0. This makes the boot
                  DROP INTO the initramfs RNDIS+telnet rescue console (192.168.2.15:23)
                  with the Droidian rootfs mounted rw at /root — used for rootfs surgery.
                  Without --rescue you get the real, fully-booting Droidian image.

Requires: avbtool in PATH, testkey_rsa4096.pem next to this script (or via --key).
"""
import struct, sys, subprocess, os, argparse

# --- Samsung Tab S7+ Wi-Fi constants (verified working) ---
BOOT_PARTITION_SIZE     = 71303168     # /dev/block/by-name/boot
RECOVERY_PARTITION_SIZE = 86888448     # /dev/block/by-name/recovery
ROLLBACK_INDEX          = 1900000000   # >= device fused minimum
RAMDISK_ADDR = 0x02000000  # header offset 20
TAGS_ADDR    = 0x01e00000  # header offset 32
OS_VERSION   = 0x1e000198  # header offset 44  (Android 15 + 2024-12 SPL encoding)
BOARD_NAME   = b"SRPTC16A002"  # header offset 48 (16 bytes)

# cmdline tokens Samsung BL accepts. console=tty0 is REQUIRED (console=null breaks
# klibc run-init -> /dev/console ENODEV -> initramfs panics). Do NOT add Droidian
# namespace tokens (droidian.lvm.*, loop.max_part, cgroup.memory, reboot=panic_warm,
# buildproduct) here without re-testing — some get the image silently rejected by BL.
# Do NOT add `lpm_levels.sleep_disabled=1` (nor `cpuidle.off=1`/`nohz=off`): the porter
# stability hack `sleep_disabled=1` left the qcom RPMh/PDC wakeup infra down, so big-cluster
# rail-pc idle stranded the arch_mem_timer broadcast wake -> ~1/min whole-userspace idle FREEZE.
# Letting the FULL lpm sleep run (none of those tokens) brings up the wakeup path -> big cores
# power-collapse AND wake correctly. Verified: 7 min idle freeze-free, broadcast IPIs reach
# cpu4-7. See FIXES-TO-BAKE.md C1 + memory project_tabs7p_idle_freeze_nohz.
CMDLINE_REAL = (
    "console=tty0 androidboot.hardware=qcom androidboot.memcg=1 "
    "video=vfb:640x400,bpp=32,memsize=3072000 "
    "msm_rtb.filter=0x237 service_locator.enable=1 swiotlb=2048 "
    "firmware_class.path=/vendor/firmware_mnt androidboot.usbcontroller=a600000.dwc3 "
    "buildvariant=eng androidboot.selinux=permissive"
)
# console=null -> initramfs run-init fails -> drops to RNDIS+telnet rescue at 192.168.2.15
CMDLINE_RESCUE = CMDLINE_REAL.replace("console=tty0", "console=null")

def patch_header(path, cmdline):
    with open(path, "rb") as f:
        d = bytearray(f.read())
    assert d[:8] == b"ANDROID!", "not an Android boot.img"
    struct.pack_into("<I", d, 20, RAMDISK_ADDR)
    struct.pack_into("<I", d, 32, TAGS_ADDR)
    struct.pack_into("<I", d, 44, OS_VERSION)
    d[48:64] = BOARD_NAME.ljust(16, b"\x00")
    cb = cmdline.encode()
    assert len(cb) < 512, "cmdline too long for v2 header"
    for i in range(64, 64 + 512):
        d[i] = 0
    d[64:64 + len(cb)] = cb
    with open(path, "wb") as f:
        f.write(bytes(d))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw"); ap.add_argument("out")
    ap.add_argument("--rescue", action="store_true")
    ap.add_argument("--partition", default="boot", choices=["boot", "recovery"])
    ap.add_argument("--key", default=os.path.join(os.path.dirname(__file__), "..", "testkey_rsa4096.pem"))
    a = ap.parse_args()
    psize = BOOT_PARTITION_SIZE if a.partition == "boot" else RECOVERY_PARTITION_SIZE
    cmdline = CMDLINE_RESCUE if a.rescue else CMDLINE_REAL

    import shutil; shutil.copy(a.raw, a.out)
    patch_header(a.out, cmdline)
    # remove any existing footer, then add a fresh one
    subprocess.run(["avbtool", "erase_footer", "--image", a.out],
                   stderr=subprocess.DEVNULL)
    subprocess.run(["avbtool", "add_hash_footer",
                    "--image", a.out,
                    "--partition_size", str(psize),
                    "--partition_name", a.partition,
                    "--algorithm", "SHA256_RSA4096",
                    "--key", a.key,
                    "--rollback_index", str(ROLLBACK_INDEX)], check=True)
    print(f"OK: {a.out}  partition={a.partition} size={psize} "
          f"cmdline={'RESCUE/console=null' if a.rescue else 'REAL/console=tty0'}")

if __name__ == "__main__":
    main()
