import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image
import random

# ============================================================
# V10.0 STEP 10B.1
# 以 STEP 10A 修正版為核心
# 保留隨機用語池 + 01~08獨立狀態
# 新增：一次生成 4×2 原始總圖
# 不加入裁切核心、不修改裁切邏輯
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

# STEP 10A 原有隨機用語池，保留在 10B.1
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
# Session State：01~08各自獨立保存
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


def build_prompt(
    style,
    custom_style,
    selected_character,
    custom_character,
    sticker_texts,
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

    # --------------------------------------------------------
    # 4×2 版面規則
    # --------------------------------------------------------

    parts.extend([
        "請一次生成一張 4×2 的八格 LINE 貼圖總圖。",
        "總圖必須是清楚的兩排四欄構圖。",
        "第一排由左至右固定為 01、02、03、04。",
        "第二排由左至右固定為 05、06、07、08。",
        "不得交換、重新排序、合併或遺漏任何一格。",
        "每一格必須有獨立且清楚的構圖區域。",
        "八格人物維持同一人物身份與主要視覺風格。",
        "每格人物完整呈現，不要裁切頭部、臉部、身體或四肢。",
        "人物與該格邊界保持安全距離。",
        "不要讓人物因為畫面比例而被拉伸、變形或壓縮。",
    ])

    # --------------------------------------------------------
    # 明確綁定 01~08 文字
    # --------------------------------------------------------

    for i, text in enumerate(sticker_texts):
        label = f"{i + 1:02d}"
        content = text.strip() or "（此格未指定文字）"

        parts.append(
            f"位置 {label} 的指定文字為：「{content}」。"
        )

    if transparent_bg:
        parts.append(
            "請使用透明背景 PNG。"
            "背景保持真正透明，不要使用白色、黑色或其他純色填滿背景。"
            "人物本體完整保留。"
        )

    parts.append(
        "整體具有 LINE 貼圖的清楚、可讀、可愛與完整構圖感。"
    )

    return "\n".join(parts)


# ============================================================
# UI
# ============================================================

st.title("🎨 LINE 貼圖創作工作室")
st.caption(
    "V10.0 Web Edition｜STEP 10B.1："
    "保留10A隨機用語池＋4×2原始總圖生成"
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
# ④ 01～08貼圖文字 + 隨機用語池
# ============================================================

st.divider()
st.header("💬 ④ 01～08 貼圖文字")

st.write(
    "每一格獨立保存。先隨機填入8格後，"
    "可以再修改任意一格，其他7格會完整保留。"
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

with st.expander(
    "📚 查看目前隨機用語池",
    expanded=False
):
    st.write("、".join(COMMON_PHRASES))

# ============================================================
# ⑤ 背景設定
# ============================================================

st.divider()
st.header("🌈 ⑤ 背景設定")

transparent_bg = st.checkbox(
    "使用透明背景 PNG",
    value=False,
    help=(
        "目前先把透明背景要求送入AI；"
        "真正透明輸出與後續裁切核心仍會獨立處理。"
    )
)

# ============================================================
# ⑥ Prompt預覽
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
# ⑦ 4×2生成
# ============================================================

st.divider()
st.header("✨ ⑦ 一次生成 4×2 八格總圖")

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
        "🎨 AI 正在製作 4×2 八格原始總圖……"
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
                "🎉 4×2 八格原始總圖生成成功！"
            )

        except Exception as e:
            st.error("❌ 4×2 八格生成失敗")
            st.code(str(e))

# ============================================================
# ⑧ 原始總圖
# ============================================================

if st.session_state.generated_4x2_bytes:

    st.divider()
    st.header("🖼️ ⑧ 4×2 原始總圖")

    result_image = Image.open(
        BytesIO(
            st.session_state.generated_4x2_bytes
        )
    )

    st.image(
        result_image,
        caption="🤖 AI 生成的4×2原始總圖（尚未裁切）",
        use_container_width=True
    )

    st.download_button(
        label="⬇️ 儲存 4×2 原始總圖 PNG",
        data=st.session_state.generated_4x2_bytes,
        file_name="sticker_4x2_original.png",
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

# ============================================================
# 開發進度
# ============================================================

st.divider()
st.caption(
    "V10.0 Web Edition｜STEP 10B.1："
    "10A功能完整保留＋4×2原始總圖生成"
)
