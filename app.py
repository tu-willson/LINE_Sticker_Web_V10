import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image
import random

# ============================================================
# V10.0 STEP 10A 修正版
# 01～08 貼圖文字 + 隨機用語池
# 修正：隨機填入後，手動修改其中一格不會清掉其他 7 格
# ============================================================

st.set_page_config(
    page_title="LINE 貼圖創作工作室",
    page_icon="🎨",
    layout="wide"
)

client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"]
)

POPULAR_STYLES = [
    "↓ 請選擇風格",
    "Q版黏土3D",
    "Q版收藏公仔",
    "3D收藏公仔",
    "療癒系Cute Wstyle",
    "大頭小身",
    "LINE貼圖風",
    "柔和光影",
    "手作玩偶風",
    "可愛漫畫風",
    "立體卡通風",
]

CHARACTER_OPTIONS = [
    "五官比例保留",
    "服飾配件保留",
    "人物辨識度保留",
    "Q版收藏公仔",
    "療癒系 Cute Wstyle",
    "大頭小身",
    "LINE貼圖風",
    "柔和光影",
]

COMMON_PHRASES = [
    "早安", "晚安", "午安", "嗨", "哈囉",
    "加油", "辛苦了", "謝謝", "感謝", "不客氣",
    "沒問題", "OK", "收到", "了解", "好喔",
    "好的", "太好了", "讚", "超讚", "棒棒的",
    "恭喜", "祝福你", "一起加油", "慢慢來",
    "等等我", "馬上來", "我來了", "出發",
    "回來了", "先這樣", "掰掰", "再見",
    "哈哈哈", "笑死", "真的嗎", "真的假的",
    "好開心", "好幸福", "太可愛了",
    "我愛你", "想你", "抱抱", "親親",
    "不要啦", "不要鬧", "傻眼", "無言",
    "生氣", "氣死我了", "好累", "累了",
    "忙死了", "休息一下", "我不行了",
    "好餓", "吃飯了嗎", "等等再說",
    "拜託", "求你了", "可以嗎", "好嗎",
    "當然可以", "當然好", "隨便你",
    "沒事", "沒關係", "別擔心", "放心",
    "我懂", "我知道", "我明白",
    "真的假的啦", "太扯了", "傻眼貓咪",
    "救命", "完蛋了", "糟糕", "慘了",
    "好可怕", "不要怕", "冷靜",
]

# ------------------------------------------------------------
# Session State
# ------------------------------------------------------------

if "uploaded_image_bytes" not in st.session_state:
    st.session_state.uploaded_image_bytes = None

if "generated_image_bytes" not in st.session_state:
    st.session_state.generated_image_bytes = None

if "last_prompt" not in st.session_state:
    st.session_state.last_prompt = ""

# 01～08 的真正單一資料來源：
# widget key 本身就是每一格的儲存位置。
for i in range(8):
    key = f"sticker_text_{i}"
    if key not in st.session_state:
        st.session_state[key] = ""


def get_sticker_texts():
    """永遠從 8 個 widget state 取得目前文字。"""
    return [
        st.session_state.get(f"sticker_text_{i}", "")
        for i in range(8)
    ]


def set_sticker_texts(values):
    """一次更新 01～08，並同步更新 widget state。"""
    values = list(values)[:8]
    values += [""] * (8 - len(values))

    for i, value in enumerate(values):
        st.session_state[f"sticker_text_{i}"] = str(value)


def build_prompt(
    style,
    custom_style,
    selected_character,
    custom_character,
    sticker_text,
    transparent_bg
):
    parts = [
        "請以我提供的人物照片作為主要人物參考。",
        "保留人物的身份辨識特徵，避免任意改變人物核心外觀。",
    ]

    if style and style != "↓ 請選擇風格":
        parts.append(f"主要貼圖風格：{style}。")

    if custom_style.strip():
        parts.append(
            f"使用者自定風格：{custom_style.strip()}。"
        )

    if selected_character:
        parts.append(
            "人物與畫面特色："
            + "、".join(selected_character)
            + "。"
        )

    if custom_character.strip():
        parts.append(
            f"使用者自定人物／場景要求：{custom_character.strip()}。"
        )

    if sticker_text.strip():
        parts.append(
            f"01～08 貼圖文字：\n{sticker_text.strip()}"
        )

    parts.extend([
        "人物完整呈現，不要裁切頭部、臉部、身體或四肢。",
        "構圖應保留足夠安全邊界，人物不要貼近畫面邊緣。",
        "不要讓人物因為畫面比例而被拉伸、變形或壓縮。",
    ])

    if transparent_bg:
        parts.append(
            "請使用透明背景 PNG。"
            "背景保持真正透明，不要使用白色、黑色或其他純色填滿背景。"
            "人物本體完整保留。"
        )

    parts.append(
        "整體要具有 LINE 貼圖的清楚、可讀、可愛與完整構圖感。"
    )

    return "\n".join(parts)


# ============================================================
# UI
# ============================================================

st.title("🎨 LINE 貼圖創作工作室")
st.caption(
    "V10.0 Web Edition｜STEP 10A 修正版："
    "01～08 貼圖文字＋隨機用語池"
)
st.divider()


# ============================================================
# ① 人物照片
# ============================================================

st.header("📷 ① 上傳人物照片")

uploaded_file = st.file_uploader(
    "選擇人物照片",
    type=["jpg", "jpeg", "png", "webp"],
    help="支援 JPG、JPEG、PNG、WEBP"
)

