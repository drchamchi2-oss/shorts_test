# Media and Licensing Notes

This project intentionally keeps generated videos, local background music, local caches, and API credentials out of the repository. Contributors should treat all media and provider responses as inputs that need their own licensing review before publication.

## Source Expectations

- Prefer Wikimedia Commons or other sources with clear license metadata.
- Use Pexels and Pixabay fallbacks only when their current provider terms allow the intended use.
- Keep the local BGM file outside Git. The maintainer is responsible for confirming redistribution and publication rights for any music used in final videos.
- Do not commit downloaded images, generated videos, voice audio, subtitles, or temporary render files unless a future issue explicitly adds a small licensed fixture.

## Pre-Publication Checklist

Before publishing a generated video, review:

- The generated Korean script for factual accuracy and unsupported claims.
- `media_attribution.json`, including image URLs, providers, selection reasons, and license-review flags.
- Image source pages and license requirements.
- BGM and sound-effect rights.
- Whether any generated narration or overlay text implies certainty beyond the source material.
- Whether credits or attribution are required by the selected media licenses.

## Repository Hygiene

The `.gitignore` file excludes local keys, generated output, caches, and common media artifacts. If a new provider, cache, or output directory is added later, update `.gitignore` in the same pull request.
