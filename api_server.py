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

from fastapi import Body  # noqa: E402
from backend import server as server_module  # noqa: E402
from backend.ai_provider import DEFAULT_API_BASE, DEFAULT_MODEL, ProviderConfig, validate_connectivity  # noqa: E402

# Keep the legacy server's public/runtime configuration contract while switching
# its actual defaults to the production OpenAI-compatible provider. The key stays
# empty and must be supplied by the local user or environment.
server_module.BUILT_IN_VISION_API_BASE = DEFAULT_API_BASE
server_module.BUILT_IN_VISION_MODEL = DEFAULT_MODEL
server_module.BUILT_IN_VISION_API_KEY = ""

app = server_module.app  # noqa: E402,F401


@app.post("/api/config/validate")
def validate_runtime_provider(payload: dict = Body(default={})):
    """Validate real provider authentication before a fan-out generation job starts."""
    runtime = server_module._runtime_ai_config(
        str(payload.get("apiBase") or ""),
        str(payload.get("model") or ""),
        str(payload.get("apiKey") or ""),
    )
    config = ProviderConfig(
        api_base=runtime["apiBase"],
        model=runtime["model"],
        api_key=runtime["apiKey"],
    )
    # validate_connectivity deliberately returns only key-safe public fields.
    return validate_connectivity(config)
