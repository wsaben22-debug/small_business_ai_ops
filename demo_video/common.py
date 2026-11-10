"""record_a.py / record_b.py 共用的設定與工具。"""

import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# ---------------------------------------------------------------
# 停留秒數（依分鏡；要調整節奏改這裡就好）
# ---------------------------------------------------------------
# 旁白秒數見 output/voice/durations.txt；每段影片要比旁白長 1.5～2 秒以上。
# 段 1 開場（旁白 15.5 秒）
HOLD_LOGIN_PAGE = 1.5
HOLD_LIST = 8

# 段 2 T001（旁白 29.7 秒）
HOLD_T001_SEARCH = 4
HOLD_T001_EVALUATED = 5
HOLD_T001_EXECUTION = 8

# 段 3 T002（旁白 28.0 秒）
HOLD_T002_SEARCH = 3
HOLD_T002_SCORES = 6
HOLD_T002_REASON = 5
HOLD_T002_RECOMMEND = 5     # 段 3 停在「決策建議」後結束

# 段 4a T003，AI 按鈕前（旁白 25.5 秒）
HOLD_T003_QUEUE = 4
HOLD_T003_SCORES = 7
HOLD_T003_REASON = 6
# 段 4b AI 結果（旁白 12.8 秒）
HOLD_AI_SUMMARY = 7
HOLD_AI_RISK_NOTES = 7
HOLD_AI_REPLY_DRAFT = 7

# 段 5 AI 失敗（旁白 20.3 秒；估計影片約 28 秒，已足夠）
HOLD_T002_REVIEW_OPEN = 3
HOLD_AI_FAILED = 6
HOLD_AFTER_SUBMIT = 3

# 段 6 收尾（旁白 19.1 秒）
HOLD_FINAL_KPIS = 7
HOLD_FINAL_QUEUE = 7
HOLD_FINAL_HISTORY = 4

# 每支影片結尾多留一點，方便剪輯
HOLD_END = 1.5

# ---------------------------------------------------------------
# 畫面與速度
# ---------------------------------------------------------------
# 1536×864 的 CSS 視窗 × 1.25 倍像素 = 1920×1080 影片與截圖，
# 版面等同 1920 螢幕開 125% 縮放。
VIEWPORT = {"width": 1536, "height": 864}
DEVICE_SCALE_FACTOR = 1.25
VIDEO_SIZE = {"width": 1920, "height": 1080}

SLOW_MO_MS = 500
HIGHLIGHT_MS = 800          # 框起來後多久才點
TYPE_DELAY_MS = 70          # 一般輸入每個字的間隔
REASON_TYPE_DELAY_MS = 35   # 人工審核原因（字比較多）
SCROLL_MS = 900             # 一般捲動動畫
SLOW_SCROLL_MS = 1800       # 「慢慢往下捲」
SCROLL_TOP_RATIO = 0.18     # 目標元素捲到畫面上方 18% 處，避開下緣字幕區
# 段 4 T003 已有舊 AI 卡片時：AI 按鈕下緣對齊畫面高度 86% 處。
# 舊卡片緊接在按鈕下方（間距 14px），所以畫面最下方約 12% 仍會露出卡片頂端，
# 正好落在字幕區。改成 0.98 可完全藏住卡片，但按鈕會貼在畫面最下緣。
AI_BUTTON_BOTTOM_RATIO = 0.86
NAV_TIMEOUT_MS = 30_000
AI_TIMEOUT_MS = 90_000

HIGHLIGHT_COLOR = "#e53935"

DEMO_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = DEMO_DIR / "output"
RAW_VIDEO_DIR = OUTPUT_DIR / "_raw"

# 人工審核選項（值 → 畫面文字）
ACTION_ESCALATE = "escalate_high_priority_case"   # 升級高優先案件


# ---------------------------------------------------------------
# 環境變數
# ---------------------------------------------------------------
def _require_env(name):
    value = os.environ.get(name, "")
    if not value.strip():
        sys.exit(f"缺少環境變數 {name}，請先在 CMD 用 set {name}=... 設定。")
    return value


def load_config():
    base_url = _require_env("BASE_URL").strip().rstrip("/")
    host = urlparse(base_url).hostname or ""

    if host not in ("localhost", "127.0.0.1", "::1"):
        sys.exit(f"BASE_URL 必須是本機位址，目前是：{base_url}")

    return {
        "base_url": base_url,
        "username": _require_env("DEMO_USERNAME").strip(),
        "password": _require_env("DEMO_PASSWORD"),
    }


# ---------------------------------------------------------------
# 錄影 context
# ---------------------------------------------------------------
def new_recording_context(browser, storage_state=None):
    RAW_VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    context = browser.new_context(
        viewport=VIEWPORT,
        device_scale_factor=DEVICE_SCALE_FACTOR,
        record_video_dir=str(RAW_VIDEO_DIR),
        record_video_size=VIDEO_SIZE,
        storage_state=storage_state,
        locale="zh-TW",
        timezone_id="Asia/Taipei",
    )
    context.set_default_navigation_timeout(NAV_TIMEOUT_MS)
    context.set_default_timeout(NAV_TIMEOUT_MS)
    return context


