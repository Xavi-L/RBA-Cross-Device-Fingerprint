#!/usr/bin/env python3
"""Minimal Sauce Labs Appium smoke test.

Usage:
  python3 sauce_appium_smoke.py

If the uploaded Sauce Storage filename is different:
  python3 sauce_appium_smoke.py --app storage:filename=featureapp-debug.apk
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from appium import webdriver
from appium.options.android import UiAutomator2Options


DEFAULT_REGION = "us-west-1"
DEFAULT_BUILD = "appium-build-1CHEN"
DEFAULT_APP = "storage:filename=app-debug.apk"
DEFAULT_DEVICE_NAME = "Android GoogleAPI Emulator"
DEFAULT_PLATFORM_VERSION = "12.0"
DEFAULT_AUTOMATION = "UiAutomator2"
DEFAULT_TEST_NAME = "HybridGuard Appium smoke"
SAUCE_USERNAME = "oauth-lx2310282802-32696"
SAUCE_ACCESS_KEY = "b25a9ae9-0cf0-4e4d-9457-464223b8875c"


def env_or_default(name: str, default: str) -> str:
    return os.environ.get(name, "").strip() or default


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start one Android Appium session on Sauce Labs and mark the job result."
    )
    parser.add_argument(
        "--username",
        default=env_or_default("SAUCE_USERNAME", SAUCE_USERNAME),
        help="Sauce Labs username. Defaults to SAUCE_USERNAME, then the script constant.",
    )
    parser.add_argument(
        "--access-key",
        default=env_or_default("SAUCE_ACCESS_KEY", SAUCE_ACCESS_KEY),
        help="Sauce Labs access key. Defaults to SAUCE_ACCESS_KEY, then the script constant.",
    )
    parser.add_argument(
        "--region",
        default=env_or_default("SAUCE_REGION", DEFAULT_REGION),
        help=f"Sauce data center region. Default: {DEFAULT_REGION}.",
    )
    parser.add_argument(
        "--app",
        default=env_or_default("SAUCE_APP", DEFAULT_APP),
        help=f"Uploaded app reference. Default: {DEFAULT_APP}.",
    )
    parser.add_argument(
        "--build",
        default=env_or_default("SAUCE_BUILD", DEFAULT_BUILD),
        help=f"Sauce build id/name. Default: {DEFAULT_BUILD}.",
    )
    parser.add_argument(
        "--name",
        default=env_or_default("SAUCE_TEST_NAME", DEFAULT_TEST_NAME),
        help=f"Sauce test name. Default: {DEFAULT_TEST_NAME}.",
    )
    parser.add_argument(
        "--device-name",
        default=env_or_default("SAUCE_DEVICE_NAME", DEFAULT_DEVICE_NAME),
        help=f"Android device name. Default: {DEFAULT_DEVICE_NAME}.",
    )
    parser.add_argument(
        "--platform-version",
        default=env_or_default("SAUCE_PLATFORM_VERSION", DEFAULT_PLATFORM_VERSION),
        help=f"Android platform version. Default: {DEFAULT_PLATFORM_VERSION}.",
    )
    parser.add_argument(
        "--orientation",
        default=env_or_default("SAUCE_DEVICE_ORIENTATION", "PORTRAIT"),
        choices=("PORTRAIT", "LANDSCAPE"),
        help="Device orientation.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=int(env_or_default("SAUCE_WAIT_SECONDS", "5")),
        help="Seconds to keep the app open after session creation.",
    )
    parser.add_argument(
        "--remote-url",
        default=os.environ.get("SAUCE_REMOTE_URL", "").strip(),
        help="Override the Sauce endpoint. Defaults to the selected region.",
    )
    parser.add_argument(
        "--screenshot",
        default=os.environ.get("SAUCE_SCREENSHOT", "").strip(),
        help="Optional local path for one screenshot after the app starts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print redacted capabilities without starting a Sauce session.",
    )
    return parser.parse_args()


def build_remote_url(args: argparse.Namespace) -> str:
    if args.remote_url:
        return args.remote_url
    return f"https://ondemand.{args.region}.saucelabs.com:443/wd/hub"


def build_capabilities(args: argparse.Namespace) -> dict[str, object]:
    return {
        "platformName": "Android",
        "appium:app": args.app,
        "appium:deviceName": args.device_name,
        "appium:platformVersion": args.platform_version,
        "appium:automationName": DEFAULT_AUTOMATION,
        "appium:autoGrantPermissions": True,
        "appium:newCommandTimeout": 90,
        "sauce:options": {
            "username": args.username,
            "accessKey": args.access_key,
            "build": args.build,
            "name": args.name,
            "deviceOrientation": args.orientation,
        },
    }


def to_options(caps: dict[str, object]) -> UiAutomator2Options:
    options = UiAutomator2Options()
    for key, value in caps.items():
        options.set_capability(key, value)
    return options


def redacted(caps: dict[str, object]) -> dict[str, object]:
    clean_caps = dict(caps)
    sauce_options = dict(clean_caps.get("sauce:options", {}))
    if sauce_options.get("accessKey"):
        sauce_options["accessKey"] = "***"
    clean_caps["sauce:options"] = sauce_options
    return clean_caps


def require_credentials(args: argparse.Namespace) -> None:
    if args.username and args.access_key:
        return
    print(
        "Missing Sauce credentials. Fill SAUCE_USERNAME and SAUCE_ACCESS_KEY at the top of this script, or pass them with CLI/env:",
        file=sys.stderr,
    )
    print("  export SAUCE_USERNAME='oauth-...'", file=sys.stderr)
    print("  export SAUCE_ACCESS_KEY='...'", file=sys.stderr)
    print("  python3 sauce_appium_smoke.py", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    args = parse_args()
    caps = build_capabilities(args)
    remote_url = build_remote_url(args)

    print("Sauce endpoint:", remote_url)
    print("Capabilities:")
    print(json.dumps(redacted(caps), indent=2, sort_keys=True))

    if args.dry_run:
        print("Dry run only; no Sauce session was started.")
        return 0

    require_credentials(args)

    driver = None
    job_status = "failed"
    try:
        print("Starting Sauce Labs Appium session...")
        driver = webdriver.Remote(command_executor=remote_url, options=to_options(caps))
        print("Session started:", driver.session_id)

        try:
            print("Current package:", driver.current_package)
            print("Current activity:", driver.current_activity)
        except Exception as exc:
            print("Session is alive, but package/activity lookup failed:", exc)

        if args.screenshot:
            screenshot_path = Path(args.screenshot).expanduser()
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            driver.get_screenshot_as_file(str(screenshot_path))
            print("Saved screenshot:", screenshot_path)

        if args.wait_seconds > 0:
            print(f"Keeping the app open for {args.wait_seconds}s...")
            time.sleep(args.wait_seconds)

        job_status = "passed"
        print("Smoke test passed.")
        return 0
    except Exception as exc:
        print("Smoke test failed:", exc, file=sys.stderr)
        return 1
    finally:
        if driver is not None:
            try:
                driver.execute_script("sauce:job-result=" + job_status)
                print("Marked Sauce job as:", job_status)
            except Exception as exc:
                print("Could not mark Sauce job result:", exc, file=sys.stderr)
            finally:
                driver.quit()
                print("Session closed.")


if __name__ == "__main__":
    raise SystemExit(main())
