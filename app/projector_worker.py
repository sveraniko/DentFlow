import asyncio

from app.worker import run_projector_worker_forever


def main() -> None:
    asyncio.run(run_projector_worker_forever())


if __name__ == "__main__":
    main()
