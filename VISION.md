# The Everest vision

**Everest builds on Omarchy to deliver a calm, cohesive, modern Linux desktop,
designed for comfortable everyday use.**

The project takes inspiration from the ease and attention to detail people
associate with macOS: predictable behavior, clear hierarchy, approachable
controls, and an interface that feels considered from the first login onward.
Everest gives those qualities its own identity on Linux.

This document describes the intended product. The [README](README.md) and
[roadmap](ROADMAP.md) distinguish the existing prototype from that destination.

## Who it is for

Everest is for someone who wants a capable Linux desktop that is comfortable
with a mouse or trackpad and easy to understand through the interface. They may
enjoy keyboard shortcuts and powerful tools, but should be able to complete
ordinary tasks without learning configuration syntax first.

That includes browsing, writing, managing files, using multiple applications,
connecting headphones, changing displays, taking screenshots, and maintaining
the system.

## The relationship with Omarchy

Omarchy supplies the underlying desktop technology and existing system
capabilities. Everest takes responsibility for how people encounter them:
defaults, navigation, visual design, application integration, and the path
through common tasks.

Prefer supported user configuration, documented interfaces, and small components
that can be maintained alongside upstream work. Preserve locking, authentication,
and the normal update path. Every supported upstream version needs recorded
compatibility evidence.

The current implementation is a reversible user layer for the pinned Omarchy
release. Future architectural changes should follow demonstrated experience
needs and an explicit maintenance plan.

## Design principles

### Consistency across the whole desktop

Define shared choices for type, spacing, color, icons, corners, and motion.
Apply them across the bar, dock, launcher, Settings, dialogs, and notifications,
then carry them into the selected everyday applications where their toolkits
allow it.

Dawn and Dusk are equally considered appearances. Each needs readable text,
clear selection and focus states, and coherent application surfaces. The
terminal retains an appropriate monospace font for its content.

### Comfortable, predictable interaction

Floating windows are the default. Opening, focusing, moving, resizing,
maximizing, minimizing or restoring, and closing windows should be understandable
with a pointer. Switching applications and workspaces should preserve a clear
sense of where things are.

Keyboard shortcuts and optional tiling extend that experience. Gestures need
discoverable alternatives. Controls should behave consistently across repeated
use and multiple displays.

### Graphical paths through everyday tasks

Provide visible routes to applications, files, search, settings, device
connections, display setup, appearance, software management, and updates.
Settings should use familiar names and explain the consequence of an action.

Setup and recovery also belong to the product. People should be able to see what
will change, understand errors, and find a clear way forward. Developer commands
and diagnostic details belong in documentation or an explicit advanced view.

### A quiet, modern visual identity

Use proportional interface typography, comfortable spacing, restrained color,
clear hierarchy, and real mountain photography. Build character through the
quality of the details. Reserve attention-grabbing color and motion for actions
or information that justify it.

Defaults should make room for the person's work. Keep technical readouts and
dense status information available through deliberate choices. Preserve
application names, recognizable branding, and honest descriptions of what the
system can do.

### Care that survives daily use

Design focus states, contrast, scaling, keyboard navigation, and motion
preferences alongside the default appearance. Test missing hardware, failed
connections, long labels, many open windows, and interrupted operations.

A beautiful first login is only the beginning. Updates, sleep and wake,
external displays, error handling, backups, and removal all need predictable
behavior.

## Scope and boundaries

Everest's scope includes the shell, window behavior, application defaults and
integration, first-run setup, settings, software and update workflows, and
recovery. Several of these are still roadmap work.

Keep the implementation small enough to maintain. Reuse reliable upstream
capabilities, make changes reversible where possible, and preserve unrelated
user settings. Any additional dependency needs a clear experience benefit and
a plan for updates and failure.

Everest does not provide macOS application compatibility. Linux applications
retain toolkit and compositor constraints. Document those limits and resolve
them deliberately when they interfere with the intended experience.

## How we judge progress

Review changes against complete everyday tasks. Can a person find the control,
understand it, finish the task, and return to their work without surprises?
Does it remain usable in both appearances, with a keyboard, at different
display scales, and when something fails?

Evidence includes real desktop screenshots, recorded interaction results, and
installation and recovery checks. Wallpapers and automated test results each
have a purpose; neither establishes the quality of the complete desktop.

The [roadmap](ROADMAP.md) turns these principles into milestones. New features
should make a specific part of this experience clearer, more consistent, or
more dependable.
