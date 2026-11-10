"""讀 narration.txt，用 edge-tts 產生每段旁白 mp3，並用「字幕:」文字另外產生 .srt。

安裝：pip install edge-tts
用法（CMD，在專案根目錄）：
    python demo_video\\make_voice.py            產生全部 7 段
    python demo_video\\make_voice.py 段2 段4a   只重做指定段落

注意：edge-tts 會把「語音:」文字送到 Microsoft 的線上語音服務。

輸出：demo_video\\output\\voice\\段名.mp3、段名.srt、durations.txt
字幕時間依「字幕:」各句的長度，按該段音檔秒數比例分配；
不使用 edge-tts 依語音文字產生的字幕。
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------
# 可調整的常數
# ---------------------------------------------------------------
VOICE = "zh-TW-HsiaoChenNeural"
RATE = "+0%"        # 語速，例如 "-10%"、"+5%"
VOLUME = "+0%"
PITCH = "+0Hz"

SEGMENTS = ["段1", "段2", "段3", "段4a", "段4b", "段5", "段6"]

SUBTITLE_MAX_CHARS = 18     # 每條字幕最多幾個字，超過就再切
SUBTITLE_GAP_MS = 80        # 字幕之間的空白
ASCII_WORD_WEIGHT = 2       # 英文/數字詞（T001、Gemini…）大約等於幾個中文字的唸讀時間

# edge-tts 預設輸出格式為 audio-24khz-48kbitrate-mono-mp3（固定位元率）
MP3_BITRATE_BPS = 48_000

DEMO_DIR = Path(__file__).resolve().parent
NARRATION_PATH = DEMO_DIR / "narration.txt"
VOICE_DIR = DEMO_DIR / "output" / "voice"
DURATIONS_PATH = VOICE_DIR / "durations.txt"


# ---------------------------------------------------------------
# 讀 narration.txt
# ---------------------------------------------------------------
def load_narration(path):
    """格式：
        [段1]
        字幕: ……
        語音: ……
    以 # 開頭的行是註解。
    """
    if not path.is_file():
        sys.exit(f"找不到 {path}")

    blocks = {}
    current = None

    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()

        if not line or line.startswith("#"):
            continue

        header = re.fullmatch(r"\[(.+?)\]", line)
        if header:
            current = header.group(1).strip()
            if current in blocks:
                sys.exit(f"narration.txt 第 {number} 行：段落 {current} 重複")
            blocks[current] = {}
            continue

        field = re.fullmatch(r"(字幕|語音)\s*[:：]\s*(.*)", line)
        if field and current is not None:
            key = "subtitle" if field.group(1) == "字幕" else "speech"
            blocks[current][key] = field.group(2).strip()
            continue

        sys.exit(f"narration.txt 第 {number} 行無法辨識：{raw}")

    problems = []
    for name in SEGMENTS:
        block = blocks.get(name)
        if block is None:
            problems.append(f"缺少段落 [{name}]")
            continue
        for key, label in (("subtitle", "字幕"), ("speech", "語音")):
            if not block.get(key):
                problems.append(f"[{name}] 缺少「{label}:」或內容是空的")

    extra = [name for name in blocks if name not in SEGMENTS]
    if extra:
        problems.append(f"未知的段落：{', '.join(extra)}")

    if problems:
        sys.exit("narration.txt 格式有誤：\n  " + "\n  ".join(problems))

    return blocks


# ---------------------------------------------------------------
# 產生語音
# ---------------------------------------------------------------
async def synthesize(text, mp3_path):
    import edge_tts

    communicate = edge_tts.Communicate(
        text, VOICE, rate=RATE, volume=VOLUME, pitch=PITCH
    )

    tmp_path = mp3_path.with_name(mp3_path.name + ".part")
    with tmp_path.open("wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])

    if tmp_path.stat().st_size == 0:
        tmp_path.unlink()
        raise RuntimeError("edge-tts 沒有回傳音訊")

    tmp_path.replace(mp3_path)


def mp3_seconds(path):
    """有安裝 mutagen 就用它讀長度；沒有就依固定位元率估算。"""
    try:
        from mutagen.mp3 import MP3
    except ImportError:
        return path.stat().st_size * 8 / MP3_BITRATE_BPS
    return MP3(str(path)).info.length


# ---------------------------------------------------------------
# 用「字幕:」文字產生 srt
# ---------------------------------------------------------------
SENTENCE_END = "。！？；!?;"
SOFT_BREAKS = "，、,：:"


def split_subtitle(text):
    # 先依句尾標點切（標點留在句尾）
    sentences = [
        s.strip()
        for s in re.split(rf"(?<=[{SENTENCE_END}])", text)
        if s.strip()
    ]
    chunks = []

    for sentence in sentences:
        while len(sentence) > SUBTITLE_MAX_CHARS:
            window = sentence[: SUBTITLE_MAX_CHARS + 1]
            # 優先在逗號、冒號處切；沒有就在空白處切，避免切斷英文詞
            cut = max(window.rfind(p) for p in SOFT_BREAKS)
            if cut > 0:
                cut += 1
            else:
                cut = window.rfind(" ")
                if cut <= 0:
                    cut = SUBTITLE_MAX_CHARS
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            chunks.append(sentence)

    return chunks


def _weight(chunk):
    ascii_words = re.findall(r"[A-Za-z0-9]+", chunk)
    rest = re.sub(r"[A-Za-z0-9]+", "", chunk)
    cjk = re.sub(r"[，、。！？；：「」『』（）,.!?;:()\s]", "", rest)
    return max(1, len(cjk) + ASCII_WORD_WEIGHT * len(ascii_words))


def _srt_time(ms):
    hours, ms = divmod(int(round(ms)), 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def write_srt(subtitle, seconds, srt_path):
    chunks = split_subtitle(subtitle)
    total_ms = seconds * 1000
    total_weight = sum(_weight(chunk) for chunk in chunks)

    lines = []
    start = 0.0
    for index, chunk in enumerate(chunks, 1):
        end = start + total_ms * _weight(chunk) / total_weight
        shown_end = end - SUBTITLE_GAP_MS if index < len(chunks) else end
        lines += [
            str(index),
            f"{_srt_time(start)} --> {_srt_time(max(start, shown_end))}",
            chunk,
            "",
        ]
        start = end

    srt_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="用 edge-tts 產生旁白音檔與字幕")
    parser.add_argument(
        "segments", nargs="*", help=f"只產生指定段落（{' '.join(SEGMENTS)}）"
    )
    args = parser.parse_args()

    unknown = [s for s in args.segments if s not in SEGMENTS]
    if unknown:
        sys.exit(f"未知的段落：{', '.join(unknown)}")

    blocks = load_narration(NARRATION_PATH)

    try:
        import edge_tts  # noqa: F401
    except ImportError:
        sys.exit("尚未安裝 edge-tts，請先執行：pip install edge-tts")

    targets = args.segments or SEGMENTS
    VOICE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"聲音：{VOICE}　語速：{RATE}")
    failed = []

    for name in targets:
        mp3_path = VOICE_DIR / f"{name}.mp3"
        try:
            asyncio.run(synthesize(blocks[name]["speech"], mp3_path))
        except Exception as exc:
            failed.append(name)
            print(f"{name}：產生失敗（{type(exc).__name__}: {exc}）")
            continue

        seconds = mp3_seconds(mp3_path)
        write_srt(blocks[name]["subtitle"], seconds, VOICE_DIR / f"{name}.srt")
        print(f"{name}：完成 {seconds:6.2f} 秒")

    # durations.txt 列出資料夾裡所有段落（含之前產生、這次沒重做的）
    rows = []
    total = 0.0
    for name in SEGMENTS:
        mp3_path = VOICE_DIR / f"{name}.mp3"
        if mp3_path.is_file():
            seconds = mp3_seconds(mp3_path)
            total += seconds
            rows.append(f"{name}\t{seconds:.2f}")
        else:
            rows.append(f"{name}\t（尚未產生）")
    rows.append(f"合計\t{total:.2f}")

    DURATIONS_PATH.write_text(
        "段落\t秒數\n" + "\n".join(rows) + "\n", encoding="utf-8"
    )

    print("\n===== 各段秒數 =====")
    print("\n".join(rows))
    print(f"\n已寫入：{DURATIONS_PATH}")

    if failed:
        sys.exit(f"以下段落失敗，請重跑：{' '.join(failed)}")


if __name__ == "__main__":
    main()
