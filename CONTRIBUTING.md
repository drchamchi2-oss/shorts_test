# Contributing

Thanks for considering a contribution to `shorts_test`.

This project is intentionally small and maintainer-friendly. Keep changes focused, explain why they are needed, and avoid broad rewrites unless an issue clearly calls for them.

## Good First Contributions

- Improve setup documentation.
- Add small error-handling improvements.
- Improve reproducibility around ffmpeg, fonts, or BGM setup.
- Add tests or checks for pure helper functions.
- Improve issue reports with reproducible examples.

## Before Opening A Pull Request

1. Check whether an issue already exists.
2. Keep the change scoped to one problem.
3. Do not include API keys, `.env`, generated videos, private logs, or local media assets.
4. Update `README.md` when setup or behavior changes.
5. Run at least a syntax check:

```bash
python -m py_compile main_gpt.py
```

## Pull Request Checklist

- Explain what changed and why.
- Explain how you tested it.
- Call out any external API, ffmpeg, or media-source behavior that affects reproducibility.
- Confirm no secrets or private files are included.

## Maintainer Notes

The maintainer may ask for changes before merge. Reviews should prioritize correctness, reproducibility, security, licensing clarity, and keeping the workflow easy to inspect.
