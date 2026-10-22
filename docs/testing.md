# Validation and manual acceptance

Use this guide to validate the current implementation. The
[roadmap](../ROADMAP.md) defines broader product acceptance and planned work;
passing the checks here does not by itself complete those milestones.

## Automatically checked

The GitHub Validate workflow runs in an Arch Linux container on a GitHub runner.
It checks Python/Bash/Lua/QML syntax, JSON/TOML data and palette consistency,
bundled photograph hashes and JPEG dimensions. The target installer copies
these bundled files without rendering or network calls.

Isolated fake-home tests cover install/identical reinstall/exact uninstall,
original permissions and CRLF bytes, preserving unrelated shared-config edits,
refusing changed managed files/bar values, preserving unknown files, malformed
JSON/markers, symlink targets/ancestors, stale plans, updates retaining initial
backups, selected-theme removal guards, and recovery at every write boundary
including manifest commit. Switching tests verify grouping, wrapping, shelf
exclusion, and empty-session behavior.

An offscreen QML harness also checks that the typography plugin applies Noto Sans
and restores the previous font when unloaded, using a minimal mock of the shared
style object.

These tests never install into the runner's desktop. QML formatting checks
syntax; it is not compositor/runtime type validation. Lua compilation checks
syntax, not successful evaluation against a live hl API.

## Manual graphical acceptance (not yet completed)

Record Omarchy/Hyprland/Quickshell versions, GPU/driver, monitor scales,
keyboard layout, trackpad model and whether this is physical hardware or a VM.
Use a spare user account or VM snapshot first.

- [ ] Doctor reports Omarchy 4.0.6 and required commands.
- [ ] Review plan and backup manifest; record current theme/background.
- [ ] Installation succeeds; identical reinstall reports no changes.
- [ ] hyprctl configerrors reports no new errors after loading the include.
- [ ] Normal logout/login works and creates exactly one Everest dock.
- [ ] Omarchy shell stays running with its existing idle, lock and polkit services.
- [ ] Lock/unlock, authentication prompts, suspend/resume and lid behavior work.
- [ ] Dawn/Dusk render the bar, launcher, notifications, terminal and file manager coherently.
- [ ] Interface text uses Noto Sans across the bar, menus, panels and notifications.
- [ ] Terminal fonts retain their original monospace configuration.
- [ ] Unloading the typography plugin restores the previous shell font.
- [ ] Settings opens from the dock and Super+comma; each category opens its graphical control.
- [ ] Wallpaper switches; dock colors follow within three seconds.
- [ ] Bar clock/workspaces and applicable network/Bluetooth/audio/display/battery/power panels work.
- [ ] Disabled/unavailable hardware controls fail gracefully.
- [ ] Open terminal/browser/files; new normal windows float and dialogs remain usable.
- [ ] Move and resize windows, maximize via Super+Up and toggle fullscreen.
- [ ] Tile two windows, check Omarchy's tiling layout and return to floating.
- [ ] Switch distinct app classes, then several windows within one class.
- [ ] Shelf/restore multiple windows, including a terminal and an XWayland app.
- [ ] Dock launch/focus/cycle/right-click behavior matches app capabilities.
- [ ] Close apps; running indicators disappear. Test missing/ambiguous desktop IDs.
- [ ] Test many apps in the horizontally scrollable dock.
- [ ] Test two monitors, hotplug, fractional scaling, fullscreen reserved edges.
- [ ] Natural scrolling, tap/right-click and palm rejection work.
- [ ] Opt-in workspace swipe works without colliding with personal gestures.
- [ ] Keyboard-only workspace fallback works with no touchpad.
- [ ] Screenshot/capture tools and notifications work.
- [ ] Ctrl+C interrupt and terminal Ctrl+Shift+C/V are unchanged.
- [ ] App Ctrl+C/V/X/Z and inherited Omarchy Super+C/V/X work; binding conflicts are understood.
- [ ] Stop the dock independently; core session/lock/polkit remain functional.
- [ ] Restore all shelf windows, previous theme/background, then uninstall.
- [ ] Original files/permissions return; unrelated user edits survive.
- [ ] Next normal login has original session behavior and no Everest dock.
- [ ] After an Omarchy update, repeat compatibility checks before reinstalling.

## Record the experience

Publish graphical results with the tested commit, upstream versions, relevant
hardware, scale, input method, and pass/fail details. Include actual desktop
screenshots of Dawn and Dusk with the launcher, Settings, notifications, and
selected applications. Keep backgrounds labeled as backgrounds.

In addition to component checks, record complete tasks: launch an application,
find a file, arrange and restore windows, connect a device, adjust a display,
take a screenshot, change appearance, and return to work. Note where the
interface is unclear or a terminal is required. Planned graphical setup,
software management, updates, and recovery need their own recorded tasks when
implemented; their absence remains a roadmap gap.

Keep failed checks and untested configurations visible. Label code as
implemented until its relevant graphical behavior has been observed, and
accepted only after the milestone criteria are met.

## Troubleshooting evidence

Capture hyprctl configerrors and the dock's foreground logs, omarchy-version,
hyprctl version, qs --version, and the failing shortcut/window class. Avoid
posting private window titles or authentication details in public issues.
