"""Fetch and parse all four sources: `python -m rulebook.corpus [--refresh] [uk de fi el]`."""

import sys

from . import de, el, fi, uk

SOURCES = {"uk": uk, "de": de, "fi": fi, "el": el}


def main(argv: list[str]) -> int:
    refresh = "--refresh" in argv
    wanted = [a for a in argv if not a.startswith("--")] or list(SOURCES)
    failed = []
    for name in wanted:
        try:
            records = SOURCES[name].run(refresh=refresh)
            print(f"{name}: {len(records)} sections")
        except Exception as e:  # one blocked source must not stop the others
            print(f"{name}: FAILED {type(e).__name__}: {e}", file=sys.stderr)
            failed.append(name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
