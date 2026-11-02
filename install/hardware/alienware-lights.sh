# Give the active session access to the x15 R2 keyboard and chassis lights.
if omarchy-hw-alienware; then
  sudo install -Dm644 "$OMARCHY_PATH/default/udev/alienware-lights.rules" /etc/udev/rules.d/71-alienware-lights.rules
  sudo udevadm control --reload
  sudo udevadm trigger --subsystem-match=hidraw
  sudo udevadm trigger --subsystem-match=input
fi
