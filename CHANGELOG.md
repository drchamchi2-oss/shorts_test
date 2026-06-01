# Changelog

All notable changes to this project are documented here.

## v0.1.0 - 2026-06-01

### Added

- Korean short-form video generation pipeline in `main_gpt.py`.
- Public OSS documentation, MIT license, security policy, contribution guide, and GitHub templates.
- Environment example and dependency list.
- GitHub Actions CI with syntax checks, tests, Bandit static security scanning, and pip-audit dependency auditing.
- Release checklist and media/licensing guidance.
- Helper-function tests for path, JSON, caption, and cache-key behavior.

### Security

- Added repository guidance to avoid committing API keys, `.env`, generated credentials, private logs, or local media assets.
- Replaced SHA1-based URL cache keys with SHA256-based cache keys.
