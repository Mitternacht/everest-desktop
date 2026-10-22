-- Everest: appended after Omarchy defaults and personal overrides.
-- Target: Omarchy 4.0.6 / Hyprland Lua. Never loaded as a theme script.
hl.config({
  general = { border_size = 1, resize_on_border = true },
  input = {
    follow_mouse = 0,
    touchpad = {
      natural_scroll = true,
      tap_to_click = true,
      clickfinger_behavior = true,
    },
  },
  decoration = {
    rounding = 12,
    shadow = { enabled = true },
    blur = { enabled = true, size = 6, passes = 2 },
  },
})

-- New windows float; existing windows keep their state.
-- No blanket size rule: dialogs and utility windows retain their requested size.
hl.window_rule({
  name = "everest-float-first",
  match = { class = ".*" },
  float = true,
  center = true,
})

local function bind(keys, description, action)
  hl.unbind(keys)
  o.bind(keys, description, action)
end
local actions = "python3 " .. o.shell_quote(os.getenv("HOME") .. "/.config/everest/actions.py") .. " "

bind("SUPER + SPACE", "Everest: search applications", "omarchy-menu toggle apps")
bind("SUPER + comma", "Everest: preferences and system menus", "omarchy-menu toggle")
bind("SUPER + Q", "Everest: close window", hl.dsp.window.close())
bind("SUPER + TAB", "Everest: next application", actions .. "next-app")
bind("SUPER + SHIFT + TAB", "Everest: previous application", actions .. "previous-app")
bind("SUPER + grave", "Everest: next window of this application", actions .. "next-window")
bind("SUPER + SHIFT + grave", "Everest: previous window of this application", actions .. "previous-window")
bind("SUPER + M", "Everest: put window on shelf", actions .. "minimize")
bind("SUPER + SHIFT + M", "Everest: restore a shelved window", actions .. "restore")
bind("SUPER + CTRL + M", "Everest: show or hide window shelf",
  hl.dsp.workspace.toggle_special("everest-minimized"))
bind("SUPER + UP", "Everest: maximize or restore",
  hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" }))
bind("SUPER + CTRL + F", "Everest: fullscreen",
  hl.dsp.window.fullscreen({ mode = "fullscreen", action = "toggle" }))
bind("SUPER + SHIFT + T", "Everest: tile or float current window",
  hl.dsp.window.float({ action = "toggle" }))
bind("SUPER + RETURN", "Everest: terminal", "xdg-terminal-exec")
bind("SUPER + E", "Everest: files", "omarchy-launch-nautilus")
-- Omarchy binds workspace moves by physical code; remove both matching forms.
hl.unbind("SUPER + SHIFT + code:13")
hl.unbind("SUPER + SHIFT + code:14")
bind("SUPER + SHIFT + 4", "Everest: screenshot selection", "omarchy-capture-screenshot region")
bind("SUPER + SHIFT + 5", "Everest: capture menu", "omarchy-menu toggle capture")

-- Opt in after checking personal gestures: set everest_workspace_gesture = true
-- in the existing hypr/input.lua module. Duplicate Hyprland gestures are errors.
if everest_workspace_gesture == true then
  hl.config({ input = { touchpad = { drag_3fg = 0 } } })
  hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })
end
-- Workspace buttons and default Super+number bindings work without a touchpad.

-- A separate shell instance; no replacement of Omarchy's bar, lock, or polkit.
hl.on("hyprland.start", function()
  hl.exec_cmd("qs -n -p " .. o.shell_quote(os.getenv("HOME") .. "/.config/everest/dock"))
end)
