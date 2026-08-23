import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image

# ============================================================
# V10.0 STEP 9B
# 人物照片 + 完整風格設定 -> AI 真正生成
# ============================================================

st.set_page_config(
    page_title="LINE 貼圖創作工作室",
    page_icon="🎨",
    layout="wide"
)

client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"]
)

# ------------------------------------------------------------
# 預設資料
# ------------------------------------------------------------

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

# ------------------------------------------------------------
# Session State
# ------------------------------------------------------------

if "uploaded_image_bytes" not in st.session_state:
    st.session_state.uploaded_image_bytes = None

if "generated_image_bytes" not in st.session_state:
    st.session_state.generated_image_bytes = None

if "last_prompt" not in st.session_state:
    st.session_state.last_prompt = ""

# ------------------------------------------------------------
# Prompt 組合器
# ------------------------------------------------------------

def build_prompt(style, custom_style, selected_character,
                 custom_character, sticker_text, transparent_bg):

    parts = []

    parts.append(
        "請以我提供的人物照片作為主要人物參考。"
    )

    parts.append(
        "保留人物的身份辨識特徵，避免任意改變人物核心外觀。"
    )

    if style and style != "↓ 請選擇風格":
        parts.append(
            f"主要貼圖風格：{style}。"
        )

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
        "構圖應保留足夠安全邊界，人物不要貼近畫面邊緣。"
    )

    parts.append(
        "不要讓人物因為畫面比例而被拉伸、變形或壓縮。"
    )

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
st.caption("V10.0 Web Edition｜STEP 9B 人物＋完整設定生成")
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

        input_image.convert("RGBA").save(
            buffer,
            format="PNG"
        )

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
    value=False
)


# ============================================================
# ⑤ Prompt 預覽
# ============================================================

final_prompt = build_prompt(
    style,
    custom_style,
    selected_character,
    custom_character,
    sticker_text,
    transparent_bg
)

st.divider()
st.header("🔍 ⑤ AI 實際使用的設定")

with st.expander("👀 查看完整 AI Prompt", expanded=False):
    st.code(final_prompt, language="text")


# ============================================================
# ⑥ 真正生成
# ============================================================

st.divider()
st.header("✨ ⑥ 生成貼圖")

generate = st.button(
    "✨ 使用目前設定生成圖片",
    type="primary",
    use_container_width=True
)

if generate:

    if st.session_state.uploaded_image_bytes is None:
        st.warning("📷 請先上傳人物照片。")
        st.stop()

    if not final_prompt.strip():
        st.warning("✏️ 請確認貼圖設定。")
        st.stop()

    st.session_state.last_prompt = final_prompt

    with st.spinner(
        "🎨 AI 正在參考人物照片與你的完整設定……"
    ):

        try:

            # ------------------------------------------------
            # 使用已保存的 PNG bytes
            # 明確指定檔名與 MIME Type
            # ------------------------------------------------

            image_buffer = BytesIO(
                st.session_state.uploaded_image_bytes
            )

            result = client.images.edit(
                model="gpt-image-2",
                image=(
                    "person.png",
                    image_buffer,
                    "image/png"
                ),
                prompt=final_prompt,
                size="1024x1024"
            )

            image_base64 = result.data[0].b64_json

            image_bytes = base64.b64decode(
                image_base64
            )

            generated_image = Image.open(
                BytesIO(image_bytes)
            )

            output_buffer = BytesIO()

            generated_image.save(
                output_buffer,
                format="PNG"
            )

            st.session_state.generated_image_bytes = (
                output_buffer.getvalue()
            )

            st.success(
                "🎉 STEP 9B 生成成功！"
            )

        except Exception as e:

            st.error(
                "❌ 人物＋完整設定生成失敗"
            )

            st.code(str(e))


# ============================================================
# 顯示生成結果
# ============================================================

if st.session_state.generated_image_bytes:

    st.divider()
    st.header("🖼️ 生成結果")

    result_image = Image.open(
        BytesIO(
            st.session_state.generated_image_bytes
        )
    )

    st.image(
        result_image,
        caption="🤖 AI 生成結果",
        use_container_width=True
    )

    with st.expander(
        "🔍 查看本次實際送出的 Prompt"
    ):
        st.code(
            st.session_state.last_prompt,
            language="text"
        )


# ============================================================
# 開發進度
# ============================================================

st.divider()

st.caption(
    "V10.0 Web Edition｜STEP 9B：人物照片＋完整設定 → AI生成"
)
