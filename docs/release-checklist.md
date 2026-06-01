# Release Checklist

Use this checklist before tagging a public release.

## Required Checks

Run the same checks used by CI:

```bash
python -m py_compile main_gpt.py scripts/doctor.py
python -m pytest
python -m bandit -r main_gpt.py scripts -x tests -ll -s B324
python -m pip_audit -r requirements.txt
```

`B324` is skipped because the existing SHA1 use is for non-security cache keying. Remove the skip after migrating that cache key to SHA256.

## Manual Review

- Confirm `.env`, API keys, generated credentials, private logs, and local media are not committed.
- Confirm `bgm_no_attrib/mystery.mp3` exists locally if you plan to run the full renderer.
- Confirm BGM and downloaded media licenses before publishing generated videos.
- Review generated scripts for factual accuracy and unsupported claims.
- Confirm `CHANGELOG.md` describes the release.

## Tagging

Recommended first release tag:

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

Then create a GitHub release from the tag and include the release notes from `CHANGELOG.md`.
