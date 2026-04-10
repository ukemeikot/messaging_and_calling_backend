# Changelog

All notable changes to this project should be reflected in GitHub release notes.

This repository uses GitHub Actions to:

- run tests on pull requests and pushes
- keep a draft release/changelog updated on GitHub after merges to `main`
- publish a GitHub release when a version tag such as `v0.1.0` is pushed

## Unreleased

### Added

- Standardized repository documentation
- Feature inventory and implementation schema in `FEATURES.md`
- Pytest suite for core services and security helpers
- GitHub Actions workflow for CI, release drafting, and tagged releases
- Source CLI entrypoint support via `python -m messaging_sdk.cli`
- Customizable email composition with templates, theme values, hooks, and scaffolded email assets
- Python package metadata for installation and packaged email template assets
- Static project website with landing page, docs page, and copyable snippets
- GitHub Pages deployment workflow, custom domain configuration, and PR branch policy enforcement

### Changed

- `messaging_sdk` package imports are now lighter so non-app tooling can run without full app bootstrap
- Call models now generate UUIDs on the Python side as well as PostgreSQL side, which improves testability
- README and contribution guidance now document built-in SDK usage and require docs to ship with feature changes
- README and deployment docs now document GitHub package installs, protected branch promotion, and website hosting steps

### Security

- Added a documented review of current implementation risks in `SECURITY.md`
