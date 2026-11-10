"""錄製 A：分鏡段 1–4（伺服器有 GEMINI_API_KEY）。

用法（CMD，在專案根目錄）：
    python demo_video\\record_a.py            正式錄影
    python demo_video\\record_a.py --skip-ai  試跑：不按 AI 分析、不呼叫 Gemini

注意：段 2、段 3 會真的執行案件評估（寫入錄影專用資料庫），
試跑後也要重新複製資料庫才能正式錄。
"""

import argparse
import sys
import traceback
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

import common as c

VIDEO_NAME = "record_a.webm"
TIMELINE_PATH = c.DEMO_DIR / "timeline_a.txt"


# ---------------------------------------------------------------
# 開錄前的唯讀預檢（不錄影、不寫資料，只讀頁面）
# ---------------------------------------------------------------
def precheck(browser, cfg, skip_ai):
    problems = []
    warnings = []

    context = c.new_check_context(browser)
    page = context.new_page()

    try:
        c.login(page, cfg)

        for demo_id in ("DEMO-T001", "DEMO-T002"):
            page.goto(f"{c.url_list(cfg)}?{urlencode({'q': c.marker(demo_id)})}")
            row = c.list_row(page, demo_id)

            if row.count() != 1:
                problems.append(f"{demo_id}：列表找到 {row.count()} 筆，預期 1 筆")
            elif row.locator("button.triage-button").count() != 1:
                problems.append(f"{demo_id}：已經評估過（沒有「執行案件評估」按鈕）")
            elif row.locator(".status-badge.ticket-status-open").count() != 1:
                problems.append(f"{demo_id}：處理狀態不是「待處理」")

        t003_id = c.find_ticket_id(page, cfg, "DEMO-T003")

        if not c.queue_has_ticket(page, cfg, t003_id):
            problems.append("DEMO-T003：不在儀表板的待人工審核清單")

        page.goto(c.url_review(cfg, t003_id))

        if c.ai_button(page).count() == 0:
            problems.append("DEMO-T003：審核頁沒有 AI 按鈕（可能已完成人工審核）")

        t003_has_old_card = c.ai_card(page).count() > 0

        if t003_has_old_card:
            warnings.append(
                "DEMO-T003 審核頁在按下 AI 分析前就已有「最近一次 AI 分析」卡片，"
                "觀眾會分不出新舊結果。"
                + ("" if skip_ai else "若舊紀錄與目前模型相同，按下後會直接沿用、不會重新呼叫 Gemini。")
                + "錄影時按下前只捲到按鈕，讓舊卡片盡量留在畫面下方之外。"
            )

    finally:
        context.close()

    return t003_id, t003_has_old_card, problems, warnings


# ---------------------------------------------------------------
# 共用片段
# ---------------------------------------------------------------
def expect_identity(page, demo_id):
    identity = c.review_identity(page)
    if identity.count() == 0 or identity.first.inner_text().strip() != demo_id:
        raise RuntimeError(f"審核頁不是 {demo_id}（目前網址 {page.url}）")


def show_scores_and_reason(page, hold_scores, hold_reason, shot_name=None):
    summary = c.review_section(page, "案件摘要")
    priority = c.review_section(page, "優先等級")
    assessment = c.review_section(page, "案件評估")

    c.scroll_to(summary, ratio=0.02)

    # 三項分數 + 總分
    c.highlight(page, priority, assessment)
    c.hold(page, hold_scores)
    c.clear_highlights(page)

    # 分流原因
    reason = summary.locator("p.review-note")
    c.highlight(page, reason)
    if shot_name:
        c.hold(page, 1)
        c.screenshot(page, shot_name)
        c.hold(page, max(0, hold_reason - 1))
    else:
        c.hold(page, hold_reason)
    c.clear_highlights(page)


# ---------------------------------------------------------------
# 段 1–4
# ---------------------------------------------------------------
def segment_1(page, cfg, tl):
    page.goto(c.url_login(cfg))
    tl.mark("段1 開場")
    c.hold(page, c.HOLD_LOGIN_PAGE)

    c.login(page, cfg, visible=True, goto=False)
    page.locator("#ticket-search").wait_for()
    c.hold(page, c.HOLD_LIST)


