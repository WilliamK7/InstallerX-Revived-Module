"""Send one AOSP APK or a status message to one configured Telegram private chat."""

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys
from urllib import error, parse, request


MAX_DOCUMENT_BYTES = 50 * 1024 * 1024


def call_api(token, method, fields, apk=None):
    if apk is None:
        body = parse.urlencode(fields).encode("utf-8")
        content_type = "application/x-www-form-urlencoded"
    else:
        boundary = secrets.token_hex(24)
        parts = []
        for name, value in fields.items():
            parts.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode("utf-8")
            )
        parts.extend(
            [
                (
                    f"--{boundary}\r\n"
                    'Content-Disposition: form-data; name="document"; '
                    'filename="PackageInstaller.apk"\r\n'
                    "Content-Type: application/vnd.android.package-archive\r\n\r\n"
                ).encode("utf-8"),
                apk.read_bytes(),
                f"\r\n--{boundary}--\r\n".encode("utf-8"),
            ]
        )
        body = b"".join(parts)
        content_type = f"multipart/form-data; boundary={boundary}"

    api_request = request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        with request.urlopen(api_request, timeout=300) as response:
            payload = json.load(response)
    except error.HTTPError as exc:
        # HTTP exception URLs contain the bot token. Never print them or a traceback.
        raise RuntimeError(
            f"Telegram {method} failed (HTTP {exc.code}). "
            "Check BOT_TOKEN, CHAT_ID, /start and whether the bot is blocked."
        ) from None
    except (error.URLError, TimeoutError, OSError):
        raise RuntimeError(f"Telegram {method} failed: network connection error.") from None
    except ValueError:
        raise RuntimeError(f"Telegram {method} returned invalid JSON.") from None

    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError(f"Telegram rejected {method}; check the bot configuration.")
    return payload.get("result")


def private_chat(token, chat_id):
    chat = call_api(token, "getChat", {"chat_id": chat_id})
    if (
        not isinstance(chat, dict)
        or chat.get("type") != "private"
        or chat.get("id") != chat_id
    ):
        raise RuntimeError("CHAT_ID must identify your private chat; groups and channels are not allowed.")
    return chat_id


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", nargs="?", help="Path to the AOSP PackageInstaller APK")
    parser.add_argument("--caption", default="", help="Optional APK caption")
    parser.add_argument("--text", help="Send a plain status message")
    parser.add_argument("--check", action="store_true", help="Validate the private chat without sending")
    args = parser.parse_args(argv)
    if sum((args.apk is not None, args.text is not None, args.check)) != 1:
        parser.error("choose exactly one APK path, --text, or --check")
    if args.caption and not args.apk:
        parser.error("--caption requires an APK path")
    if args.text is not None and not args.text.strip():
        parser.error("--text must not be empty")
    if len(args.caption) > 1024 or (args.text is not None and len(args.text) > 4096):
        parser.error("caption or message exceeds Telegram's length limit")

    token = os.environ.get("BOT_TOKEN", "").strip()
    raw_chat_id = os.environ.get("CHAT_ID", "").strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise RuntimeError("BOT_TOKEN is missing or malformed.")
    if not re.fullmatch(r"[1-9][0-9]*", raw_chat_id):
        raise RuntimeError("CHAT_ID must be your positive numeric private-chat ID, not a username or group ID.")

    apk = Path(args.apk) if args.apk else None
    if apk is not None:
        if not apk.is_file() or apk.suffix.lower() != ".apk":
            raise RuntimeError("The APK file does not exist or has the wrong extension.")
        if not 0 < apk.stat().st_size <= MAX_DOCUMENT_BYTES:
            raise RuntimeError("The APK must be nonempty and no larger than the Bot API's 50 MB limit.")

    chat_id = private_chat(token, int(raw_chat_id))
    if args.check:
        print("Telegram private-chat configuration is valid.")
    elif args.text is not None:
        call_api(token, "sendMessage", {"chat_id": chat_id, "text": args.text})
        print("Status message sent to the configured private chat.")
    else:
        call_api(
            token,
            "sendDocument",
            {"chat_id": chat_id, "caption": args.caption},
            apk=apk,
        )
        print("AOSP APK sent to the configured private chat.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError) as exc:
        # Redact defensively and avoid tracebacks containing a credential-bearing URL.
        message = str(exc)
        token = os.environ.get("BOT_TOKEN", "").strip()
        if token:
            message = message.replace(token, "[redacted]")
        print(f"ERROR: {message}", file=sys.stderr)
        sys.exit(1)
