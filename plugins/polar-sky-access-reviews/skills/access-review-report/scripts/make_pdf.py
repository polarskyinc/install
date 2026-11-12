"""Print the rendered report HTML to PDF with a local headless Chrome or Chromium.

Usage: python3 make_pdf.py --html OUTPUT_FOLDER/report.html [--pdf OUTPUT_FOLDER/report.pdf] [--chrome PATH]
Exit code 3 means no Chrome or Chromium was found; the HTML is still usable.
"""

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

MAC_PATHS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)
LINUX_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge")


def find_chrome(explicit=None):
    """Return the path of a Chrome-family browser, or None."""
    candidates = [explicit, os.environ.get("CHROME_PATH")]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    if sys.platform == "darwin":
        for path in MAC_PATHS:
            if os.path.isfile(path):
                return path
    for name in LINUX_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def print_pdf(chrome, html_path, pdf_path):
    """Print one HTML file to PDF and return the PDF path."""
    profile = tempfile.mkdtemp(prefix="access-review-chrome-")
    try:
        command = [
            chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            f"--user-data-dir={profile}", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={pdf_path}", pathlib.Path(html_path).resolve().as_uri(),
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not os.path.isfile(pdf_path) or os.path.getsize(pdf_path) == 0:
        raise RuntimeError("Chrome finished but wrote no PDF.")
    return pdf_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--html", required=True)
    parser.add_argument("--pdf")
    parser.add_argument("--chrome", help="Path to Chrome or Chromium; CHROME_PATH also works")
    arguments = parser.parse_args(argv)
    pdf_path = arguments.pdf or os.path.splitext(arguments.html)[0] + ".pdf"
    chrome = find_chrome(arguments.chrome)
    if not chrome:
        print(
            "No Chrome or Chromium found. Open the HTML in Chrome, choose Print, set Destination to Save as PDF, "
            "paper Letter, margins Default, and turn on Background graphics.",
            file=sys.stderr,
        )
        return 3
    try:
        print(print_pdf(chrome, arguments.html, os.path.abspath(pdf_path)))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError) as error:
        print(f"Chrome could not print the PDF: {error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
