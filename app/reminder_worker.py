import asyncio

from app.worker import run_reminder_worker_forever


def main() -> None:
    asyncio.run(run_reminder_worker_forever())


if __name__ == "__main__":
    main()
