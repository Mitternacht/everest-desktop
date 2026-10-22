# Everest

[![Validate](https://github.com/Mitternacht/everest-desktop/actions/workflows/validate.yml/badge.svg)](https://github.com/Mitternacht/everest-desktop/actions/workflows/validate.yml)

A floating-first, macOS-inspired desktop layer for **Omarchy 4.0.6**.
A proportional sans-serif interface, photographic backgrounds, a top bar,
application dock, graphical Settings, and familiar Super-key shortcuts. **Dawn** is light; **Dusk** is dark.

Everest is an additional user configuration layer. Omarchy retains its update
mechanism, launcher, notifications, system controls, lock screen, and polkit agent.
It does not run macOS applications.

![Dawn](assets/dawn.jpg)
![Dusk](assets/dusk.jpg)

The photographs are the bundled backgrounds; they are not screenshots of a
tested desktop. The interface is designed around everyday graphical controls,
with terminal tools available when needed rather than permanently pinned.

This project was authored directly on GitHub without a local checkout on the
authoring machine. Automated checks run on GitHub. A real Omarchy graphical
session has not yet been tested.

## What inspection established

Upstream stable v4.0.6 is commit
[237f1b4](https://github.com/omacom/omarchy/tree/237f1b4071a0bff2296c6d740ba2b9fd695ebfa0).
It uses **Lua Hyprland configuration** and **Quickshell**, with Foot and Nautilus
among the default applications. The built-in shell already provides the bar,
application search, notifications, audio/network/Bluetooth/display/power panels,
locking, and authentication. It has no bundled application dock.

The small architecture is:

| Component | Everest implementation |
|---|---|
| Theme | Original colors.toml palettes and supported shell section overrides |
| Top bar | Existing omarchy.bar, laid out through user shell.json |
| Dock and Settings | Separate Quickshell instance; graphical settings categories |
| Interface typography | Small supported service plugin binds shell text to Noto Sans |
| Window behavior/input | One appended dofile include in user hyprland.lua |
| App/window switching and shelf | Small Python helper using public hyprctl IPC |
| Installation | Python standard library, backups, manifest and durable undo journal |

No Waybar, Walker, Mako, compositor plugins, root services, or Omarchy fork are
needed. See [architecture and staged plan](docs/architecture.md).

## Prerequisites

Install on the **target Linux machine**, as its normal desktop user:

- Omarchy **4.0.6**, including its Lua-based Hyprland configuration.
- Existing ~/.config/hypr/hyprland.lua and ~/.config/omarchy/shell.json.
- Python 3.11+, Quickshell 0.3.2-compatible APIs, and hyprctl.
- Omarchy's existing uwsm-app and gtk-launch desktop-entry launch helpers.
- Standard Omarchy wrappers: omarchy-menu, omarchy-launch-nautilus,
  omarchy-launch-browser, and xdg-terminal-exec.
- Noto Sans and Yaru icons, already part of the inspected Omarchy package set.

The installer checks the installed version using omarchy-version and refuses
other releases. It never uses sudo, installs packages, changes system files, or
restarts the graphical session. Nondefault XDG_CONFIG_HOME and symlinked target
paths are deliberately unsupported. It does not change keyboard layout.

[Current Arch Quickshell package](https://archlinux.org/packages/extra/x86_64/quickshell/)
and [pinned Omarchy package list](https://github.com/omacom/omarchy/blob/v4.0.6/install/omarchy-base.packages).

## Install

Review the project on GitHub first. The following commands are for your Omarchy
machine, not the machine on which this repository was authored.

~~~bash
git clone https://github.com/Mitternacht/everest-desktop.git
cd everest-desktop
python3 everest.py doctor
python3 everest.py plan
./install.sh
~~~

Plan and --dry-run make no target or state-directory changes. Installation
copies the bundled photographs and project-owned configuration. No rendering
packages or network access are needed during installation.

Files managed:

~~~text
~/.config/everest/{everest.py,hyprland.lua,actions.py,dock/*.qml}
~/.config/omarchy/plugins/everest.typography/{manifest.json,Service.qml}
~/.config/omarchy/themes/everest-{dawn,dusk}/...
~/.config/hypr/hyprland.lua                  (one marked include)
~/.config/omarchy/shell.json                 (selected bar properties)
~~~

Existing Everest/theme directories are refused on first installation. Other
shell settings, idle timeouts, plugins, and authentication services are retained.
One Everest typography service is added alongside the existing plugin list; it
changes shell text to Noto Sans and restores the prior font when unloaded.
The bar layout is replaced; its original value is backed up. Everest takes
precedence over earlier personal settings for the specific keys it configures.

Hyprland or Quickshell may automatically reload a watched configuration when it
changes. The installer makes no explicit compositor reload or session restart.
The floating rule affects newly opened windows; use Super+Shift+T for existing ones.

## Select an appearance and start the dock

Before switching, record your current theme and background:

~~~bash
omarchy-theme-current
readlink -f "$HOME/.local/state/omarchy/current/background"
~~~

Select either appearance explicitly:

~~~bash
omarchy-theme-set everest-dusk
# Or: omarchy-theme-set everest-dawn
~~~

This is Omarchy's normal theme command. It retints applications, reloads terminal
configuration, reloads compositor theme settings, and runs your theme hooks.
These live application effects are outside Everest's installer transaction.

On the next normal login the dock starts automatically. To start it in the
existing graphical session without logging out:

~~~bash
qs -n -p "$HOME/.config/everest/dock"
~~~

Run that command once. To load the typography plugin and refresh the main bar without restarting the shell:

~~~bash
omarchy-shell shell rescanPlugins
omarchy-shell shell reloadConfig
~~~

The dock and Settings follow Dawn/Dusk palette changes within three seconds. It keeps its
last valid palette if another theme lacks the Everest palette file.

## Everyday use

- Super+Space opens application search; Super+comma opens graphical Settings.
- Settings has Appearance, Displays, Sound, Network, Bluetooth, Power,
  Notifications, and Lock Screen controls. The same window opens from the dock.
- Click dock icons to launch/focus. Repeated clicks cycle that app's windows;
  right-click launches another instance where the application supports it.
- Super+Tab switches between application classes. Super+grave switches windows
  within the current application. Neither depends on the dock staying alive.
- Super+Up maximizes/restores; Super+Ctrl+F toggles fullscreen.
- Super+M shelves a window. Super+Shift+M restores a shelved window to the current
  ordinary workspace. Super+Ctrl+M shows/hides the shelf.
- Super+Shift+T tiles/floats the current window. Omarchy's tiling shortcuts remain
  available. New windows continue to float by default.
- Natural touchpad scrolling, tap-to-click, click-to-focus and border resizing are enabled.
- Workspace buttons and Omarchy's Super+number shortcuts work without gestures.
  After checking your personal gestures, optionally add the following to your
  existing ~/.config/hypr/input.lua module, before Everest's include loads:

~~~lua
everest_workspace_gesture = true
~~~

This enables a three-finger horizontal workspace swipe and disables three-finger
dragging. Leave it unset if you already have a conflicting horizontal/swipe
gesture; Hyprland rejects duplicate gesture definitions.

Full [shortcut reference](docs/shortcuts.md) and [manual test checklist](docs/testing.md).

## Update

Keep your source checkout on the target machine. Review changes before applying:

~~~bash
git pull --ff-only
python3 everest.py plan
./install.sh
~~~

Identical reinstallation changes no managed files and creates no new backups.
Updates retain the initial pre-install backups. Obsolete managed files are
retired only if unchanged; unknown files are preserved. A changed managed payload or bar
property causes a conflict instead of overwriting your work. Unrelated edits
outside the marked Lua block or managed bar properties survive removal.

Continue using Omarchy's normal updater. After an Omarchy update, run doctor,
check [upstream.lock.json](upstream.lock.json), and review compatibility. The
version gate is intentional; do not bypass it by editing installed version data.
Upstream refresh commands can replace user config: if Everest's include is
removed, recover/reconcile using the manifest and backups before reinstalling.

## Backups, rollback, and removal

State is stored in ~/.local/state/everest/ with:

- manifest.json: every managed path, installed hash, original hash/mode, backup path.
- backups/: original bytes from before the first installation, kept after removal.
- pending.json: durable undo images for an interrupted operation, when present.
- recover.py: a retained recovery CLI, usable even if a removal deleted the installed copy.

To inspect state or recover an interrupted installation/update/removal:

~~~bash
python3 everest.py status
python3 everest.py recover
# If the source and installed CLI are unavailable:
python3 "$HOME/.local/state/everest/recover.py" recover
~~~

Recover restores the state immediately before the interrupted operation.
It refuses changed files rather than overwriting edits.

Before removal, restore all shelved windows with Super+Shift+M, select the
previous Omarchy theme you recorded, and restore your previous background through
Omarchy's background picker if needed. If an Everest theme is still selected,
the uninstaller refuses removal.

Stop only the Everest dock, then preview and remove the layer:

~~~bash
qs ipc -n -p "$HOME/.config/everest/dock" call -- dock stop
python3 everest.py uninstall --dry-run
./uninstall.sh
~~~

If the dock is not running, the first command may report no instance; continue.
The installed CLI also works if the source checkout is gone:

~~~bash
python3 "$HOME/.config/everest/everest.py" uninstall
~~~

Rollback is an alias for full removal back to the initial pre-install file
configuration:

~~~bash
python3 everest.py rollback
~~~

With no intervening edits, removal restores original file bytes and modes.
Otherwise, it removes the unchanged Lua include and restores the managed bar
properties while preserving unrelated edits. Modified managed values cause a
reported conflict before any removal. Save those edits separately and reconcile
them with the installed version/backups; there is no force-overwrite flag.
Unknown files you added to owned directories are kept. Reload the shell config
and rescan plugins after removal to unload typography without a session restart.

Removal does not reverse unrelated application actions performed by upstream
theme hooks, remove packages, delete backups, or restart your session.

## Troubleshooting

| Symptom | Check |
|---|---|
| Version refused | Run doctor; only Omarchy 4.0.6 is currently targeted |
| Lua/config errors | Run hyprctl configerrors; inspect the appended block and config/hyprland.lua |
| Dock missing | Start qs -n -p ~/.config/everest/dock from a terminal and inspect output |
| Bar unchanged | Run omarchy-shell shell reloadConfig |
| Theme unchanged | Select everest-dawn/dusk with Omarchy's theme command |
| Maximize button ignored | Use Super+Up; this is an upstream rule, described below |
| Installer conflict | Inspect status and manifest; preserve edits, then reconcile |
| Interrupted write | Run recover before another install or removal |
| Shelf window inaccessible | Super+Ctrl+M exposes the special workspace; restore from an ordinary workspace |

## Known differences from macOS

Omarchy's universal window rule suppresses application maximize requests;
Everest does not rewrite it. Keyboard maximize works, while some titlebar
maximize buttons do not. Hyprland has no native minimize: the shelf is a special
workspace, and app dock clicks may not retrieve shelved windows. Use the shelf
shortcuts.

There is no Mission Control thumbnail overview in this first version. Workspace
buttons and swipe navigation provide real workspace switching. App grouping uses
Wayland app IDs in the dock and Hyprland application classes for keyboard
switching; applications that publish inconsistent identities may appear twice.

Omarchy's existing terminal-aware Super+C/V/X copy/paste/cut bindings are retained.
Undo, select-all, and other Command-style shortcuts vary across GTK, Qt, Electron
and terminals. Native Ctrl shortcuts remain available; terminals retain Ctrl+C
interrupt and Ctrl+Shift+C/V copy/paste. There is no global Ctrl/Super swap.

Window titlebars, file-manager details, scroll physics, fractional scaling,
XWayland apps, and multi-monitor behavior depend on applications, drivers,
hardware, and the compositor. The dock is scrollable when there are many apps;
auto-hide and magnification are deferred. See the test checklist before treating
this as a daily-driver setup.

## License

MIT; see [LICENSE](LICENSE) and [NOTICE](NOTICE). Code and palettes are MIT licensed. Bundled photographs have their separate
[asset license](assets/LICENSE.txt), which does not require attribution.
Installed system icons and runtime dependencies retain their respective licenses.
No Apple assets are included.
