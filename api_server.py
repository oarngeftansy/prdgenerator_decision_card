import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
python_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
runtime_packages = ROOT / "runtime_packages"
calibration_packages = ROOT / "calibration_packages"


def _is_compatible_dependency_root(path: Path) -> bool:
    return any((path / "pydantic_core").glob(f"_pydantic_core.{python_tag}-*.pyd"))


dependency_root = next(
    (path for path in (runtime_packages, calibration_packages) if _is_compatible_dependency_root(path)),
    None,
)
if dependency_root is not None:
    sys.path.insert(0, str(dependency_root))
sys.path.insert(0, str(ROOT))

from backend.server import app  # noqa: E402,F401
