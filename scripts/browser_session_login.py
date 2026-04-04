import argparse
from pathlib import Path


SUPPORTED_PLATFORMS = {
    "Blinkit": "https://blinkit.com/",
    "Instamart": "https://www.swiggy.com/instamart",
    "Amazon": "https://www.amazon.in/ap/signin",
    "Dmart": "https://www.dmart.in/",
    "Zepto": "https://www.zeptonow.com/",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Save a logged-in browser session for a grocery platform.")
    parser.add_argument("--platform", required=True, choices=sorted(SUPPORTED_PLATFORMS))
    parser.add_argument("--session-path", required=True)
    parser.add_argument("--login-url", default="")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise SystemExit(
            "Playwright is not installed. Run `pip install playwright` and "
            "`python -m playwright install chromium` first."
        ) from error

    session_path = Path(args.session_path)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    login_url = args.login_url.strip() or SUPPORTED_PLATFORMS[args.platform]

    print(f"Opening browser for {args.platform} login at: {login_url}")
    print("Log in manually in the opened browser window.")
    print("After login is complete, return here and press Enter to save the session.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded", timeout=45000)
        input()
        context.storage_state(path=str(session_path))
        context.close()
        browser.close()

    print(f"Saved session to {session_path}")


if __name__ == "__main__":
    main()