def segment_2(page, cfg, tl, issues):
    tl.mark("段2 T001 低風險自動處理")

    c.search_list(page, c.marker("DEMO-T001"))
    row = c.list_row(page, "DEMO-T001")
    if row.count() != 1:
        raise RuntimeError("搜尋不到 DEMO-T001")

    t001_id = c.row_ticket_id(row)
    c.highlight(page, row)
    c.hold(page, c.HOLD_T001_SEARCH)
    c.clear_highlights(page)

    c.click_highlighted(page, row.locator("button.triage-button"))

    if "/high-risk-review/" in page.url:
        raise RuntimeError("DEMO-T001 被分到人工審核，與預期的自動處理不符，需重錄")

    # 評估後導回未帶搜尋條件的列表，再搜一次
    c.search_list(page, c.marker("DEMO-T001"))
    row = c.list_row(page, "DEMO-T001")
    badge = row.locator(".table-actions .status-badge.triage-complete")
    if badge.count() == 0:
        raise RuntimeError("DEMO-T001 評估後沒有顯示「已評估」")

    c.highlight(page, row)
    c.hold(page, c.HOLD_T001_EVALUATED)
    c.clear_highlights(page)

    # 儀表板最近執行紀錄
    c.click_highlighted(page, c.header_link(page, "決策儀表板"))
    history_row = c.row_by_first_cell(c.history_section(page), page, t001_id).first

    if history_row.count() == 0:
        raise RuntimeError("最近執行紀錄找不到 DEMO-T001")

    if "處理中" not in history_row.inner_text():
        issues.append("DEMO-T001 的執行紀錄處理後狀態不是「處理中」")

    c.scroll_to(history_row, ratio=0.35)
    c.highlight(page, history_row)
    c.hold(page, 1)
    c.screenshot(page, "shot1_auto_handle.png")
    c.hold(page, max(0, c.HOLD_T001_EXECUTION - 1))
    c.clear_highlights(page)


def segment_3(page, cfg, tl):
    tl.mark("段3 T002 高風險人工審核")

    c.click_highlighted(page, c.header_link(page, "客服案件列表"))
    c.search_list(page, c.marker("DEMO-T002"))
    row = c.list_row(page, "DEMO-T002")
    if row.count() != 1:
        raise RuntimeError("搜尋不到 DEMO-T002")

    c.highlight(page, row)
    c.hold(page, c.HOLD_T002_SEARCH)
    c.clear_highlights(page)

    c.click_highlighted(page, row.locator("button.triage-button"))

    if "/high-risk-review/" not in page.url:
        raise RuntimeError("DEMO-T002 評估後沒有導向人工審核頁，與預期不符，需重錄")

    expect_identity(page, "DEMO-T002")
    show_scores_and_reason(
        page,
        c.HOLD_T002_SCORES,
        c.HOLD_T002_REASON,
        shot_name="shot2_review_package.png",
    )

    # 慢慢往下捲到「決策建議」，停留後段 3 結束（不按 AI、不送出）
    decision = c.review_section(page, "決策建議")
    recommended = decision.locator(".detail-card p").first
    c.scroll_to(decision, duration=c.SLOW_SCROLL_MS)
    c.highlight(page, recommended)
    c.hold(page, c.HOLD_T002_RECOMMEND)
    c.clear_highlights(page)


def bring_ai_button_into_view(page, button, hide_card_below):
    """有舊卡片時，只把按鈕下緣捲到畫面下方，卡片（在按鈕正下方）盡量不入鏡。"""
    if hide_card_below:
        c.scroll_bottom_to(button, ratio=c.AI_BUTTON_BOTTOM_RATIO)
    else:
        c.scroll_to(button)


