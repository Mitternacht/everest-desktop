# Keep the x15 R2 off its balanced fan table; see default/udev/alienware-fans.rules.
if omarchy-hw-alienware; then
  sudo install -Dm644 "$OMARCHY_PATH/default/udev/alienware-fans.rules" /etc/udev/rules.d/71-alienware-fans.rules
  sudo udevadm control --reload
  sudo udevadm trigger --action=change --subsystem-match=platform-profile
fi
