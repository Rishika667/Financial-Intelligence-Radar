#!/usr/bin/env python3
"""
Reproducible Browser Screenshot Capture Script for Fundamentals Lens.
Starts the Streamlit application and captures desktop and mobile viewport screenshots
of all four application pages using Chrome DevTools Protocol (CDP) over WebSockets.
"""

import sys
import os
import time
import json
import base64
import subprocess
import urllib.request
import asyncio
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs" / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser"
]


def find_browser():
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None


async def send_cdp(ws, method, params=None, msg_id=1):
    payload = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(payload))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == msg_id:
            return resp.get("result", {})


async def capture_page(ws, url, output_path, width=1280, height=900, is_mobile=False, wait_sec=4):
    import websockets

    # Set viewport
    await send_cdp(ws, "Emulation.setDeviceMetricsOverride", {
        "width": width,
        "height": height,
        "deviceScaleFactor": 1,
        "mobile": is_mobile
    }, msg_id=10)

    # Navigate
    await send_cdp(ws, "Page.navigate", {"url": url}, msg_id=11)
    await asyncio.sleep(wait_sec)

    # Capture screenshot
    res = await send_cdp(ws, "Page.captureScreenshot", {"format": "png"}, msg_id=12)
    img_data = base64.b64decode(res["data"])

    with open(output_path, "wb") as f:
        f.write(img_data)
    print(f"Captured: {output_path.name} ({width}x{height}, {len(img_data):,} bytes)")


async def run_capture_pipeline():
    browser_exe = find_browser()
    if not browser_exe:
        print("ERROR: No compatible Chrome/Edge browser found for screenshot capture.")
        return 1

    port = 8501
    cdp_port = 9222
    streamlit_url = f"http://localhost:{port}"

    print(f"Starting Streamlit app on port {port}...")
    streamlit_proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            str(REPO_ROOT / "fundamentals_lens_app.py"),
            "--server.port", str(port),
            "--server.headless", "true"
        ],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Poll until Streamlit is ready
    ready = False
    for _ in range(30):
        try:
            with urllib.request.urlopen(streamlit_url, timeout=1) as response:
                if response.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(1)

    if not ready:
        print("ERROR: Streamlit failed to respond within 30 seconds.")
        streamlit_proc.terminate()
        return 1

    print("Streamlit app is ready. Launching headless browser with CDP...")
    browser_proc = subprocess.Popen(
        [
            browser_exe,
            "--headless=new",
            f"--remote-debugging-port={cdp_port}",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            streamlit_url
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    ws_url = None
    for _ in range(20):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=1) as resp:
                targets = json.loads(resp.read().decode())
                for t in targets:
                    if t.get("type") == "page" and "webSocketDebuggerUrl" in t:
                        ws_url = t["webSocketDebuggerUrl"]
                        break
                if ws_url:
                    break
        except Exception:
            time.sleep(0.5)

    if not ws_url:
        print("ERROR: Could not obtain CDP WebSocket debugger URL.")
        browser_proc.terminate()
        streamlit_proc.terminate()
        return 1

    print(f"Connected to CDP WebSocket: {ws_url}")
    import websockets

    try:
        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            await send_cdp(ws, "Page.enable", msg_id=1)

            # 1. Page 1: Overview Desktop
            await capture_page(
                ws, f"{streamlit_url}/?page=Overview",
                OUTPUT_DIR / "01_overview_desktop.png",
                width=1280, height=900, is_mobile=False, wait_sec=4
            )

            # 2. Page 2: Company Analysis Desktop
            await capture_page(
                ws, f"{streamlit_url}/?page=Company+Analysis",
                OUTPUT_DIR / "02_company_analysis_desktop.png",
                width=1280, height=950, is_mobile=False, wait_sec=4
            )

            # 3. Page 3: Peer Comparison Desktop
            await capture_page(
                ws, f"{streamlit_url}/?page=Peer+Comparison",
                OUTPUT_DIR / "03_peer_comparison_desktop.png",
                width=1280, height=950, is_mobile=False, wait_sec=4
            )

            # 4. Page 4: Data Integrity Desktop
            await capture_page(
                ws, f"{streamlit_url}/?page=Data+Integrity+%26+Methodology",
                OUTPUT_DIR / "04_data_integrity_desktop.png",
                width=1280, height=950, is_mobile=False, wait_sec=4
            )

            # 5. Page 2: Company Analysis Mobile
            await capture_page(
                ws, f"{streamlit_url}/?page=Company+Analysis",
                OUTPUT_DIR / "05_company_analysis_mobile.png",
                width=390, height=844, is_mobile=True, wait_sec=4
            )

        print("\nAll 5 visual QA screenshots successfully captured into docs/screenshots/!")
        ret = 0
    except Exception as e:
        print(f"Error during screenshot capture: {e}")
        ret = 1
    finally:
        browser_proc.terminate()
        streamlit_proc.terminate()

    return ret


if __name__ == "__main__":
    sys.exit(asyncio.run(run_capture_pipeline()))