def new_check_context(browser):
    """不錄影的 context，只用來預檢與登入。"""
    context = browser.new_context(viewport=VIEWPORT)
    context.set_default_timeout(NAV_TIMEOUT_MS)
    return context


def save_video(page, context, filename):
    """關閉 context 後把影片存成固定檔名。"""
    video = page.video
    context.close()

    if video is None:
        print("警告：沒有取得影片物件。")
        return None

    target = OUTPUT_DIR / filename
    video.save_as(str(target))
    video.delete()
    print(f"影片已存：{target}")
    return target


# ---------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------
class Timeline:
    def __init__(self, path):
        self.path = Path(path)
        self.t0 = None

    def start(self):
        self.t0 = time.monotonic()
        self.path.write_text(
            "# 影片經過秒數\t段落\n", encoding="utf-8"
        )

    def mark(self, name):
        elapsed = time.monotonic() - self.t0
        minutes, seconds = divmod(elapsed, 60)
        line = f"{int(minutes):02d}:{seconds:05.2f}\t({elapsed:7.2f}s)\t{name}"

        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

        print(f"[timeline] {line}")


# ---------------------------------------------------------------
# 停留、捲動、框選
# ---------------------------------------------------------------
def hold(page, seconds):
    page.wait_for_timeout(int(seconds * 1000))


_SCROLL_JS = """
(el, [ratio, duration, edge]) => new Promise(resolve => {
    const startY = window.scrollY;
    const rect = el.getBoundingClientRect();
    const maxY = document.documentElement.scrollHeight - window.innerHeight;
    const anchor = edge === 'bottom' ? rect.bottom : rect.top;
    const targetY = Math.max(0, Math.min(maxY,
        anchor + window.scrollY - window.innerHeight * ratio));
    if (duration <= 0 || Math.abs(targetY - startY) < 2) {
        window.scrollTo(0, targetY);
        resolve();
        return;
    }
    const t0 = performance.now();
    function step(now) {
        const p = Math.min(1, (now - t0) / duration);
        const e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
        window.scrollTo(0, startY + (targetY - startY) * e);
        if (p < 1) requestAnimationFrame(step); else resolve();
    }
    requestAnimationFrame(step);
})
"""


def scroll_to(locator, ratio=SCROLL_TOP_RATIO, duration=SCROLL_MS):
    """把元素「上緣」捲到畫面高度 ratio 的位置。"""
    locator.first.evaluate(_SCROLL_JS, [ratio, duration, "top"])


def scroll_bottom_to(locator, ratio, duration=SCROLL_MS):
    """把元素「下緣」捲到畫面高度 ratio 的位置（元素下方的內容盡量留在畫面外）。"""
    locator.first.evaluate(_SCROLL_JS, [ratio, duration, "bottom"])


def scroll_page_top(page, duration=SCROLL_MS):
    scroll_to(page.locator("body"), ratio=0, duration=duration)


_RECT_JS = """
el => {
    const r = el.getBoundingClientRect();
    return [r.left + window.scrollX, r.top + window.scrollY,
            r.right + window.scrollX, r.bottom + window.scrollY];
}
"""

_DRAW_JS = """
([x1, y1, x2, y2, color]) => {
    const pad = 6;
    const d = document.createElement('div');
    d.className = 'demo-highlight';
    Object.assign(d.style, {
        position: 'absolute',
        left: (x1 - pad) + 'px',
        top: (y1 - pad) + 'px',
        width: (x2 - x1 + pad * 2) + 'px',
        height: (y2 - y1 + pad * 2) + 'px',
        border: '4px solid ' + color,
        borderRadius: '10px',
        boxShadow: '0 0 0 6px rgba(229, 57, 53, 0.22)',
        boxSizing: 'border-box',
        pointerEvents: 'none',
        zIndex: '2147483647',
    });
    document.documentElement.appendChild(d);
}
"""


def highlight(page, *locators, wait_ms=0):
    """在元素外框畫紅框（多個元素就框住它們的聯集）。紅框不擋點擊。"""
    rects = [loc.first.evaluate(_RECT_JS) for loc in locators]
    x1 = min(r[0] for r in rects)
    y1 = min(r[1] for r in rects)
    x2 = max(r[2] for r in rects)
    y2 = max(r[3] for r in rects)
    page.evaluate(_DRAW_JS, [x1, y1, x2, y2, HIGHLIGHT_COLOR])

    if wait_ms:
        page.wait_for_timeout(wait_ms)


def clear_highlights(page):
    page.evaluate(
        "() => document.querySelectorAll('.demo-highlight').forEach(e => e.remove())"
    )


