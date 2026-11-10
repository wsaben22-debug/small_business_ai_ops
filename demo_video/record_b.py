"""錄製 B：分鏡段 5–6（伺服器沒有 GEMINI_API_KEY）。

前提：錄製 A 已在同一份資料庫完成；伺服器以
    set DEMO_DISABLE_GEMINI=1
    python manage.py runserver --settings=demo_video.demo_settings
重新啟動。

用法（CMD，在專案根目錄）：
    python demo_video\\record_b.py
"""

import argparse
import sys
import traceback

from playwright.sync_api import sync_playwright

import common as c

VIDEO_NAME = "record_b.webm"
TIMELINE_PATH = c.DEMO_DIR / "timeline_b.txt"

REVIEW_REASON = (
    "AI 分析暫時無法使用。依資料包判斷：商品損壞且要求退款，"
    "金額 3,600 元，升級處理並聯繫客戶確認退款流程。"
)


# ---------------------------------------------------------------
# 預檢 + 登入（不錄影）。回傳登入狀態給錄影 context 使用，
# 影片就直接從 T002 審核頁開始。
# ---------------------------------------------------------------
def precheck_and_login(browser, cfg):
    problems = []
    warnings = []

    context = c.new_check_context(browser)
    page = context.new_page()

    try:
        c.login(page, cfg)

        t002_id = c.find_ticket_id(page, cfg, "DEMO-T002")
        t003_id = c.find_ticket_id(page, cfg, "DEMO-T003")

        if not c.queue_has_ticket(page, cfg, t002_id):
            problems.append(
                "DEMO-T002 不在待人工審核清單（錄製 A 沒有完成評估，或已經送出審核）"
            )

        if not c.queue_has_ticket(page, cfg, t003_id):
            warnings.append("DEMO-T003 不在待人工審核清單，段 6 無法框出 T003")

        page.goto(c.url_review(cfg, t002_id))

        if c.ai_button(page).count() == 0:
            problems.append("DEMO-T002 審核頁沒有 AI 按鈕（可能已完成人工審核）")

        if c.ai_card(page).locator("h3", has_text="客服回覆草稿").count() > 0:
            warnings.append("DEMO-T002 已有成功的 AI 結果，畫面會同時出現舊結果")

        state = context.storage_state()

    finally:
        context.close()

    return t002_id, t003_id, state, problems, warnings


# ---------------------------------------------------------------
# 段 5–6
# ---------------------------------------------------------------
def segment_5(page, cfg, tl, t002_id, issues):
    page.goto(c.url_review(cfg, t002_id))
    tl.mark("段5 AI 失敗後人工完成審核")

    identity = c.review_identity(page)
    if identity.count() == 0 or identity.first.inner_text().strip() != "DEMO-T002":
        raise RuntimeError("開啟的審核頁不是 DEMO-T002")

    c.hold(page, c.HOLD_T002_REVIEW_OPEN)

    tl.mark("段5 AI 等待開始")
    try:
        c.click_highlighted(page, c.ai_button(page), timeout=c.AI_TIMEOUT_MS)
    except c.PlaywrightTimeoutError:
        issues.append("AI 分析請求超時，畫面沒有出現失敗訊息")
    tl.mark("段5 AI 等待結束")

    if c.flash_note(page).filter(has_text="AI 輔助分析已完成").count() > 0:
        issues.append(
            "AI 分析竟然成功：伺服器可能仍有金鑰（確認啟動前有 set DEMO_DISABLE_GEMINI=1），需重錄 B"
        )

    flash = c.flash_error(page)
    card_error = c.ai_card(page).locator("p.review-error")
    half = c.HOLD_AI_FAILED / 2

    if flash.count() == 0:
        issues.append("沒有看到頁首的 AI 失敗訊息")
        c.screenshot(page, "shot4_ai_failed.png")
    else:
        print(f"畫面訊息：{flash.first.inner_text().strip()}")
        c.scroll_page_top(page)
        c.highlight(page, flash)
        c.hold(page, 1)
        c.screenshot(page, "shot4_ai_failed.png")
        c.hold(page, max(0, half - 1))
        c.clear_highlights(page)

    if card_error.count() > 0:
        c.scroll_to(card_error, ratio=0.35)
        c.highlight(page, card_error)
        c.hold(page, half)
        c.clear_highlights(page)

    # 人工審核表單
    human = c.review_section(page, "提交人工審核")
    select = page.locator("#selected_action")

    c.scroll_to(human)
    c.highlight(page, select, wait_ms=600)
    select.select_option(c.ACTION_ESCALATE)
    c.clear_highlights(page)
    c.hold(page, 1)

    c.type_into(page, page.locator("#reason"), REVIEW_REASON, delay=c.REASON_TYPE_DELAY_MS)
    c.hold(page, 1)

    c.click_highlighted(page, human.locator("button[type=submit]"))

    if "/triage-dashboard/" not in page.url:
        error = c.review_section(page, "提交人工審核").locator("p.review-error")
        detail = error.first.inner_text().strip() if error.count() else "未知原因"
        raise RuntimeError(f"人工審核送出失敗：{detail}")

    c.hold(page, c.HOLD_AFTER_SUBMIT)


