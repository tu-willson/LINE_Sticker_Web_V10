import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image

# ============================================================
# V10.0 STEP 10B
# 01～08 文字 -> AI 4×2 單張大圖生成
# ============================================================

st.set_page_config(
    page_title="LINE 貼圖創作工作室",
    page_icon="🎨",
    layout="wide"
)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

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

for i in range(8):
    key = f"sticker_text_{i}"
    if key not in st.session_state:
        st.session_state[key] = ""

if "generated_4x2_bytes" not in st.session_state:
    st.session_state.generated_4x2_bytes = None

if "last_prompt" not in st.session_state:
    st.session_state.last_prompt = ""


def get_sticker_texts():
    return [
        st.session_state.get(f"sticker_text_{i}", "")
        for i in range(8)
    ]


def set_sticker_texts(values):
    values = list(values)[:8]
    values += [""] * (8 - len(values))
    for i, value in enumerate(values):
        st.session_state[f"sticker_text_{i}"] = str(value)


def build_prompt(style, custom_style, selected_character,
                 custom_character, sticker_texts, transparent_bg):

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

    # --------------------------------------------------------
    # 01～08 固定位置規則
    # --------------------------------------------------------

    parts.append(
        "請一次生成一張 4×2 的八格 LINE 貼圖總圖。"
    )

    parts.append(
        "必須嚴格按照以下固定位置排列，不得交換、重新排序或合併："
    )

    parts.append(
        "第一排由左至右：01、02、03、04。"
    )

    parts.append(
        "第二排由左至右：05、06、07、08。"
    )

    parts.append(
        "每一格只對應一個指定編號與一個指定文字。"
    )

    parts.append(
        "不要把不同格子的文字放到其他格子。"
    )

    parts.append(
        "不要遺漏任何一格。"
    )

    parts.append(
        "八格之間保持清楚、獨立的構圖區域。"
    )

    parts.append(
        "每格人物完整呈現，不要裁切頭部、臉部、身體或四肢。"
    )

    parts.append(
        "每格人物與該格邊界保持安全距離。"
    )

    parts.append(
        "不要讓人物因為格子比例而被拉伸、變形或壓縮。"
    )

    parts.append(
        "八格人物可以有不同動作、表情與姿勢，但必須維持同一人物身份與視覺風格。"
    )

    # --------------------------------------------------------
    # 明確列出 01～08
    # --------------------------------------------------------

    for i, text in enumerate(sticker_texts):
        label = f"{i + 1:02d}"
        content = text.strip() or "（此格未指定文字）"

        parts.append(
            f"位置 {label}：文字「{content}」。"
        )

    if transparent_bg:
        parts.append(
            "請使用透明背景 PNG。"
            "背景保持真正透明，不要使用白色、黑色或其他純色填滿背景。"
        )

    parts.append(
        "整體為 LINE 貼圖設計，畫面清楚、可讀、可愛。"
    )

    return "\n".join(parts)


# ============================================================
# UI
# ============================================================

st.title("🎨 LINE 貼圖創作工作室")
st.caption(
    "V10.0 Web Edition｜STEP 10B：01～08 → 4×2 AI生成"
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
# ② 風格
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
    placeholder="例如：Q版黏土3D、木雕玩具質感、手工微縮場景、霧面材質……",
    height=100
)

# ============================================================
# ③ 人物特色
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
    placeholder="例如：保留髮型、服裝與配件；人物四肢完整；每格保留安全邊界。",
    height=130
)

# ============================================================
# ④ 01～08
# ============================================================

st.divider()
st.header("💬 ④ 01～08 貼圖文字")

st.write(
    "這裡的 01～08 是固定位置。"
    "AI 生成時會明確要求第一排 01～04、第二排 05～08。"
)

row1 = st.columns(4)

for i, col in enumerate(row1):
    with col:
        st.text_input(
            f"{i + 1:02d}",
            key=f"sticker_text_{i}",
            placeholder="輸入貼圖用語"
        )

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
    1 for text in sticker_texts
    if text.strip()
)

st.info(f"📊 已填寫 {filled_count} / 8 格")

# ============================================================
# ⑤ 背景
# ============================================================

st.divider()
st.header("🌈 ⑤ 背景設定")

transparent_bg = st.checkbox(
    "使用透明背景 PNG",
    value=False
)

# ============================================================
# ⑥ Prompt 預覽
# ============================================================

final_prompt = build_prompt(
    style,
    custom_style,
    selected_character,
    custom_character,
    sticker_texts,
    transparent_bg
)

st.divider()
st.header("🔍 ⑥ AI生成規則預覽")

with st.expander(
    "👀 查看完整 AI Prompt",
    expanded=False
):
    st.code(final_prompt, language="text")

# ============================================================
# ⑦ 生成 4×2
# ============================================================

st.divider()
st.header("✨ ⑦ 生成 4×2 八格總圖")

generate = st.button(
    "✨ 一次生成 4×2 八格貼圖",
    type="primary",
    use_container_width=True
)

if generate:

    if st.session_state.uploaded_image_bytes is None:
        st.warning("📷 請先上傳人物照片。")
        st.stop()

    if filled_count == 0:
        st.warning("💬 請至少輸入一格貼圖文字。")
        st.stop()

    st.session_state.last_prompt = final_prompt

    with st.spinner(
        "🎨 AI 正在製作 4×2 八格貼圖總圖……"
    ):

        try:
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
                size="1536x1024"
            )

            image_base64 = result.data[0].b64_json
            image_bytes = base64.b64decode(image_base64)

            generated_image = Image.open(
                BytesIO(image_bytes)
            )

            output_buffer = BytesIO()

            generated_image.save(
                output_buffer,
                format="PNG"
            )

            st.session_state.generated_4x2_bytes = (
                output_buffer.getvalue()
            )

            st.success(
                "🎉 STEP 10B：4×2 八格總圖生成成功！"
            )

        except Exception as e:
            st.error(
                "❌ 4×2 八格生成失敗"
            )
            st.code(str(e))

# ============================================================
# ⑧ 結果
# ============================================================

if st.session_state.generated_4x2_bytes:

    st.divider()
    st.header("🖼️ ⑧ 4×2 八格總圖")

    result_image = Image.open(
        BytesIO(
            st.session_state.generated_4x2_bytes
        )
    )

    st.image(
        result_image,
        caption="🤖 AI 生成的 4×2 八格總圖",
        use_container_width=True
    )

    st.download_button(
        label="⬇️ 儲存 4×2 總圖 PNG",
        data=st.session_state.generated_4x2_bytes,
        file_name="sticker_4x2.png",
        mime="image/png",
        use_container_width=True
    )

    with st.expander(
        "🔍 查看本次實際送出的 Prompt"
    ):
        st.code(
            st.session_state.last_prompt,
            language="text"
        )

st.divider()
st.caption(
    "V10.0 Web Edition｜STEP 10B："
    "01～08 固定位置 → 一次生成 4×2 八格總圖"
)