def click_highlighted(page, locator, navigate=True, timeout=NAV_TIMEOUT_MS, scroll=True):
    """捲到目標 → 框起來 → 停一下 → 點擊（預設等待換頁）。"""
    if scroll:
        scroll_to(locator)
    highlight(page, locator, wait_ms=HIGHLIGHT_MS)

    if navigate:
        with page.expect_navigation(timeout=timeout):
            locator.first.click()
        page.wait_for_load_state("load")
    else:
        locator.first.click()
        clear_highlights(page)


def type_into(page, locator, text, delay=TYPE_DELAY_MS):
    scroll_to(locator)
    highlight(page, locator, wait_ms=300)
    locator.first.click()
    locator.first.fill("")
    locator.first.press_sequentially(text, delay=delay)
    clear_highlights(page)


def screenshot(page, filename):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    page.screenshot(path=str(path))
    print(f"截圖已存：{path}")
    return path


# ---------------------------------------------------------------
# 網址與定位
# ---------------------------------------------------------------
def url_login(cfg):
    return f"{cfg['base_url']}/login/"


def url_list(cfg):
    return f"{cfg['base_url']}/tickets/"


def url_dashboard(cfg):
    return f"{cfg['base_url']}/triage-dashboard/"


def url_review(cfg, ticket_id):
    return f"{cfg['base_url']}/high-risk-review/{ticket_id}/"


def marker(demo_id):
    return f"[{demo_id}]"


def list_row(page, demo_id):
    return page.locator("table.ops-table tbody tr").filter(
        has=page.locator(
            "td.ticket-identifier strong",
            has_text=re.compile(rf"^\s*{re.escape(demo_id)}\s*$"),
        )
    )


def row_ticket_id(row):
    text = row.first.locator("span.ticket-reference").inner_text()
    match = re.search(r"#(\d+)", text)
    if not match:
        raise RuntimeError(f"無法從「{text}」解析 Ticket ID")
    return int(match.group(1))


def dashboard_section(page, title):
    return page.locator("section.table-section").filter(
        has=page.locator("h2", has_text=title)
    )


def queue_section(page):
    return dashboard_section(page, "待人工審核案件")


def history_section(page):
    return dashboard_section(page, "最近執行紀錄")


def row_by_first_cell(section, page, ticket_id):
    return section.locator("tbody tr").filter(
        has=page.locator(
            "td:first-child",
            has_text=re.compile(rf"^\s*#?{ticket_id}\s*$"),
        )
    )


def review_section(page, title):
    return page.locator("section.review-section").filter(
        has=page.locator("h2", has_text=title)
    )


def review_identity(page):
    return page.locator(".review-identity .ticket-identifier strong")


def ai_button(page):
    return page.locator("section.review-section--ai form button.action-button")


def ai_card(page):
    return page.locator(".ai-result-card")


def flash_error(page):
    return page.locator("section.review-messages p.review-error")


def flash_note(page):
    return page.locator("section.review-messages p.review-note")


def ai_card_block(page, heading):
    """AI 結果卡片內的某個小標與它下一個區塊。"""
    h3 = ai_card(page).locator("h3", has_text=heading)
    body = h3.locator("xpath=following-sibling::*[1]")
    return h3, body


# ---------------------------------------------------------------
# 登入與背景查詢
# ---------------------------------------------------------------
def login(page, cfg, visible=False, goto=True):
    if goto:
        page.goto(url_login(cfg))

    username = page.locator("#id_username")
    password = page.locator("#id_password")
    button = page.locator("button.login-button")

    if visible:
        type_into(page, username, cfg["username"])
        type_into(page, password, cfg["password"])
        click_highlighted(page, button, scroll=False)
    else:
        username.fill(cfg["username"])
        password.fill(cfg["password"])
        with page.expect_navigation():
            button.click()

    if "/login/" in page.url:
        raise SystemExit("登入失敗：請確認 DEMO_USERNAME / DEMO_PASSWORD。")


def search_list(page, query):
    """在列表頁搜尋欄輸入並送出（觀眾看得到輸入過程）。"""
    scroll_page_top(page)
    type_into(page, page.locator("#ticket-search"), query)
    click_highlighted(
        page,
        page.locator("form.search-form button[type=submit]"),
        scroll=False,
    )


def header_link(page, text):
    return page.locator("header a.secondary-button", has_text=text)


def find_ticket_id(page, cfg, demo_id):
    """背景請求列表頁取得 DB ID（不會出現在影片裡）。"""
    response = page.request.get(url_list(cfg), params={"q": marker(demo_id)})

    if "/login/" in response.url:
        raise RuntimeError("背景查詢時尚未登入")

    ids = re.findall(
        rf"<strong>\s*{re.escape(demo_id)}\s*</strong>\s*"
        r'<span class="ticket-reference">Ticket #(\d+)</span>',
        response.text(),
    )

    if len(ids) != 1:
        raise RuntimeError(f"{demo_id}：預期找到 1 筆，實際 {len(ids)} 筆")

    return int(ids[0])


def queue_has_ticket(page, cfg, ticket_id):
    page.goto(url_dashboard(cfg))
    return row_by_first_cell(queue_section(page), page, ticket_id).count() > 0

