# Contributing to Everest

Start with the [vision](VISION.md) and [roadmap](ROADMAP.md). Everest aims to
make everyday desktop tasks comfortable, consistent, and approachable on top of
Omarchy. Contributions should move a specific part of that experience forward.

The current repository is a prototype targeting the version in
[upstream.lock.json](upstream.lock.json). The
[architecture](docs/architecture.md) describes its inspected interfaces.

## Propose the experience

Describe the task someone is trying to complete, the problem they encounter,
and the behavior they should get after the change. Include how they discover
the control and what happens if the action fails or hardware is unavailable.

For visible changes, explain the fit with Dawn and Dusk, the existing visual
language, keyboard navigation, display scaling, and motion preferences.
Keep technical implementation details in developer documentation or an
explicit diagnostic view.

Use clear labels, proportionate interface typography, comfortable spacing, and
restrained color. Preserve recognizable application identities. For imagery,
follow the existing photographic direction and the asset license.

## Build on the existing foundation

Prefer supported Omarchy interfaces and small components with clear ownership.
Preserve lock and authentication services, the upstream update path, and
unrelated user configuration. Explain new dependencies and how they will be
updated and recovered if they fail.

Maintain installer idempotence, backups, conflict checks, recovery, and removal.
Document live effects that fall outside the file transaction. Read the existing
implementation before changing its integration points.

## Show what was verified

Use the [testing guide](docs/testing.md) and the checks appropriate to the
change. Run source and installer checks through the repository's Validate
workflow. Add focused regression coverage for changed behavior where it can
establish something useful.

For UI changes, include actual Dawn and Dusk desktop screenshots and record the
tested upstream version, relevant hardware, display scale, and interaction
results. Separate automated results from real graphical results. If graphical
validation is unavailable, keep that limitation explicit and acceptance pending.

Wallpaper previews illustrate backgrounds. Use screenshots of the running
desktop to demonstrate interface work.

## Keep the project honest

Describe what works now and what remains planned. Update the relevant roadmap,
installation, shortcut, or compatibility documentation when behavior changes.
Make release claims only when the corresponding acceptance evidence exists.
