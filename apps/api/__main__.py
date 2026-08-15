import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "apps.api.main:app",
        host=os.environ.get("API_HOST", "127.0.0.1"),
        port=int(os.environ.get("API_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
