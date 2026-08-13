from __future__ import annotations

import argparse
import json
import sys

from ..fonnte import FonnteSendError, fonnte_default_country_code, fonnte_token, send_fonnte_text_message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a WhatsApp message through the Fonnte API.")
    parser.add_argument(
        "-n",
        "--number",
        required=True,
        help="Target WhatsApp number. Example: 08123456789",
    )
    parser.add_argument(
        "-m",
        "--message",
        required=True,
        help="Message body to send.",
    )
    parser.add_argument(
        "--country-code",
        default=None,
        help="Override default country code for local numbers. Example: 62",
    )
    return parser.parse_args()


def send_message(number: str, message: str, country_code: str) -> int:
    if not fonnte_token():
        print("FONNTE_TOKEN is not set. Please update your environment first.", file=sys.stderr)
        return 1

    try:
        response = send_fonnte_text_message(
            target_number=number,
            text=message,
            country_code=country_code,
        )
        print(json.dumps(response, indent=2))
        return 0
    except FonnteSendError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def main() -> int:
    args = parse_args()
    country_code = args.country_code or fonnte_default_country_code()
    return send_message(args.number, args.message, country_code)


if __name__ == "__main__":
    raise SystemExit(main())
