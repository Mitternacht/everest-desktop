# Keyboard and mouse reference

Super is normally the Windows/Command-logo key. These override matching earlier
Omarchy/user bindings; other Omarchy shortcuts remain available.

| Shortcut | Action |
|---|---|
| Super+Space | Application launcher/search |
| Super+comma | Omarchy menu: setup/preferences/system entry point |
| Super+Return | Default terminal through xdg-terminal-exec |
| Super+E | Nautilus file manager through Omarchy |
| Super+Q | Close the current window |
| Super+Tab / Super+Shift+Tab | Next/previous application class |
| Super+grave / Super+Shift+grave | Next/previous window in the current app |
| Super+Up | Maximize/restore |
| Super+Ctrl+F | Fullscreen/restore |
| Super+Shift+T | Tile/float current window |
| Super+M | Stash window on the Everest shelf |
| Super+Shift+M | Restore one shelved window to the current ordinary workspace |
| Super+Ctrl+M | Show/hide all shelved windows |
| Super+Shift+4 | Omarchy screenshot selection |
| Super+Shift+5 | Omarchy capture menu |
| Print | Existing Omarchy screenshot command |
| Super+number | Existing Omarchy workspace switching |
| Super+Ctrl+L | Existing Omarchy lock command |
| Super+Ctrl+A/B/W/D/P | Existing audio/Bluetooth/network/display/power panels |

grave is the backtick/tilde key on many US keyboards; position and availability
vary by keyboard layout. These bindings use key symbols rather than assuming
US physical key positions. Comma uses xkbcommon's lower-case comma symbol.

App switching includes normal windows on all ordinary workspaces and focuses
the group's most recently used window. The shelf is excluded. Group order is
alphabetical by application class, not an animated MRU switcher.

The preferences shortcut replaces Omarchy's Super+comma notification-dismissal
binding. Notification controls remain in the shell; Super+Shift+comma still
dismisses all notifications, and Super+Shift+Alt+comma opens notification history.

Dock: left-click launches/focuses and cycles existing windows. Right-click
requests a new instance. Dialogs follow their parent application. Four built-in
pins launch Applications, Files, Terminal and Browser; other running apps follow.

Mouse: click to focus, resize at borders, retain Omarchy's Super+drag window
move/resize bindings. Touchpad: natural scrolling, tap to click, clickfinger
right-click, three-finger horizontal workspace swipe. Unsupported hardware uses
workspace buttons/shortcuts. Three-finger dragging is disabled.

## Editing and terminal behavior

Use native application Ctrl+C/V/X/A/Z shortcuts. In terminals, Ctrl+C continues
to send an interrupt; Ctrl+Shift+C/V copy and paste where supported. Super+Q
closes the focused window and may terminate a terminal job after its application
confirmation policy. Super+W is left at Omarchy's default; it is not globally
mapped to close a browser tab.

No global Ctrl/Super swap, synthetic editing injection, or application shortcut
rewriting is installed. Toolkit and terminal differences are intentional limits
of this initial layer.