def segment_4(page, cfg, tl, t003_id, has_old_card, skip_ai, issues):
    """回傳 True 代表 AI 分析失敗。"""
    tl.mark("段4 T003 與 Gemini AI 分析")

    c.click_highlighted(page, c.header_link(page, "返回決策儀表板"))

    queue = c.queue_section(page)
    queue_row = c.row_by_first_cell(queue, page, t003_id)
    if queue_row.count() == 0:
        raise RuntimeError("待審清單找不到 DEMO-T003")

    c.scroll_to(queue)
    c.hold(page, 1)
    c.scroll_to(queue_row, ratio=0.4)
    c.highlight(page, queue_row)
    c.hold(page, c.HOLD_T003_QUEUE)
    c.click_highlighted(page, queue_row.locator("a.action-button"), scroll=False)

    expect_identity(page, "DEMO-T003")
    show_scores_and_reason(page, c.HOLD_T003_SCORES, c.HOLD_T003_REASON)

    button = c.ai_button(page)
    if button.count() == 0:
        raise RuntimeError("DEMO-T003 審核頁沒有 AI 按鈕")

    card = c.ai_card(page)
    before_text = card.first.inner_text().strip() if card.count() else None
    if before_text:
        issues.append("DEMO-T003 按下 AI 分析前已有舊的 AI 結果卡片")

    hide_card_below = has_old_card or bool(before_text)
    bring_ai_button_into_view(page, button, hide_card_below)

    if skip_ai:
        c.highlight(page, button)
        c.hold(page, 2)
        c.clear_highlights(page)
        print("--skip-ai：已框起 AI 按鈕，未點擊、未呼叫 Gemini。")
        return False

    tl.mark("段4 AI 等待開始（剪輯時剪掉）")
    timed_out = False
    try:
        # 已在 bring_ai_button_into_view 捲好位置，這裡不再捲動
        c.click_highlighted(page, button, timeout=c.AI_TIMEOUT_MS, scroll=False)
    except c.PlaywrightTimeoutError:
        timed_out = True
    tl.mark("段4 AI 等待結束")

    succeeded = (
        not timed_out
        and c.flash_note(page).filter(has_text="AI 輔助分析已完成").count() > 0
        and c.ai_card(page).locator("h3", has_text="客服回覆草稿").count() > 0
    )

    if not succeeded:
        c.screenshot(page, "ai_failed_record_a.png")
        if timed_out:
            print(f"AI 分析超過 {c.AI_TIMEOUT_MS // 1000} 秒沒有回應。")
        elif c.flash_error(page).count():
            print(f"畫面訊息：{c.flash_error(page).first.inner_text().strip()}")
        print("本次錄影 AI 失敗，需重錄")
        return True

    after_text = c.ai_card(page).first.inner_text().strip()
    if before_text and after_text == before_text:
        issues.append(
            "AI 結果與按下前完全相同，可能沿用了舊紀錄、沒有重新呼叫 Gemini"
        )

    steps = [
        ("案件摘要", c.HOLD_AI_SUMMARY),
        ("處理注意事項", c.HOLD_AI_RISK_NOTES),
        ("客服回覆草稿", c.HOLD_AI_REPLY_DRAFT),
    ]

    for index, (heading, seconds) in enumerate(steps):
        h3, body = c.ai_card_block(page, heading)
        c.scroll_to(h3)
        c.highlight(page, h3, body)

        if index == 0:
            c.hold(page, 1)
            c.screenshot(page, "shot3_ai_result.png")
            c.hold(page, max(0, seconds - 1))
        else:
            c.hold(page, seconds)

        c.clear_highlights(page)

    return False


# ---------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="錄製 A：分鏡段 1–4")
    parser.add_argument("--skip-ai", action="store_true", help="試跑：不按 AI 分析、不呼叫 Gemini")
    parser.add_argument("--headless", action="store_true", help="不顯示瀏覽器視窗")
    args = parser.parse_args()

    cfg = c.load_config()
    c.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    issues = []
    ai_failed = False
    aborted = False

    with sync_playwright() as p:
        checker = p.chromium.launch(headless=True)
        try:
            t003_id, t003_has_old_card, problems, warnings = precheck(
                checker, cfg, args.skip_ai
            )
        finally:
            checker.close()

        for warning in warnings:
            print(f"警告：{warning}")

        if problems:
            for problem in problems:
                print(f"預檢失敗：{problem}")
            sys.exit(
                "預檢未通過，沒有開始錄影。"
                "請重新複製資料庫並執行 prepare_live_demo。"
            )

        browser = p.chromium.launch(headless=args.headless, slow_mo=c.SLOW_MO_MS)
        context = c.new_recording_context(browser)
        page = context.new_page()

        timeline = c.Timeline(TIMELINE_PATH)
        timeline.start()

        try:
            segment_1(page, cfg, timeline)
            segment_2(page, cfg, timeline, issues)
            segment_3(page, cfg, timeline)
            ai_failed = segment_4(
                page, cfg, timeline, t003_id, t003_has_old_card, args.skip_ai, issues
            )
            timeline.mark("錄製 A 結束")
            c.hold(page, c.HOLD_END)

        except Exception:
            aborted = True
            traceback.print_exc()
            timeline.mark("錄製 A 中斷")
            try:
                c.screenshot(page, "error_record_a.png")
            except Exception:
                pass

        finally:
            c.save_video(page, context, VIDEO_NAME)
            browser.close()

    print("\n===== 錄製 A 結果 =====")
    print(f"Timeline：{TIMELINE_PATH}")
    for issue in issues:
        print(f"注意：{issue}")

    if args.skip_ai:
        print("這次是 --skip-ai 試跑。正式錄影前請重新複製資料庫。")
    if ai_failed:
        print("本次錄影 AI 失敗，需重錄")
    if aborted:
        print("錄影中途出錯，需重錄（見上方錯誤訊息與 error_record_a.png）")

    if ai_failed or aborted:
        sys.exit(1)


if __name__ == "__main__":
    main()
