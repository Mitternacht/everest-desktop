# Architecture

Everest's [vision](../VISION.md) defines the intended desktop experience. This
document describes the current prototype's implementation. The
[roadmap](../ROADMAP.md) tracks the work and acceptance evidence still needed.

## Inspected baseline

Inspected on 2026-10-22: Omarchy stable v4.0.6 at
237f1b4071a0bff2296c6d740ba2b9fd695ebfa0. No Omarchy system was running in the
authoring environment. Repository contents and upstream interfaces were inspected
remotely; configuration generation and validation do not constitute desktop tests.

Primary sources:

- [User Lua entry point](https://github.com/omacom/omarchy/blob/v4.0.6/config/hypr/hyprland.lua)
- [Hyprland helpers and binding APIs](https://github.com/omacom/omarchy/blob/v4.0.6/default/hypr/helpers.lua)
- [Existing shortcuts](https://github.com/omacom/omarchy/blob/v4.0.6/default/hypr/bindings/utilities.lua)
- [Input examples](https://github.com/omacom/omarchy/blob/v4.0.6/config/hypr/input.lua)
- [Shell configuration and IPC](https://github.com/omacom/omarchy/blob/v4.0.6/docs/omarchy-shell.md)
- [Theme interfaces](https://github.com/omacom/omarchy/blob/v4.0.6/docs/theming.md)
- [Theme generation and side effects](https://github.com/omacom/omarchy/blob/v4.0.6/bin/omarchy-theme-set)
- [Existing maximize suppression](https://github.com/omacom/omarchy/blob/v4.0.6/default/hypr/windows.lua)
- [Quickshell Toplevel API](https://quickshell.org/docs/v0.3.2/types/Quickshell.Wayland/Toplevel/)
- [Quickshell DesktopEntry API](https://quickshell.org/docs/v0.3.2/types/Quickshell/DesktopEntry/)
- [Quickshell layer-shell panel](https://quickshell.org/docs/v0.3.2/types/Quickshell/PanelWindow/)
- [Hyprland Lua configuration options](https://github.com/hyprwm/hyprland-wiki/blob/main/content/configuring/core/config-options.md)

## Design decisions

Keep the main Quickshell process and all its security/idle services. The dock is a
separate process so errors there cannot replace or deliberately take down lock
and authentication services. Only the main bar's documented user configuration
is changed. Unknown bar properties and other root configuration keys are kept.

Use palette-only local theme directories plus supported shell section overrides.
No code is hidden inside theme Lua. A dedicated, documented user service plugin
binds the shared shell font to Noto Sans. Its binding restores the previous value
when unloaded. Terminal font settings are untouched. Omarchy generates application colors through
its normal templates. Photographic mountain backgrounds are bundled as 3840x2160 JPEGs. The Prepare
wallpapers workflow fetches the selected assets on a GitHub runner; installation
only copies their version-controlled bytes.

An appended Lua include runs after defaults and existing personal modules. The
layer uses the inspected hl API, not legacy Hyprland .conf syntax. New windows
float. Tiling remains available per window; the layer does not replace the
compositor or change the login/session manager.

Keyboard switching groups normal windows across ordinary workspaces. App groups
cycle in stable alphabetical class order; within a group the most recently used
window is selected. Within-app switching cycles stable window addresses. This is
deterministic rather than macOS's modifier-held app-switcher UI.

## Implementation status

The initial integration code is present. Full graphical acceptance remains
pending. The current Settings window routes to existing Omarchy controls;
setup, updates, and recovery still use command-line tools. Pointer window
controls, common-application consistency, and hardware behavior need further
work and testing.

The roadmap prioritizes a verified graphical baseline, a consistent visual
system, complete everyday workflows, and approachable setup and maintenance.
Overview, dock effects, and advanced gestures are later work.

The official Omarchy package set supplies Quickshell, Nautilus, Foot, ImageMagick,
fonts, and Python through its existing dependencies. Bundled JPEG backgrounds
need no local rendering package or network call. No additional shell, launcher, or compositor plugin is
required. The installer never installs packages for you.

## Reversibility

The plan is built and checked before target writes. Each transaction journals
before/after bytes and original modes before the first write, and replaces each
file atomically. A single installer lock serializes writes. Recovery compares
actual files with both journal states, covering interruption immediately after
replacement or manifest commit. Conflicting outside edits prevent recovery.

Initial backups are retained through updates and full removal. Exact unchanged
files restore byte-for-byte. If shared configuration was edited elsewhere, only
the exact Lua block and unchanged managed bar properties are removed/restored.
An edited managed property is a conflict, not silent consent to overwrite it.

Upstream theme activation is deliberately a separate, explicit action because
it runs application retint/reload hooks outside this file transaction. Restore
the previous theme/background before removing Everest. Session restart remains
the user's decision.
