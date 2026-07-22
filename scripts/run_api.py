import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicia la API PitchProphet.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()
    uvicorn.run(
        "src.api.app:app",
        host=arguments.host,
        port=arguments.port,
    )


if __name__ == "__main__":
    main()
