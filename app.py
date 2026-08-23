import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image


# ============================================================
# 基本設定
# ============================================================

st.set_page_config(
    page_title="LINE 貼圖創作工作室",
    page_icon="🎨",
    layout="wide"
)


# ============================================================
# OpenAI
# ============================================================

client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"]
)


# ============================================================
# 標題
# ============================================================

st.title("🎨 LINE 貼圖創作工作室")

st.caption(
    "V10.0 Web Edition｜LINE 貼圖製作工作站"
)

st.divider()


# ============================================================
# STEP 7：上傳人物照片
# ============================================================

st.header("📷 ① 上傳人物照片")

st.write(
    "請上傳你希望 AI 參考的人物照片。"
)

uploaded_file = st.file_uploader(
    "選擇人物照片",
    type=["jpg", "jpeg", "png", "webp"],
    help="支援 JPG、JPEG、PNG、WEBP"
)


# ============================================================
# 圖片預覽
# ============================================================

if uploaded_file is not None:

    try:

        image = Image.open(uploaded_file)

        # 確保圖片已完整載入
        image.load()

        width, height = image.size

        st.success("✅ 人物照片已成功載入")

        col1, col2 = st.columns([2, 1])

        with col1:

            st.image(
                image,
                caption="📷 人物照片預覽",
                use_container_width=True
            )

        with col2:

            st.subheader("📐 圖片資訊")

            st.write(
                f"寬度：{width} px"
            )

            st.write(
                f"高度：{height} px"
            )

            st.write(
                f"格式：{image.format or '未知'}"
            )

            st.write(
                f"模式：{image.mode}"
            )

            st.divider()

            st.info(
                "💡 如果圖片方向或人物位置不理想，"
                "可以重新選擇另一張照片。"
            )

    except Exception as e:

        st.error(
            "❌ 無法讀取這張圖片"
        )

        st.code(
            str(e)
        )


# ============================================================
# STEP 7-2：貼圖描述
# ============================================================

st.divider()

st.header("✏️ ② 貼圖描述")

prompt = st.text_area(
    "告訴 AI 你希望人物呈現什麼樣的動作或情緒",
    value=(
        "Q版可愛人物，開心揮手，"
        "LINE貼圖風格，"
        "人物完整呈現，不裁切人物，"
        "透明背景"
    ),
    height=130
)


# ============================================================
# STEP 7-3：生成圖片
# ============================================================

generate = st.button(
    "✨ 生成圖片",
    type="primary",
    use_container_width=True
)


# ============================================================
# AI 圖片生成
# ============================================================

if generate:

    if uploaded_file is None:

        st.warning(
            "📷 請先上傳人物照片。"
        )

        st.stop()

    if not prompt.strip():

        st.warning(
            "✏️ 請先輸入貼圖描述。"
        )

        st.stop()

    with st.spinner(
        "🎨 AI 正在製作貼圖，請稍候……"
    ):

        try:

            # ------------------------------------------------
            # 目前 STEP 7 先確認：
            # 上傳圖片 → Python → AI
            # ------------------------------------------------

            image = Image.open(uploaded_file)

            # ------------------------------------------------
            # 暫時仍使用文字生成測試
            # ------------------------------------------------

            result = client.images.generate(
                model="gpt-image-2",
                prompt=prompt,
                size="1024x1024"
            )

            image_base64 = result.data[0].b64_json

            image_bytes = base64.b64decode(
                image_base64
            )

            generated_image = Image.open(
                BytesIO(image_bytes)
            )

            st.success(
                "🎉 AI 圖片生成成功！"
            )

            st.image(
                generated_image,
                caption="AI 生成結果",
                use_container_width=True
            )

        except Exception as e:

            st.error(
                "❌ 圖片生成失敗"
            )

            st.code(
                str(e)
            )


# ============================================================
# 目前開發進度
# ============================================================

st.divider()

st.caption(
    "V10.0 Web Edition｜目前：STEP 7 上傳人物照片"
)
