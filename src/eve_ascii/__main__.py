import argparse

from eve_ascii.app import run_app


def main() -> None:
    parser = argparse.ArgumentParser(description="EVE ASCII terminal game")
    parser.add_argument(
        "--no-tutorial",
        action="store_true",
        help="Skip the opening tutorial and start in free play",
    )
    args = parser.parse_args()
    run_app(with_tutorial=not args.no_tutorial)


if __name__ == "__main__":
    main()
