import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image

# ============================================================
# V10.0 STEP 9A
# 人物與畫面特色 + 貼圖風格 + Prompt 組合器
# 本版先不送出新的生成請求，只預覽最終 Prompt。
# ============================================================

st.set_page_config(
    page_title="LINE 貼圖創作工作室",
    page_icon="🎨",
    layout="wide"
)

client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"]
)

# -----------------------------
# Session State
# -----------------------------
if "uploaded_image_bytes" not in st.session_state:
    st.session_state.uploaded_image_bytes = None

if "generated_image_b64" not in st.session_state:
    st.session_state.generated_image_b64 = None

# -----------------------------
# 預設資料
# -----------------------------
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

# -----------------------------
# 標題
# -----------------------------
st.title("🎨 LINE 貼圖創作工作室")
st.caption("V10.0 Web Edition｜STEP 9A 風格與人物設定")
st.divider()

# ============================================================
# ① 上傳人物照片
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

        width, height = input_image.size

        col1, col2 = st.columns([2, 1])

        with col1:
            st.image(
                input_image,
                caption="📷 人物照片",
                use_container_width=True
            )

        with col2:
            st.success("✅ 人物照片已載入")
            st.write(f"寬度：{width} px")
            st.write(f"高度：{height} px")
            st.write(f"格式：{input_image.format or '未知'}")
            st.write(f"模式：{input_image.mode}")

    except Exception as e:
        st.error("❌ 無法讀取圖片")
        st.code(str(e))

# ============================================================
# ② 貼圖風格
# ============================================================
st.divider()
st.header("🎨 ② 貼圖風格")

style = st.selectbox(
    "熱門風格",
    POPULAR_STYLES,
    index=0,
    help="先選擇一種主要視覺方向。"
)

custom_style = st.text_area(
    "⭐ 我的自定風格",
    placeholder="例如：Q版黏土3D、手工微縮場景、霧面材質、溫暖療癒氛圍……",
    height=110,
    help="如果你有自己的固定風格，可直接輸入。"
)

# ============================================================
# ③ 人物與畫面特色
# ============================================================
st.divider()
st.header("👤 ③ 人物與畫面特色")

selected_character = st.multiselect(
    "可以複選你希望 AI 保留或套用的特色",
    CHARACTER_OPTIONS,
    default=[],
    help="全部預設未選取；只會套用你實際勾選的項目。"
)

custom_character = st.text_area(
    "📝 自定義人物／場景需求",
    placeholder=(
        "例如：人物要有收藏公仔般的立體感；"
        "臉部不要過度改變；保留原本髮型與服裝配件；"
        "人物四肢完整呈現，不要被畫面邊界切掉。"
    ),
    height=150
)

# ============================================================
# ④ 貼圖內容
# ============================================================
st.divider()
st.header("💬 ④ 貼圖內容")

sticker_text = st.text_area(
    "這張貼圖想表達什麼？",
    value="開心揮手",
    height=90,
    placeholder="例如：早安、加油、謝謝、生氣、好累……"
)

transparent_bg = st.checkbox(
    "🌈 使用透明背景 PNG",
    value=False,
    help="目前只加入 Prompt 設定；真正的透明輸出會在後續版本接回 V8.4 核心。"
)

# ============================================================
# ⑤ Prompt 組合器
# ============================================================
st.divider()
st.header("🔍 ⑤ AI 實際使用的設定")

def build_prompt():
    parts = []

    parts.append(
        "請以我提供的人物照片作為主要人物參考。"
    )

    parts.append(
        "保留人物的身份辨識特徵，並避免任意改變人物核心外觀。"
    )

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
            f"這張貼圖要表達的內容／情緒：{sticker_text.strip()}。"
        )

    parts.append(
        "人物完整呈現，不要裁切頭部、臉部、身體或四肢。"
    )

    parts.append(
        "構圖應保留足夠安全邊界，避免人物貼近畫面邊緣。"
    )

    if transparent_bg:
        parts.append(
            "請使用透明背景 PNG，人物本體完整保留，背景不要填滿純色。"
        )

    parts.append(
        "整體要具有 LINE 貼圖的清楚、可讀、可愛與完整構圖感。"
    )

    return "\n".join(parts)

final_prompt = build_prompt()

with st.expander("👀 查看完整 AI Prompt", expanded=True):
    st.code(final_prompt, language="text")

st.info(
    "💡 STEP 9A 目前先讓你確認「使用者選項 → AI Prompt」是否正確。"
    "本頁不會因為重新勾選設定而產生新的圖片。"
)

# ============================================================
# STEP 9A 測試按鈕
# ============================================================
if st.button(
    "🧪 測試 Prompt 組合",
    use_container_width=True
):
    st.success("✅ Prompt 已重新組合完成，請查看上方「完整 AI Prompt」。")

# ============================================================
# 開發進度
# ============================================================
st.divider()
st.caption(
    "V10.0 Web Edition｜STEP 9A 完成：風格、人物特色、"
    "自定需求與 Prompt 組合器"
)
