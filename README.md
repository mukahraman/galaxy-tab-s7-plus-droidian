# Samsung Galaxy Tab S7+ (Wi-Fi) — Droidian / Linux Mobile Port

A community port of **[Droidian](https://droidian.org)** (Halium + Debian Trixie + Phosh) to the
**Samsung Galaxy Tab S7+ Wi-Fi**. This repo is the **status & porting guide** — what works, what's
still untested, the non-obvious fixes that made it work, and a **step-by-step install guide** (below).

> ⚠️ **Experimental.** Flashing requires an **unlocked bootloader** (which **trips Knox permanently**
> and voids warranty). You can brick or boot-loop the device; recovery is possible via Download
> Mode + TWRP, but don't attempt this without understanding the risks. **Not affiliated with Samsung or Droidian.**

**→ Just want to flash it?** Jump to **[Install Droidian — step by step](#install-droidian-step-by-step)** below.

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

## Install Droidian (step by step)

From a **stock-Android SM-T970** to a working Droidian desktop. You need a **Linux PC**, a USB-C
cable, and ~45 minutes. **This erases the tablet.**

> The Tab S7+ bootloader has **no fastboot**, so Droidian's generic `flash_all.sh` does **not** work
> here — everything below uses **Heimdall** (the Samsung Download-Mode flasher).

### 0. Set up your PC

```bash
# Debian/Ubuntu package names (adjust for your distro):
sudo apt install heimdall-flash android-tools-adb android-sdk-libsparse-utils \
                 avbtool device-tree-compiler binutils python3 unzip
```

`simg2img` comes from `android-sdk-libsparse-utils`, `dtc` from `device-tree-compiler`, `ar` from
`binutils`. Then clone this repo — it carries the flashing tools, the public AOSP test key, and the
verification-disabled vbmeta you'll flash:

```bash
git clone https://github.com/mukahraman/galaxy-tab-s7-plus-droidian
cd galaxy-tab-s7-plus-droidian
```

### 1. Unlock the bootloader &nbsp; ⚠️ erases all data, trips Knox permanently

1. On the tablet: **Settings → About tablet → Software information** → tap **Build number** 7× (this enables Developer options).
2. **Settings → Developer options** → turn on **OEM unlocking**.
3. Power the tablet off. Hold **Volume-Up + Volume-Down** and plug the USB-C cable into your PC → the unlock/Download screen appears. **Long-press Volume-Up** to unlock and confirm; the tablet factory-resets.
4. Let it reboot into stock Android, **connect to Wi-Fi**, and wait ~5 minutes. Samsung's *VaultKeeper* must phone home and release the bootloader — otherwise Heimdall reaches 100 % then fails with "session end" and nothing is written.

### 2. Download the images

| File | Where |
|---|---|
| Droidian rootfs — `droidian-*-gts7xlwifi-*.zip` | [`droidian-recipes` → Releases → **nightly**](https://github.com/mukahraman/droidian-recipes/releases/tag/nightly) (verify against its `SHA256SUMS`) |
| Kernel — `linux-bootimage-4.19-325-*.deb` | [`kernel_samsung_sm8250` → Releases](https://github.com/mukahraman/kernel_samsung_sm8250/releases) (newest, branch `droidian`) |
| `twrp-gts7xl-*.img` | any working gts7xl TWRP build — used once, to write the rootfs |

Drop all three into this repo's folder.

### 3. Build the bootable boot.img + dtbo (on your PC)

The Droidian zip *contains* a `boot.img`, but **Samsung's bootloader rejects it as-is** — you wrap your
own from the kernel `.deb`. That's exactly what `build-bootimg.py` does (header patch + `console=tty0`
+ AVB hash footer); it's the step that took ~50 flash attempts to pin down.

```bash
# 3a. unpack the kernel .deb → raw boot.img
ar x linux-bootimage-*.deb
tar xf data.tar.*
ls boot/                                     # → boot.img-4.19-325-...

# 3b. wrap it into a Samsung-ABL-acceptable image (signed with the bundled AOSP testkey)
python3 tools/build-bootimg.py boot/boot.img-* boot-tab.img

# 3c. unpack the Droidian rootfs zip
unzip droidian-*-gts7xlwifi-*.zip -d droidian
#   droidian/data/userdata.img  ← the rootfs      droidian/data/dtbo.img

# 3d. fix the Book Cover trackpad orientation in the dtbo (DP re-driver kept intact)
python3 tools/make-touchpad-dtbo.py droidian/data/dtbo.img dtbo-tab.img
#   no keyboard cover? skip this and flash droidian/data/dtbo.img instead
```

You'll flash three small images: **`boot-tab.img`**, **`dtbo-tab.img`**, and the bundled
**`vbmeta-disabled.img`** (verification disabled). ⚠️ **Don't** use the zip's own `vbmeta.img` — it's
flags=1, and the bootloader won't accept the test-key-signed boot under it.

### 4. Flash recovery, then write the rootfs

Reboot to **Download Mode** (power off → hold **Volume-Up + Volume-Down** → plug in USB; or
`adb reboot download`).

```bash
# always include --VBMETA in the same command; single-image flashes commit unreliably on SM8250
heimdall flash --VBMETA vbmeta-disabled.img --RECOVERY twrp-gts7xl-*.img --DTBO dtbo-tab.img --no-reboot
```

Boot TWRP: hold **Volume-Up + Power** until the splash. Then write the ~4.4 GB rootfs over adb:

```bash
simg2img droidian/data/userdata.img userdata.raw.img
cat userdata.raw.img | adb shell -T "dd of=/dev/block/by-name/userdata bs=4M"
```

(~5 minutes. The `cat | adb shell -T` pipe is required — TWRP's busybox `dd` won't stream a
redirected file on its own.)

### 5. Flash the kernel and boot Droidian

```bash
adb reboot download          # back to Download Mode (or use the key combo)
heimdall flash --VBMETA vbmeta-disabled.img --BOOT boot-tab.img --DTBO dtbo-tab.img --no-reboot
```

Exit Download Mode with **Volume-Down + Power**, then let go and **press nothing**. Droidian boots —
the first boot takes 1–2 minutes to reach the Phosh welcome screen.

> **Landed in TWRP instead of Droidian?** The boot-control block is latched to recovery. Boot TWRP,
> clear it, then redo step 5:
> ```bash
> adb shell dd if=/dev/zero of=/dev/block/by-name/misc bs=4096 count=1
> ```

### 6. First boot

Complete the Phosh welcome wizard with the **touchscreen** and the **Book Cover keyboard** — both work
out of the box, and the panel is landscape-native. You're on Droidian.

> **External monitor:** boot with the USB-C cable **unplugged**, then hotplug your dock/monitor
> (booting with DP already attached triggers a transient touch-inversion cascade).

A bad `boot-tab.img` is always recoverable: just re-flash from Download Mode (step 5) — your install on
`userdata` survives, so you repeat only the boot flash, not the whole procedure.

---

## What's in this repo

`tools/` (need `avbtool` + `dtc` in PATH):

- **`build-bootimg.py`** — turns a raw kernel `boot.img` into a Samsung-ABL-acceptable, AVB-footered, bootable image (header patch + `console=tty0` + AVB hash footer).
- **`make-touchpad-dtbo.py`** — patches the dtbo for the landscape trackpad (`touchpad,invert <0 1 1> → <0 0 0>`) and re-signs it; leaves `secdp,redrv="ps5169"` (DP re-driver) intact.

Bundled so the tools and the flash work out-of-the-box:

- **`testkey_rsa4096.pem`** — the public **AOSP AVB test key** both tools sign with (their `--key` default). Not a secret — it's the standard AOSP test key, usable here only because `vbmeta` verification is disabled.
- **`vbmeta-disabled.img`** — a 64 KB vbmeta with verification disabled (flags `0x02`). Regenerate with `avbtool make_vbmeta_image --flags 2 --padding_size 65536 --output vbmeta-disabled.img`.

---

## Credits

Built on the work of the Droidian, Halium, and LineageOS communities, and the Samsung SM8250
kernel maintainers (himekifee, ianmacd). The DisplayPort root-cause (the PS5169 re-driver) came from
community research. Issues / additions welcome.

*This guide documents an independent hobbyist port. No warranty. Trademarks belong to their owners.*
