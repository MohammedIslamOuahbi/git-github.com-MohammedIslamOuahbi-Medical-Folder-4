import sys
from pathlib import Path

import uvicorn


def ensure_backend_on_path() -> None:
    backend_root = Path(__file__).resolve().parent
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)


if __name__ == "__main__":
    ensure_backend_on_path()
    from app.main import app

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
