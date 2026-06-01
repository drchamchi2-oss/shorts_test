# Roadmap

This roadmap tracks near-term work that keeps `shorts_test` useful, testable, and safer to maintain as a public OSS project.

## Current Focus

- Keep the video generation pipeline reproducible for new contributors.
- Improve security and dependency maintenance through CI, CodeQL, Dependabot, Bandit, and pip-audit.
- Make media attribution and licensing review easier before generated videos are published.
- Expand pure helper tests before larger refactors.

## Completed

- [#9](https://github.com/drchamchi2-oss/shorts_test/issues/9): Migrated URL cache keys to SHA256 and removed the Bandit B324 skip.
- [#10](https://github.com/drchamchi2-oss/shorts_test/issues/10): Added fixture-based tests for subtitle timing edge cases.
- [#11](https://github.com/drchamchi2-oss/shorts_test/issues/11): Recorded media provider attribution metadata in generated outputs.
- [#12](https://github.com/drchamchi2-oss/shorts_test/issues/12): Added dry-run mode for topic and script generation checks.
- [#13](https://github.com/drchamchi2-oss/shorts_test/issues/13): Split media and rendering helpers into focused modules.

## Near-Term Issues

No open roadmap issues remain.

## Release Readiness

The first release target is `v0.1.0`. Before tagging, run the checks in [`docs/release-checklist.md`](docs/release-checklist.md), confirm generated media is not committed, and review media/BGM licensing requirements.

## Non-Goals

- No committed API keys, `.env` files, generated videos, downloaded cache files, or local BGM assets.
- No broad rewrite until pure helper coverage is stronger.
- No generated media publishing without source/license review.