def segment_6(page, cfg, tl, t002_id, t003_id, issues):
    tl.mark("段6 儀表板收尾")

    # 上方統計
    c.scroll_page_top(page)
    c.highlight(page, page.locator("section.operations-kpis"))
    c.hold(page, c.HOLD_FINAL_KPIS)
    c.clear_highlights(page)

    # 待審清單：T003 還在、T002 已不在
    queue = c.queue_section(page)

    if c.row_by_first_cell(queue, page, t002_id).count() > 0:
        issues.append("DEMO-T002 送出審核後仍在待審清單")

    t003_row = c.row_by_first_cell(queue, page, t003_id)
    c.scroll_to(queue)

    if t003_row.count() > 0:
        c.scroll_to(t003_row, ratio=0.4)
        c.highlight(page, t003_row)
    else:
        issues.append("待審清單找不到 DEMO-T003")
        c.highlight(page, queue.locator("h2"))

    c.hold(page, c.HOLD_FINAL_QUEUE)
    c.clear_highlights(page)

    # 最近執行紀錄
    history = c.history_section(page)
    c.scroll_to(history)
    c.highlight(page, history)
    c.hold(page, c.HOLD_FINAL_HISTORY)
    c.clear_highlights(page)


# ---------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="錄製 B：分鏡段 5–6")
    parser.add_argument("--headless", action="store_true", help="不顯示瀏覽器視窗")
    args = parser.parse_args()

    cfg = c.load_config()
    c.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    issues = []
    aborted = False

    with sync_playwright() as p:
        checker = p.chromium.launch(headless=True)
        try:
            t002_id, t003_id, state, problems, warnings = precheck_and_login(checker, cfg)
        finally:
            checker.close()

        for warning in warnings:
            print(f"警告：{warning}")

        if problems:
            for problem in problems:
                print(f"預檢失敗：{problem}")
            sys.exit("預檢未通過，沒有開始錄影。")

        browser = p.chromium.launch(headless=args.headless, slow_mo=c.SLOW_MO_MS)
        context = c.new_recording_context(browser, storage_state=state)
        page = context.new_page()

        timeline = c.Timeline(TIMELINE_PATH)
        timeline.start()

        try:
            segment_5(page, cfg, timeline, t002_id, issues)
            segment_6(page, cfg, timeline, t002_id, t003_id, issues)
            timeline.mark("錄製 B 結束")
            c.hold(page, c.HOLD_END)

        except Exception:
            aborted = True
            traceback.print_exc()
            timeline.mark("錄製 B 中斷")
            try:
                c.screenshot(page, "error_record_b.png")
            except Exception:
                pass

        finally:
            c.save_video(page, context, VIDEO_NAME)
            browser.close()

    print("\n===== 錄製 B 結果 =====")
    print(f"Timeline：{TIMELINE_PATH}")
    for issue in issues:
        print(f"注意：{issue}")

    if aborted:
        print("錄影中途出錯，需從第 1 步重新複製資料庫重錄（見上方錯誤訊息與 error_record_b.png）")
        sys.exit(1)

    if issues:
        sys.exit(1)


if __name__ == "__main__":
    main()
