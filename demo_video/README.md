# Demo 影片自動錄製（Playwright）

依《分鏡.md》用兩支腳本錄兩段影片，剪輯時接起來：

| 腳本 | 分鏡段落 | 伺服器 | 輸出 |
|---|---|---|---|
| `record_a.py` | 段 1–4（開場、T001、T002、T003＋AI） | 有 `GEMINI_API_KEY` | `output\record_a.webm`、`timeline_a.txt`、shot1–3 |
| `record_b.py` | 段 5–6（AI 失敗＋人工審核、儀表板收尾） | 停用 Gemini | `output\record_b.webm`、`timeline_b.txt`、shot4 |

所有指令都在 **CMD**、專案根目錄 `C:\small_business_ai_ops` 執行。

---

## 1. 安裝（只需一次）

```bat
pip install playwright
playwright install chromium
```

`requirements.txt` 不會被修改；Playwright 只用在錄影。

---

## 2. 錄影前的資料庫準備（每次正式錄影都要重做）

評估只能按一次、已評估的案件也刪不掉，所以**每次重錄都要從乾淨備份重新複製**。腳本不會讀寫任何 `.sqlite3` 檔，以下步驟由你手動執行。

```bat
cd /d C:\small_business_ai_ops
copy /Y db_demo_backup_20261028.sqlite3 db_demo_recording.sqlite3
set DEMO_DB_PATH=C:\small_business_ai_ops\db_demo_recording.sqlite3
set ALLOW_DEMO_DATA_RESET=true
python manage.py prepare_live_demo --settings=demo_video.demo_settings
python manage.py prepare_live_demo --execute --settings=demo_video.demo_settings
```

- 第一個 `prepare_live_demo` 是 dry run，應該看到 6 筆 `READY`。
- 加 `--execute` 後應該看到 `Live Demo preparation completed: updated=6`。這代表 T001、T002 都還是 open、沒有 Decision。
- 請確認 `db_demo_backup_20261028.sqlite3` 就是你要的乾淨備份。

### 為什麼要 `--settings=demo_video.demo_settings`

`demo1/settings.py` 的資料庫路徑寫死為 `db.sqlite3`。`demo_video/demo_settings.py` 沿用原本所有設定，只做兩件事：

1. 資料庫改用 `DEMO_DB_PATH`。若沒設定、檔案不存在，或指向 `db.sqlite3`、`db_demo_backup_20261028.sqlite3`、`db_demo_rehearsal_20261028.sqlite3`，會直接報錯。
2. `DEMO_DISABLE_GEMINI=1` 時移除 `GEMINI_API_KEY`。

第 2 點是必要的：`.env` 裡有 `GEMINI_API_KEY`，而 `settings.py` 會用 `load_dotenv` 載入它。CMD 的 `set GEMINI_API_KEY=` 只會刪掉變數，dotenv 接著又從 `.env` 讀回來，錄製 B 的 AI 就會成功。

伺服器啟動時會在終端機印出 `[demo_settings] DB=... | Gemini=...`，請確認內容正確。

---

## 3. 錄製 A（段 1–4，有金鑰）

**終端機 1：伺服器**

```bat
cd /d C:\small_business_ai_ops
set DEMO_DB_PATH=C:\small_business_ai_ops\db_demo_recording.sqlite3
set DEMO_DISABLE_GEMINI=
python manage.py runserver --settings=demo_video.demo_settings
```

確認畫面顯示 `Gemini=依 .env 設定（錄製 A）`。

**終端機 2：錄影**

```bat
cd /d C:\small_business_ai_ops
set BASE_URL=http://127.0.0.1:8000
set DEMO_USERNAME=你的帳號
set "DEMO_PASSWORD=你的密碼"
python demo_video\record_a.py
```

- 密碼若含 `&`、`^`、`%` 等符號，請保留 `set "..."` 的雙引號寫法。
- `BASE_URL` 只接受 localhost / 127.0.0.1。

**試跑：** `python demo_video\record_a.py --skip-ai` 不會按 AI 分析、不會呼叫 Gemini。但段 2、段 3 仍會真的執行評估，**試跑完一定要回到第 2 步重新複製資料庫**。

**開錄前的預檢：** 腳本會先用不錄影的背景瀏覽器檢查 T001、T002 是否尚未評估，以及 T003 是否在待審清單。不符合就不會開始錄影。若 T003 已有舊的 AI 結果，會印出警告：按下前畫面就會有結果卡片，而且若是同一模型的舊紀錄，按下後會直接沿用、不會重新呼叫 Gemini。

