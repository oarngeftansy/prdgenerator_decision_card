import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8014)
    parser.add_argument("--jobs-root", required=True)
    parser.add_argument("--packages", default="runtime_packages_server")
    args = parser.parse_args()

    workspace = Path(__file__).resolve().parents[1]
    packages = (workspace / args.packages).resolve()
    jobs_root = Path(args.jobs_root).resolve()
    sys.path.insert(0, str(workspace))
    sys.path.insert(0, str(packages))
    os.environ["PRD_JOBS_ROOT"] = str(jobs_root)

    import uvicorn

    uvicorn.run("backend.server:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
