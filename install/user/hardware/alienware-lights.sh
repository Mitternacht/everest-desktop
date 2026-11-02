# Start Everest lighting for the person using this Alienware.
if omarchy-hw-alienware; then
  unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  mkdir -p "$unit_dir"
  sed "s|@OMARCHY_PATH@|$OMARCHY_PATH|g" \
    "$OMARCHY_PATH/default/systemd/user/everest-lights.service.in" > "$unit_dir/everest-lights.service"
  systemctl --user daemon-reload || true
  systemctl --user enable --now everest-lights.service || true
fi
