# Changelog

All notable changes to this project are documented here.

## v0.1.0 - 2026-06-01

### Added

- Korean short-form video generation pipeline in `main_gpt.py`.
- Public OSS documentation, MIT license, security policy, contribution guide, and GitHub templates.
- Environment example and dependency list.
- GitHub Actions CI with syntax checks, tests, Bandit static security scanning, and pip-audit dependency auditing.
- Release checklist and media/licensing guidance.
- Local doctor script for runtime prerequisite checks.
- Public roadmap for near-term maintenance issues.
- Helper-function tests for path, JSON, and caption behavior.
- Fixture-based tests for subtitle timing edge cases.
- Dry-run mode for script and media-attribution checks.
- Focused media and rendering helper modules.

### Security

- Added repository guidance to avoid committing API keys, `.env`, generated credentials, private logs, or local media assets.
- Added CI-enforced static security scanning and dependency vulnerability auditing.
- Replaced SHA1 image cache keys with SHA256 and removed the Bandit B324 skip.
- Added generated media attribution metadata for source/license review.