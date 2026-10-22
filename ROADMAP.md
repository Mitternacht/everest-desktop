# Roadmap

Everest is an early prototype. This roadmap describes the work needed to turn
the [vision](VISION.md) into a tested everyday desktop. Milestones are ordered
by dependency and accepted through evidence; there are no release dates yet.

## Starting point

Code is present for Dawn and Dusk themes, photographic backgrounds, a top bar,
a dock and Settings window, proportional shell typography, floating windows,
keyboard switching, a window shelf, and an installer with backups and recovery.

Automated validation covers source formats, assets, installer transactions and
helpers. An isolated QML check exercises typography binding and restoration.
**Full graphical acceptance has not been completed.** Code being present does
not close the milestones below.

Current gaps include command-line setup and maintenance, incomplete pointer
window workflows, fixed default dock pins, toolkit differences, and untested
multi-monitor and hardware behavior.

## 1. Prove the graphical foundation

**Next priority.** Establish that the existing layer works on the pinned
Omarchy baseline before expanding it.

- Run the [manual acceptance checklist](docs/testing.md) in a real graphical
  session and record Omarchy, Hyprland, Quickshell, driver, and hardware versions.
- Exercise login, shell loading, launch/focus behavior, Settings categories,
  appearance changes, lock/unlock, authentication, and suspend/resume.
- Exercise install, repeat install, recovery, and removal on that target.
- Capture actual Dawn and Dusk desktop screenshots, including open applications.

**Acceptance:** publish the results and outstanding failures; resolve blocking
session, security, configuration, or data-preservation failures. Login creates
one dock, shell logs and compositor diagnostics have no new errors, and removal
returns the recorded prior configuration.

## 2. Establish a consistent visual system

- Document shared typography, spacing, color, icon, surface, and motion choices.
- Apply them to the shell, launcher, Settings, dialogs, and notifications.
- Review the file manager, browser, and selected everyday applications across
  GTK, Qt, Electron, and XWayland where applicable; document toolkit limits.
- Check readable text, visible keyboard focus, long labels, light and dark
  appearances, scaling, and reduced-motion behavior.
- Keep technical status information quiet by default and available on demand.

**Acceptance:** publish a review of real desktop surfaces in Dawn and Dusk at
100%, 150%, and 200% display scale on supported configurations. Record and
resolve clipping, unreadable states, inconsistent controls, and accidental
monospace interface text. Application content uses fonts appropriate to its task.

## 3. Complete everyday graphical workflows

- Make launch, focus, switching, window controls, minimize/restore, and workspace
  navigation predictable with a pointer and keyboard.
- Resolve the prototype's maximize-button and shelf/dock limitations through
  supported behavior, or document an explicit compatibility boundary.
- Add persistent, user-editable dock pins and clear running/focus feedback.
- Improve Settings navigation and feedback for appearance, displays, audio,
  network, Bluetooth, power, notifications, and unavailable devices.
- Review file browsing, downloads, screenshots, external storage, default
  applications, and quiet notification handling as complete tasks.
- Preserve optional tiling and useful keyboard shortcuts.

**Acceptance:** someone unfamiliar with the configuration can complete those
tasks through the interface. Test repeated use, several windows per app, missing
desktop identities, disconnected hardware, and recovery from mistakes. Publish
remaining application-specific limits.

## 4. Make setup and maintenance approachable

- Design graphical first-run setup with an understandable preview of changes
  and access to backups and removal.
- Provide discoverable software installation and update workflows using
  maintained upstream capabilities.
- Present compatibility, progress, failures, restart requirements, and recovery
  in plain language, with diagnostics available when needed.
- Retain transactional writes, conflict detection, initial backups, and a
  documented command-line recovery path for a broken graphical session.
- Maintain a support table for inspected upstream versions and exercise real
  update and migration paths before adding a supported version.

**Acceptance:** record end-to-end setup, application installation, an update,
an interrupted operation and recovery, and removal on a supported target.
Unrelated settings survive. People can understand the result and next action
from the interface.

## 5. Earn a tested preview release

- Complete and publish the acceptance matrix with supported hardware and
  explicit limits, including multi-monitor, hotplug, fractional scaling,
  XWayland applications, trackpad input, sleep/wake, and missing hardware.
- Review keyboard navigation, focus, text readability, contrast, and motion
  preferences across the main workflows.
- Publish actual screenshots, installation and recovery instructions,
  compatibility information, known issues, and release notes.
- Repeat lifecycle checks after upstream changes and significant UI changes.

**Acceptance:** close blocking items from earlier milestones, publish the
evidence, and describe the release's support boundaries accurately. A daily-use
claim requires sustained use of the supported workflows on real systems.

## Later work

An overview, richer gestures, dock auto-hide or magnification, per-device tuning,
and broader customization can follow once the core workflows are dependable.
Evaluate each against the vision and its maintenance cost. Priorities may change
when real use exposes a more important problem.

## Tracking progress

Link implementation work to the milestone and user task it advances. Record
whether it is proposed, implemented, graphically tested, or accepted, together
with its evidence. Update this roadmap when scope or acceptance changes.
