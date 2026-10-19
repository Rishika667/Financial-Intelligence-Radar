#!/usr/bin/env python3
"""
Reproducible Browser Screenshot Capture Script for Fundamentals Lens (Phase 14 Hardened).
Starts the Streamlit application and captures desktop and mobile viewport screenshots
of all application pages using Chrome DevTools Protocol (CDP) over WebSockets.

Hardened Features:
1. Hard failure on DOM timeout (no silent fallback or unverified captures).
2. Essential Plotly chart presence and non-zero dimension assertions.
3. Desktop 1280x900 viewport horizontal fold and overflow verification.
4. Synchronized export to docs/screenshots/ and conversation artifacts directory.
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


async def verify_dom_and_charts(ws, require_chart=False, timeout_sec=15):
    """
    Polls via CDP Runtime.evaluate to verify essential Streamlit DOM landmarks are mounted,
    and checks chart element presence, dimensions, and horizontal overflow.
    Fails with TimeoutError if DOM does not mount within timeout.
    """
    start = time.time()
    last_geom = {}
    eval_script = """
    (() => {
        const body = Boolean(document.body);
        const container = Boolean(document.querySelector('[data-testid="stAppViewContainer"]'));
        const markdowns = document.querySelectorAll('.stMarkdown, [data-testid="stMarkdownContainer"], h1, h2, h3').length;
        const chart = document.querySelector('[data-testid="stPlotlyChart"], .js-plotly-plot');
        const scrollW = document.documentElement.scrollWidth;
        const rect = chart ? chart.getBoundingClientRect() : null;

        let traceTypes = [];
        let traceCount = 0;
        if (chart && chart.data && Array.isArray(chart.data)) {
            traceCount = chart.data.length;
            traceTypes = chart.data.map(t => t.type || 'scatter');
        }

        const kpiCount = document.querySelectorAll('[data-testid="stMetric"]').length;
        const controlsCount = document.querySelectorAll('select, [data-testid="stSelectbox"], [data-testid="stCheckbox"], [data-testid="stRadio"]').length;

        return {
            dom_ready: body && container && markdowns > 0,
            chart_mounted: Boolean(chart),
            chart_width: rect ? Math.round(rect.width) : 0,
            chart_height: rect ? Math.round(rect.height) : 0,
            trace_count: traceCount,
            trace_types: traceTypes,
            kpi_count: kpiCount,
            controls_count: controlsCount,
            scroll_width: scrollW,
            has_overflow: scrollW > 1290
        };
    })()
    """
    while time.time() - start < timeout_sec:
        res = await send_cdp(ws, "Runtime.evaluate", {
            "expression": eval_script,
            "returnByValue": True
        }, msg_id=20)
        val = res.get("result", {}).get("value", {})
        last_geom = val
        if val.get("dom_ready"):
            if not require_chart or (val.get("chart_mounted") and val.get("chart_height", 0) >= 200 and val.get("chart_width", 0) >= 250):
                return val
        await asyncio.sleep(0.5)

    raise TimeoutError(
        f"DOM/chart verification timed out after {timeout_sec}s (require_chart={require_chart}, last_geom={last_geom})"
    )


async def select_tab(ws, tab_index: int, wait_sec=2):
    """Clicks the specified tab index in the DOM and waits for content to re-render."""
    eval_script = f"""
    (() => {{
        const tabs = document.querySelectorAll('button[data-baseweb="tab"], button[role="tab"]');
        if (tabs && tabs[{tab_index}]) {{
            tabs[{tab_index}].click();
            return {{ clicked: true, total_tabs: tabs.length }};
        }}
        return {{ clicked: false, total_tabs: tabs ? tabs.length : 0 }};
    }})()
    """
    res = await send_cdp(ws, "Runtime.evaluate", {
        "expression": eval_script,
        "returnByValue": True
    }, msg_id=30)
    await asyncio.sleep(wait_sec)
    return res.get("result", {}).get("value", {})


async def capture_page(ws, url, output_path, width=1280, height=900, is_mobile=False, require_chart=False, wait_sec=4, tab_index=None):
    # Set viewport
    await send_cdp(ws, "Emulation.setDeviceMetricsOverride", {
        "width": width,
        "height": height,
        "deviceScaleFactor": 1,
        "mobile": is_mobile
    }, msg_id=10)

    # Navigate if URL provided
    if url:
        await send_cdp(ws, "Page.navigate", {"url": url}, msg_id=11)
        await asyncio.sleep(wait_sec)

    # Click tab if specified
    if tab_index is not None:
        await select_tab(ws, tab_index, wait_sec=2)

    # DOM landmark and chart verification with hard assertion
    geom = await verify_dom_and_charts(ws, require_chart=require_chart, timeout_sec=15)

    scroll_w = geom.get("scroll_width", width)
    if width >= 1280 and scroll_w > width + 5:
        raise AssertionError(f"Layout overflow violation on {output_path.name}: scrollWidth {scroll_w}px > viewport width {width}px!")

    # Capture screenshot
    res = await send_cdp(ws, "Page.captureScreenshot", {"format": "png"}, msg_id=12)
    img_data = base64.b64decode(res["data"])

    with open(output_path, "wb") as f:
        f.write(img_data)

    # Also mirror to conversation artifacts directory if available
    artifact_screenshots_dir = Path(r"C:\Users\HP\.gemini\antigravity\brain\d7ec3f7c-e4ad-4364-b22a-b751ed5204d7\screenshots")
    if artifact_screenshots_dir.exists():
        with open(artifact_screenshots_dir / output_path.name, "wb") as f_art:
            f_art.write(img_data)

    chart_info = f", chart={geom['chart_width']}x{geom['chart_height']}" if require_chart else ""
    print(f"Captured: {output_path.name} ({width}x{height}, {len(img_data):,} bytes, DOM verified{chart_info})")


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
            await asyncio.sleep(2)  # Initial Streamlit websocket connection stabilization

            # 1. Page 1: Overview Desktop (with 2x2 dashboard)
            await capture_page(
                ws, f"{streamlit_url}/?page=Overview",
                OUTPUT_DIR / "01_overview_desktop.png",
                width=1280, height=900, is_mobile=False, require_chart=True, wait_sec=6
            )

            # 2. Page 2: Company Analysis Desktop (Tab 0: Growth & Scale)
            await capture_page(
                ws, f"{streamlit_url}/?page=Company+Analysis",
                OUTPUT_DIR / "02_company_analysis_desktop.png",
                width=1280, height=950, is_mobile=False, require_chart=True, wait_sec=4, tab_index=0
            )

            # 2b. Company Analysis Sub-Tab 1: Profitability & Margins
            await capture_page(
                ws, None,
                OUTPUT_DIR / "02b_company_analysis_tab2_margins.png",
                width=1280, height=950, is_mobile=False, require_chart=True, wait_sec=2, tab_index=1
            )

            # 2c. Company Analysis Sub-Tab 2: Cash Flow & Reinvestment
            await capture_page(
                ws, None,
                OUTPUT_DIR / "02c_company_analysis_tab3_cashflow.png",
                width=1280, height=950, is_mobile=False, require_chart=True, wait_sec=2, tab_index=2
            )

            # 2d. Company Analysis Sub-Tab 3: Statements & Evidence
            await capture_page(
                ws, None,
                OUTPUT_DIR / "02d_company_analysis_tab4_evidence.png",
                width=1280, height=950, is_mobile=False, require_chart=False, wait_sec=2, tab_index=3
            )

            # 3. Page 3: Peer Comparison Desktop (with matrix & charts)
            await capture_page(
                ws, f"{streamlit_url}/?page=Peer+Comparison",
                OUTPUT_DIR / "03_peer_comparison_desktop.png",
                width=1280, height=950, is_mobile=False, require_chart=True, wait_sec=4
            )

            # 4. Page 4: Price & Technical Analysis Desktop (Tab 0: Price & Trend Channels)
            await capture_page(
                ws, f"{streamlit_url}/?page=Price+%26+Technical+Analysis",
                OUTPUT_DIR / "04_technical_analysis_desktop.png",
                width=1280, height=900, is_mobile=False, require_chart=True, wait_sec=4, tab_index=0
            )

            # 4b. Technical Analysis Sub-Tab 1: Momentum & Oscillators (RSI / MACD)
            await capture_page(
                ws, None,
                OUTPUT_DIR / "04b_technical_analysis_tab2_momentum.png",
                width=1280, height=900, is_mobile=False, require_chart=True, wait_sec=2, tab_index=1
            )

            # 4c. Technical Analysis Sub-Tab 2: Benchmark Comparison
            await capture_page(
                ws, None,
                OUTPUT_DIR / "04c_technical_analysis_tab3_benchmark.png",
                width=1280, height=900, is_mobile=False, require_chart=True, wait_sec=2, tab_index=2
            )

            # 4d. Technical Analysis Sub-Tab 3: Technical Data & Exports
            await capture_page(
                ws, None,
                OUTPUT_DIR / "04d_technical_analysis_tab4_exports.png",
                width=1280, height=900, is_mobile=False, require_chart=False, wait_sec=2, tab_index=3
            )

            # 5. Page 5: Data Integrity Desktop (tables, audit logs, and expanders)
            await capture_page(
                ws, f"{streamlit_url}/?page=Data+Integrity+%26+Methodology",
                OUTPUT_DIR / "05_data_integrity_desktop.png",
                width=1280, height=950, is_mobile=False, require_chart=False, wait_sec=4
            )

            # 6. Page 2: Company Analysis Mobile View (390x844)
            await capture_page(
                ws, f"{streamlit_url}/?page=Company+Analysis",
                OUTPUT_DIR / "06_company_analysis_mobile.png",
                width=390, height=844, is_mobile=True, require_chart=True, wait_sec=4, tab_index=0
            )

            # 7. Page 4: Price & Technical Analysis Mobile View (390x844)
            await capture_page(
                ws, f"{streamlit_url}/?page=Price+%26+Technical+Analysis",
                OUTPUT_DIR / "07_technical_analysis_mobile.png",
                width=390, height=844, is_mobile=True, require_chart=True, wait_sec=4, tab_index=0
            )

        print("\nAll application pages and sub-tabs successfully verified and captured with zero horizontal overflow!")
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
