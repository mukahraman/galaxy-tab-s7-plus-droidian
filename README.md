# Samsung Galaxy Tab S7+ (Wi-Fi) — Droidian / Linux Mobile Port

A community port of **[Droidian](https://droidian.org)** (Halium + Debian Trixie + Phosh) to the
**Samsung Galaxy Tab S7+ Wi-Fi**. This repo is the **status & porting guide** — what works, what's
still untested, the non-obvious fixes that made it work, and how to build/flash.

> ⚠️ **Experimental.** Flashing requires an **unlocked bootloader** (which **trips Knox permanently**
> and voids warranty). You can brick or boot-loop the device; recovery is possible via Download
> Mode + TWRP, but don't attempt this without understanding the risks. **Not affiliated with Samsung or Droidian.**

---

## Device

| | |
|---|---|
| Model | Samsung Galaxy Tab S7+ **Wi-Fi** — SM-T970 |
| Codename | `gts7xlwifi` |
| SoC | Qualcomm **SM8250** "kona" (Snapdragon 865+) |
| GPU | Adreno 650 |
| Display | 12.4" 2800×1752 Super AMOLED, 120 Hz, command-mode DSI |
| Kernel | 4.19 downstream; built on **LineageOS `lineage-23.2`** (4.19.325) base |
| OS stack | Droidian = **Halium 11 / API 30** Android vendor + Debian Trixie + **Phosh** (Wayland/wlroots) |

## Repos

| Repo | What |
|---|---|
| [`kernel_samsung_sm8250`](https://github.com/mukahraman/kernel_samsung_sm8250) (branch `droidian`) | Kernel; CI builds `linux-bootimage-*.deb` in Releases |
| [`adaptation-samsung-gts7xlwifi`](https://github.com/mukahraman/adaptation-samsung-gts7xlwifi) | Device adaptation package (udev/libinput/pulse/etc.) |
| [`droidian-recipes`](https://github.com/mukahraman/droidian-recipes) | Image recipe → flashable rootfs |
| [`droidian-camera`](https://github.com/mukahraman/droidian-camera) | Camera app fork (config-driven orientation) |

---

## Status at a glance

✅ Works (device-tested) · ⚠️ Works with caveats · ❓ Not yet tested · 🚫 N/A

### ✅ Working & tested

| Feature | Notes |
|---|---|
| **Boot to desktop** | Boots to Phosh, landscape-native, stable |
| **Touchscreen** | Calibrated for landscape |
| **Internal display** | 120 Hz; windows appear immediately (direct-scanout workaround) |
| **Auto-rotate** | Accelerometer + sensorfw; display + touch rotate together |
| **Book Cover Keyboard (EF-DT970)** | Keys **and** trackpad (trackpad direction fixed) |
| **S-Pen** | Wacom digitizer — drawing + pressure (use native/apt apps, e.g. Xournal++) |
| **Cameras** | Front **and** rear, live preview, correct (upright) orientation |
| **Audio (speakers)** | Audible via kernel ASoC + Android HIDL audio HAL bridge |
| **Bluetooth** | Adapter, scan, **pairing**, **A2DP** (phone audio → tablet speakers) via bluebinder |
| **External display (USB-C DP)** | Monitor/dock over USB-C DP Alt Mode — **full HBR3**, extended desktop. *Needs the PS5169 re-driver enabled (see below).* |
| **Hardware video decode** | In Epiphany (WebKit→gst-droid) or Clapper |
| **Deep idle / sleep** | Power-collapses correctly; no idle freeze; good battery |
| **Wi-Fi** | Connects and is stable |
| **Brightness control** | Adjustable (display backlight slider works) |
| **Power / volume keys** | gpio-keys |

### ⚠️ Works, with caveats

| Feature | Caveat |
|---|---|
| **Volume control** | Audio plays, but the volume slider is effectively all-or-nothing — the same level at every step except 0 (mute). Per-level volume scaling isn't wired up yet. |
| Browser video | Firefox/Chromium are **software-decode only** (laggy) — use Epiphany/Clapper for HW decode |
| GPU-accelerated apps | Install **via apt**, not Flatpak — Flatpak's bundled Mesa can't drive the Adreno GPU (no window) |
| External display | Comes up **extended** by default; mirror / mode selection via `wlr-randr` is not pre-configured. **Boot with the cable unplugged, then hotplug** (booting with DP attached causes a transient instability + inverted-touch cascade). |
| Camera | Portrait **preview** doesn't rotate (orientation pinned for landscape) |
| Bluetooth HID | Kernel `hidp` is built, but a BT keyboard/mouse hasn't been device-verified yet |

### ❓ Not yet tested / unknown

- Bluetooth **OBEX file transfer** (receive) — needs a Phosh session auto-accept agent (`bluez-obexd` works; not yet packaged)
- **DisplayPort audio** (audio out over the external monitor)
- **Battery %** / charge-state reporting accuracy
- **Microphone**, USB-C / BT headset audio out
- **GPS / location**, **NFC**
- **Haptics / vibration**
- Grip / hall (cover) / light / proximity sensors (present in DT; behaviour unverified)
- Charging edge-cases, thermal behaviour under sustained load

### 🚫 Not applicable

- Cellular / modem / SIM — this is the **Wi-Fi-only** variant.

---

## Notable engineering (for other porters)

The LineageOS-based downstream tree had several things deliberately disabled/gutted that
Droidian (unlike Android) actually needs. The non-obvious fixes:

- **Bluetooth** — LineageOS `#if 0`'d the entire kernel HCI-socket control path in
  `net/bluetooth/hci_sock.c` (Android drives BT through the userspace HAL over UART, never the
  kernel AF_BLUETOOTH sockets). The stub `hci_sock_create()` returned success with a NULL `sk`,
  so the moment **bluebinder** opened its socket → `BUG_ON(!sk)` → panic → boot loop. Fix:
  **un-gut `hci_sock.c`**, and **uncomment `rfcomm/`, `bnep/`, `hidp/` in `net/bluetooth/Makefile`**
  (commented out, so those protocols never compiled despite `=y`).

- **External display** — the Tab S7+ routes the 4 DP main lanes through a **PS5169 re-driver IC**.
  The device tree declares it (`secdp,redrv = "ps5169"`) and `drivers/redriver/ps5169.c` exists, but
  `CONFIG_REDRIVER` / `CONFIG_COMBO_REDRIVER_PS5169` were never enabled → the IC was never powered →
  AUX + EDID worked (they bypass the re-driver via the SBU aux-switch) **but main-lane clock recovery
  always failed**. Fix: **`CONFIG_REDRIVER=y` + `CONFIG_COMBO_REDRIVER_PS5169=y`** (+ re-enable DP).
  *This was the single missing config behind months of "DP detects the monitor but never displays".*

- **Trackpad orientation** — the pogo trackpad is an absolute touchpad, so libinput's calibration
  matrix (which fixes the touchscreen/S-Pen) doesn't rotate it. Fixed in the **device tree**:
  `touchpad,invert = <0 1 1>` (Samsung-Android orientation) → `<0 0 0>` (landscape identity).

- **Audio** — kernel ASoC card works, but ACDB calibration only loads inside the Android audio HAL;
  routed via the re-enabled HIDL audio service + a 64-bit `audio.hidl_compat` wrapper.

- **Idle freeze** — removing the porter hack `lpm_levels.sleep_disabled=1` (it left qcom RPMh/PDC
  wakeup down) gave full deep idle and fixed an intermittent whole-userspace freeze.

- **Boot acceptance** — Samsung's ABL accepts a custom `boot.img` only with a valid **AVB hash footer**
  (partition_name match, AOSP testkey, SHA256_RSA4096) + `vbmeta` flags `0x02`. Header + kernel cmdline
  must avoid Droidian-namespace tokens or the BL silently rejects the image.

---

## Build & flash (outline)

1. **Kernel**: grab `linux-bootimage-4.19-325-*.deb` from the
   [kernel Releases](https://github.com/mukahraman/kernel_samsung_sm8250/releases) (branch `droidian`),
   extract `boot.img`, add the AVB footer (Samsung-ABL-acceptable header + `console=tty0`).
2. **Rootfs**: build via [`droidian-recipes`](https://github.com/mukahraman/droidian-recipes) (or its release).
3. **Flash** (Heimdall, from Download Mode — *always multi-file with VBMETA*; single-file commits unreliably on SM8250):
   ```
   heimdall flash --VBMETA vbmeta.img --BOOT boot.img --DTBO dtbo.img --no-reboot
   ```
   - `vbmeta.img` = a flags=`0x02` (verification-disabled) vbmeta.
   - For external display + trackpad, the `dtbo.img` must keep `secdp,redrv=ps5169` and use
     `touchpad,invert=<0 0 0>` (patch the stock dtbo or use the device's CI dtbo).
4. Userdata = Droidian LVM rootfs.

> Recovery: keep TWRP on the recovery partition. A bad BOOT is always re-flashable from Download Mode.

---

## Credits

Built on the work of the Droidian, Halium, and LineageOS communities, and the Samsung SM8250
kernel maintainers (himekifee, ianmacd). The DisplayPort root-cause (the PS5169 re-driver) came from
community research. Issues / additions welcome.

*This guide documents an independent hobbyist port. No warranty. Trademarks belong to their owners.*
