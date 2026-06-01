import importlib.util
import sys
from pathlib import Path


DOCTOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "doctor.py"
SPEC = importlib.util.spec_from_file_location("doctor", DOCTOR_PATH)
doctor = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["doctor"] = doctor
SPEC.loader.exec_module(doctor)


def test_python_version_check_accepts_supported_version():
    result = doctor.check_python_version((3, 10, 0))

    assert result.ok
    assert result.name == "python"


def test_python_version_check_rejects_old_version():
    result = doctor.check_python_version((3, 9, 18))

    assert not result.ok


def test_executable_override_uses_existing_path():
    result = doctor.check_executable("ffmpeg", override=str(DOCTOR_PATH))

    assert result.ok
    assert "doctor.py" in result.detail


def test_render_text_includes_status_and_detail():
    rendered = doctor.render_text([doctor.CheckResult("sample", True, "ready")])

    assert "[ok] sample: ready" in rendered
