import argparse

from eve_ascii.app import run_app


def main() -> None:
    parser = argparse.ArgumentParser(description="EVE ASCII terminal game")
    parser.add_argument(
        "--no-tutorial",
        action="store_true",
        help="Skip the opening tutorial and start in free play",
    )
    parser.add_argument(
        "--no-sound",
        action="store_true",
        help="Disable sound effects",
    )
    args = parser.parse_args()
    run_app(with_tutorial=not args.no_tutorial, sound_enabled=not args.no_sound)


if __name__ == "__main__":
    main()
