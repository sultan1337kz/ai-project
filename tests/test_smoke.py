import importlib


def test_package_is_importable() -> None:
    # Guards the src-layout install: fails if `triage` is not installed into the venv.
    module = importlib.import_module("triage")
    assert module.__name__ == "triage"