if uploaded_file is not None:
    try:
        uploaded_file.seek(0)
        input_image = Image.open(uploaded_file)
        input_image.load()

        buffer = BytesIO()
        input_image.convert("RGBA").save(buffer, format="PNG")
        st.session_state.uploaded_image_bytes = buffer.getvalue()

        col1, col2 = st.columns([2, 1])

        with col1:
            st.image(
                input_image,
                caption="📷 人物照片",
                use_container_width=True
            )

        with col2:
            st.success("✅ 人物照片已載入")
            st.write(f"寬度：{input_image.width} px")
            st.write(f"高度：{input_image.height} px")
            st.write(f"格式：{input_image.format or '未知'}")
            st.write(f"模式：{input_image.mode}")

    except Exception as e:
        st.error("❌ 無法讀取人物照片")
        st.code(str(e))


# ============================================================
# ② 貼圖風格
# ============================================================

st.divider()
st.header("🎨 ② 貼圖風格")

style = st.selectbox(
    "熱門風格",
    POPULAR_STYLES,
    index=0
)

custom_style = st.text_area(
    "⭐ 我的自定風格",
    placeholder=(
        "例如：Q版黏土3D、木雕玩具質感、"
        "手工微縮場景、霧面材質、溫暖療癒氛圍……"
    ),
    height=110
)


# ============================================================
# ③ 人物與畫面特色
# ============================================================

st.divider()
st.header("👤 ③ 人物與畫面特色")

selected_character = st.multiselect(
    "可以複選",
    CHARACTER_OPTIONS,
    default=[]
)

custom_character = st.text_area(
    "📝 自定義人物／場景需求",
    placeholder=(
        "例如：保留原本髮型與服裝配件；"
        "人物四肢完整；人物與畫面邊緣保持安全距離。"
    ),
    height=150
)


# ============================================================
# ④ 01～08 貼圖文字
# ============================================================

st.divider()
st.header("💬 ④ 01～08 貼圖文字")

st.write(
    "每一格都是獨立儲存。隨機填入後，可以任意修改其中一格，"
    "其他 7 格會完整保留。"
)

pool_col1, pool_col2, pool_col3 = st.columns([1, 1, 1])

with pool_col1:
    if st.button(
        "🎲 隨機填入 8 格",
        use_container_width=True
    ):
        choices = random.sample(
            COMMON_PHRASES,
            k=min(8, len(COMMON_PHRASES))
        )
        set_sticker_texts(choices)
        st.rerun()

with pool_col2:
    if st.button(
        "🔄 清空 8 格",
        use_container_width=True
    ):
        set_sticker_texts([""] * 8)
        st.rerun()

with pool_col3:
    st.write(
        f"目前隨機用語池：{len(COMMON_PHRASES)} 句"
    )

st.subheader("📝 自行輸入用語區")

# ------------------------------------------------------------
# 01～04
# ------------------------------------------------------------

row1 = st.columns(4)

for i, col in enumerate(row1):
    with col:
        st.text_input(
            f"{i + 1:02d}",
            key=f"sticker_text_{i}",
            placeholder="輸入貼圖用語"
        )

# ------------------------------------------------------------
# 05～08
# ------------------------------------------------------------

row2 = st.columns(4)

for i, col in enumerate(row2, start=4):
    with col:
        st.text_input(
            f"{i + 1:02d}",
            key=f"sticker_text_{i}",
            placeholder="輸入貼圖用語"
        )

sticker_texts = get_sticker_texts()

filled_count = sum(
    1 for x in sticker_texts
    if x.strip()
)

st.info(f"📊 已填寫 {filled_count} / 8 格")


# ============================================================
# 隨機用語池參考
# ============================================================

with st.expander(
    "📚 查看目前隨機用語池",
    expanded=False
):
    st.write("、".join(COMMON_PHRASES))


# ============================================================
# ⑤ 透明背景
# ============================================================

st.divider()
st.header("🌈 ⑤ 背景設定")

transparent_bg = st.checkbox(
    "使用透明背景 PNG",
    value=False,
    help=(
        "STEP 10A 只負責設定文字；"
        "真正透明輸出將在後續接回 V8 系列核心。"
    )
)


# ============================================================
# ⑥ Prompt 預覽
# ============================================================

st.divider()
st.header("🔍 ⑥ 目前設定預覽")

st.subheader("01～08 貼圖文字")

preview_cols = st.columns(4)

for i, col in enumerate(preview_cols):
    with col:
        text = sticker_texts[i].strip()
        st.markdown(
            f"**{i + 1:02d}**　"
            + (text if text else "（未輸入）")
        )

preview_cols2 = st.columns(4)

for i, col in enumerate(preview_cols2, start=4):
    with col:
        text = sticker_texts[i].strip()
        st.markdown(
            f"**{i + 1:02d}**　"
            + (text if text else "（未輸入）")
        )

all_text = "\n".join(
    f"{i + 1:02d}. {text.strip()}"
    for i, text in enumerate(sticker_texts)
    if text.strip()
)

final_prompt = build_prompt(
    style,
    custom_style,
    selected_character,
    custom_character,
    all_text,
    transparent_bg
)

with st.expander(
    "👀 查看目前組合後的 AI Prompt",
    expanded=False
):
    st.code(final_prompt, language="text")


# ============================================================
# STEP 10A 測試
# ============================================================

st.divider()

if st.button(
    "🧪 更新文字設定",
    use_container_width=True
):
    st.success(
        f"✅ 已保存目前 01～08 文字設定，共 {filled_count} 格。"
    )

st.caption(
    "V10.0 Web Edition｜STEP 10A 修正版："
    "01～08 貼圖文字＋隨機用語池"
)
