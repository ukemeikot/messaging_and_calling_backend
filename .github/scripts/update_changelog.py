from pathlib import Path
import os


CHANGELOG_PATH = Path("CHANGELOG.md")
UNRELEASED_HEADING = "## Unreleased"


def main() -> int:
    category = os.environ["CHANGELOG_CATEGORY"].strip()
    entry = os.environ["CHANGELOG_ENTRY"].strip()

    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    if entry in text:
        return 0

    heading = f"### {category}"
    if UNRELEASED_HEADING not in text:
        text = f"{text.rstrip()}\n\n{UNRELEASED_HEADING}\n"

    intro, body = text.split(UNRELEASED_HEADING, 1)

    if heading in body:
        body = body.replace(heading, f"{heading}\n\n{entry}", 1)
    else:
        body = f"\n\n{heading}\n\n{entry}{body}"

    CHANGELOG_PATH.write_text(intro + UNRELEASED_HEADING + body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
