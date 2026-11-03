# alienware-mute-led

Makes the white firmware lamps on the speaker-mute and mic-mute keys of the Alienware x15 R2 follow the mute state of the internal speakers and the internal microphone: lit while muted, off while not.

The lamps track the SOF card's `Master Playback Switch` and `Dmic0 Capture Switch`, which is the sof-hda-dsp UCM policy for mute LEDs. They do not follow a Bluetooth, HDMI or USB default sink or source: muting one of those leaves the firmware lamp as it was, while Everest Lights paints the key from `@DEFAULT_SINK@` / `@DEFAULT_SOURCE@`.

## Why

The lamps are the BIOS "global mute" indicators, switched with the Dell SMBIOS tokens `GLOBAL_MUTE_ENABLE`/`DISABLE` (0x058C/0x058D) and `GLOBAL_MIC_MUTE_ENABLE`/`DISABLE` (0x0364/0x0365). On Dell laptops `dell-laptop` registers `platform::mute` and `platform::micmute` for them, but its DMI table only accepts the vendor "Dell Inc.", so it never loads on an Alienware. `dell-smbios` does load here, and its in-kernel calls can reach the mic-mute tokens that it blocks for userspace.

- `alienware_mute_led.c` registers the two LEDs with dell-laptop's names and the `audio-mute` / `audio-micmute` triggers from `snd-ctl-led`, writes the tokens through `dell-smbios`, and writes the last state again after resume. Reading a token back does not reflect the lamp on this BIOS, so the module never reads. It loads automatically on the x15 R2 only (`force=1` loads it elsewhere, `mic=0` skips the mic lamp). It refuses the speaker tokens unless each sits at the location equal to its id, as on this BIOS, steps aside when another driver already has an LED of the same name, and does not load at all while `dell-laptop` is loaded.
- `check-dell-smbios-abi` runs from the Makefile before every build, DKMS rebuilds included. The module declares dell-smbios's token struct and three functions itself, because the kernel build tree does not ship `dell-smbios.h` and the kernel has no `CONFIG_MODVERSIONS`. The script compares them with the target kernel's dell-smbios BTF (pahole, pfunct) and stops the build on any difference.
- `alienware-mute-attach` attaches the SOF card's `Master Playback Switch` to the ctl-led speaker group. The sof-hda-dsp UCM profile only does that when `platform::mute` belongs to dell-laptop or msi-ec. The mic group already holds `Dmic0 Capture Switch`. The attachment lives in the card's control and goes away whenever the card registers again, so `alienware-mute-attach.rules` starts `alienware-mute-attach.service` each time the sofhdadsp control device appears.

Once `dell-laptop` supports this machine, remove this module (see Remove): dell-laptop then drives the same lamps itself, and UCM attaches the speaker switch on its own.

## Install

From this directory. DKMS rebuilds the module for every new kernel. Only the source files go into `/usr/src`.

```bash
sudo install -Dm644 -t /usr/src/alienware-mute-led-0.1 alienware_mute_led.c Makefile dkms.conf
sudo install -Dm755 -t /usr/src/alienware-mute-led-0.1 check-dell-smbios-abi
sudo dkms add -m alienware-mute-led -v 0.1
sudo dkms install -m alienware-mute-led -v 0.1
sudo install -Dm755 alienware-mute-attach /usr/local/lib/everest/alienware-mute-attach
sudo install -Dm644 alienware-mute-attach.service /etc/systemd/system/alienware-mute-attach.service
sudo install -Dm644 alienware-mute-attach.rules /etc/udev/rules.d/90-alienware-mute-attach.rules
sudo systemctl daemon-reload
sudo udevadm control --reload
sudo systemctl enable alienware-mute-attach.service
sudo modprobe alienware_mute_led
sudo systemctl start alienware-mute-attach.service
```

## Verify

```bash
journalctl -k -b | grep -E 'alienware[-_]mute[-_]led'   # "registered platform::mute: ENABLE 0x058c (location 0x058c value 1), ..."
cat /sys/class/leds/platform::mute/trigger                 # [audio-mute] is selected
cat /sys/class/sound/ctl-led/speaker/card1/list            # holds the numid of Master Playback Switch (amixer -c 1 controls)
wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle                 # with the internal speakers as default: the speaker lamp follows; toggle again
wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle               # with the internal mic as default: the mic lamp follows; toggle again
```

`/sys/class/leds/platform::mute/brightness` shows the state last written, not a reading from the firmware. Suspend and resume once and check that the lamps still match.

## Remove

```bash
sudo systemctl disable --now alienware-mute-attach.service
sudo rm /etc/systemd/system/alienware-mute-attach.service /etc/udev/rules.d/90-alienware-mute-attach.rules /usr/local/lib/everest/alienware-mute-attach
sudo systemctl daemon-reload
sudo udevadm control --reload
sudo modprobe -r alienware_mute_led                        # writes both lamps off
sudo dkms remove -m alienware-mute-led -v 0.1 --all
sudo rm -r /usr/src/alienware-mute-led-0.1
```

The speaker group keeps `Master Playback Switch` until the next boot.
