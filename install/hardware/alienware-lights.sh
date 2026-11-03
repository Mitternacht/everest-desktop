# Give the active session access to the x15 R2 keyboard and chassis lights.
if omarchy-hw-alienware; then
  sudo install -Dm644 "$OMARCHY_PATH/default/udev/alienware-lights.rules" /etc/udev/rules.d/71-alienware-lights.rules
  sudo udevadm control --reload
  sudo udevadm trigger --subsystem-match=hidraw
  sudo udevadm trigger --subsystem-match=input

  # dell-laptop refuses Alienware, so nothing drives the BIOS mute lamps on the
  # speaker-mute and mic-mute keys. alienware-mute-led does, through DKMS.
  omarchy-pkg-add dkms linux-omarchy-headers pahole
  mod="$OMARCHY_PATH/default/alienware-mute-led"
  sudo install -Dm644 -t /usr/src/alienware-mute-led-0.1 "$mod/alienware_mute_led.c" "$mod/Makefile" "$mod/dkms.conf"
  sudo install -Dm755 -t /usr/src/alienware-mute-led-0.1 "$mod/check-dell-smbios-abi"
  dkms status -m alienware-mute-led | grep -q . || sudo dkms add -m alienware-mute-led -v 0.1
  sudo dkms install -m alienware-mute-led -v 0.1
  sudo install -Dm755 "$mod/alienware-mute-attach" /usr/local/lib/everest/alienware-mute-attach
  sudo install -Dm644 "$mod/alienware-mute-attach.service" /etc/systemd/system/alienware-mute-attach.service
  sudo install -Dm644 "$mod/alienware-mute-attach.rules" /etc/udev/rules.d/90-alienware-mute-attach.rules
  sudo systemctl daemon-reload
  sudo udevadm control --reload
  sudo systemctl enable alienware-mute-attach.service
  sudo modprobe alienware_mute_led
  sudo systemctl start alienware-mute-attach.service
fi
