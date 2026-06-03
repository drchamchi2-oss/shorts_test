# shorts_test

[![Python CI](https://github.com/drchamchi2-oss/shorts_test/actions/workflows/python-ci.yml/badge.svg)](https://github.com/drchamchi2-oss/shorts_test/actions/workflows/python-ci.yml)
[![CodeQL](https://github.com/drchamchi2-oss/shorts_test/actions/workflows/codeql.yml/badge.svg)](https://github.com/drchamchi2-oss/shorts_test/actions/workflows/codeql.yml)

`shorts_test` is a Python pipeline for generating Korean short-form videos about ancient artifacts, archaeological sites, and ancient-civilization mysteries.

The script builds a roughly 60-second vertical video by selecting a topic from public web sources, drafting a Korean narration with OpenAI, collecting public-source imagery, generating TTS audio, rendering scenes with ffmpeg, burning subtitles, and cleaning intermediate files.

## What It Does

- Selects archaeology and ancient-mystery topics from Wikipedia and trend sources.
- Generates a Korean short-form script with scene-level narration.
- Collects images from Wikimedia Commons, with optional Pexels and Pixabay fallback.
- Creates OpenAI TTS narration.
- Renders 1080x1920 video scenes with title overlays, zoom/pan motion, subtitles, and BGM.
- Keeps the final output, generated script, and source images while cleaning temporary media files.

## Requirements

- Python 3.10+
- ffmpeg and ffprobe available on `PATH`, or pass `--ffmpeg_path`
- An OpenAI API key
- A local BGM file at `bgm_no_attrib/mystery.mp3`
- Optional API keys for Pexels and Pixabay image fallback

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
```

For development and CI-equivalent checks:

```bash
python -m pip install -r requirements-dev.txt
```

Create a local `.env` file from the example:

```bash
copy .env.example .env
```

Then edit `.env` and add your own keys. Do not commit `.env`.

## Usage

```bash
python main_gpt.py run --verbose
```

To check topic and script generation without rendering video, audio, or images:

```bash
python main_gpt.py run --dry_run --verbose
```

If ffmpeg is not on `PATH`:

```bash
python main_gpt.py run --ffmpeg_path C:\ffmpeg\bin\ffmpeg.exe --verbose
```

Generated files are written under `out_araboza/`. Full runs write `final.mp4`, `script.json`, `media_attribution.json`, and selected source images. Dry runs write `script.json` and `media_attribution.json`.

## Development Checks

Run the local checks before opening a pull request:

```bash
python -m py_compile main_gpt.py shorts_media.py shorts_rendering.py scripts/doctor.py
python -m pytest
python -m bandit -r main_gpt.py shorts_media.py shorts_rendering.py scripts -x tests -ll
python -m pip_audit -r requirements.txt
```

The GitHub Actions workflow runs the same syntax, test, static security, and dependency-audit checks on pull requests and pushes to `main`.

To check local runtime prerequisites before generating a video:

```bash
python scripts/doctor.py
```

## Configuration

Required environment variable:

```text
OPENAI_API_KEY=your_openai_api_key
```

Optional environment variables:

```text
PEXELS_API_KEY=your_pexels_api_key
PIXABAY_API_KEY=your_pixabay_api_key
```

The repository intentionally does not include private keys, generated videos, local cache files, or BGM assets. Use only media that you are allowed to use and redistribute.

## Media And Licensing

Review `docs/media-and-licensing.md` before publishing generated videos or adding new media providers.

## Releases

Use `docs/release-checklist.md` before tagging a public release.

## Project Status

This project is early-stage OSS. The current goal is to make the single-file workflow reproducible, inspectable, and easier to maintain.

See `ROADMAP.md` for the current maintenance plan and near-term issues.

Known limitations:

- The script depends on live web APIs and external media sources.
- Output quality depends on available images, API responses, and local ffmpeg setup.
- BGM licensing is the user's responsibility.
- The generated script should be reviewed before publishing videos publicly.

## Security

Never commit API keys, `.env`, generated credentials, private logs, private datasets, or paid/proprietary media assets. See `SECURITY.md` for reporting guidance.

## Contributing

Focused issues and pull requests are welcome. See `CONTRIBUTING.md` before opening a PR.

## License

MIT. See `LICENSE`.