**T003 有舊 AI 卡片時：** 審核頁上「執行 AI 輔助分析」按鈕在上，`.ai-result-card` 緊接在按鈕下方（間距 14px）。所以按下前腳本只把按鈕的下緣捲到畫面高度 86% 處（`common.py` 的 `AI_BUTTON_BOTTOM_RATIO`），舊卡片大部分留在畫面外，只會在最下方約 12% 露出卡片頂端，大致落在字幕區。版面上無法讓按鈕遠離下緣、同時完全看不到卡片：把值改成 `0.98` 可以完全藏住卡片，但按鈕會貼在畫面最下緣。

**AI 失敗時：** 若 AI 分析失敗或超過 90 秒，腳本會存 `output\ai_failed_record_a.png`，在終端機印出「本次錄影 AI 失敗，需重錄」，照樣跑完並存影片。

---

## 4. 錄製 B（段 5–6，停用 Gemini）

1. 在終端機 1 按 `Ctrl+C` 關掉伺服器。**資料庫不要換。**
2. 停用 Gemini 後重新啟動：

```bat
set DEMO_DISABLE_GEMINI=1
python manage.py runserver --settings=demo_video.demo_settings
```

確認畫面顯示 `Gemini=已停用（錄製 B）`。

3. 在終端機 2 執行（同一個視窗，環境變數還在）：

```bat
python demo_video\record_b.py
```

腳本會先在背景登入，所以影片直接從 T002 審核頁開始。若 AI 意外成功（代表伺服器仍有金鑰），終端機會提示需重錄 B。

---

## 5. 重錄條件

以下任一情況，都要**從第 2 步重新複製資料庫**，A、B 都重錄：

- 錄製 A 印出「本次錄影 AI 失敗，需重錄」
- 任一腳本印出「錄影中途出錯」或「預檢失敗」
- 錄製 B 結尾印出任何「注意：」

---

## 6. 輸出位置

| 檔案 | 位置 |
|---|---|
| 影片 | `demo_video\output\record_a.webm`、`record_b.webm`（Playwright 只輸出 .webm，每次執行會覆蓋） |
| 截圖（1920×1080） | `demo_video\output\shot1_auto_handle.png`、`shot2_review_package.png`、`shot3_ai_result.png`、`shot4_ai_failed.png` |
| 失敗截圖 | `demo_video\output\ai_failed_record_a.png`、`error_record_a.png`、`error_record_b.png` |
| Timeline | `demo_video\timeline_a.txt`、`demo_video\timeline_b.txt`（每次執行會覆蓋） |

要保留滿意的那次錄影，請先把 `output` 裡的檔案複製到別處，再跑下一次。

Timeline 每行的格式是 `分:秒  (秒數)  段落名稱`。段 4、段 5 另外標了「AI 等待開始／結束」，方便剪掉等待時間。

---

## 7. 調整節奏與畫面

- **停留秒數：** 全部集中在 `common.py` 最上面的 `HOLD_*` 常數。
- **速度：** `SLOW_MO_MS`（預設 500）、`TYPE_DELAY_MS`、`SLOW_SCROLL_MS`。
- **紅框：** 點擊前框起目標元素，框住後停 `HIGHLIGHT_MS` 才點擊。
- **字幕區：** 目標元素會捲到畫面上方 `SCROLL_TOP_RATIO`（18%）處，避開最下緣的字幕區。
- **縮放：** 用 CSS 視窗 1536×864 × `device_scale_factor=1.25` 達到約 125% 縮放，影片和截圖輸出 1920×1080。

### 版面跑掉或畫質不佳時

- **文字模糊：** 改用 `VIEWPORT = 1920×1080`、`DEVICE_SCALE_FACTOR = 1`，並在頁面載入後加 `document.body.style.zoom = '1.25'`。這是 Chrome 的頁面縮放，版面寬度相同。
- **畫質不夠：** Playwright 錄影的位元率偏低。可以讓腳本在一般模式（非 `--headless`）下跑，另外用 OBS 錄瀏覽器視窗。腳本照樣負責操作、計時和截圖。
- **段 3 分數與分流原因無法同框：** 調小 `show_scores_and_reason` 裡 `scroll_to(summary, ratio=0.02)` 的 ratio，或接受 shot2 只框分流原因。

---

## 8. 錄影時要知道的畫面差異（字幕參考）

- 列表沒有「請求動作」和「金額」欄位，「資訊詢問、金額 850」只能靠字幕說明。
- T001 的分數（4 分）沒有任何畫面會顯示。
- 儀表板的待審清單和最近執行紀錄只顯示數字 Ticket ID，不顯示 `DEMO-Txxx`。
- 畫面上的實際文字：
  - 分流原因：「退款請求需由人工審核」、「高優先案件需由人工審核」
  - 建議動作：「升級高優先案件」
  - AI 按鈕：「執行 AI 輔助分析」
  - AI 區塊：「案件摘要／處理注意事項／客服回覆草稿」
  - 沒有金鑰時的訊息：「AI 分析服務尚未就緒，請聯絡管理員；人工審核仍可繼續。」
