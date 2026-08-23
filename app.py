import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image, ImageDraw
import random

# ============================================================
# V10 STEP 10C
# 4×2 原始總圖 → V8.3概念的手動定位裁切
#
# 重要：
# 1. AI生成時不再要求顯示 01～08 編號
# 2. 01～08 僅作為程式內部對應，不會出現在圖片上
# 3. 保留 STEP 10A/10B.1 的隨機用語池
# 4. 每格可獨立微調裁切範圍
# 5. 預覽使用彩色虛線
# 6. 輸出 01～08 PNG
# ============================================================

st.set_page_config(
    page_title="LINE 貼圖創作工作室",
    page_icon="🎨",
    layout="wide"
)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

COMMON_PHRASES = [
    "早安","晚安","午安","嗨","哈囉","加油","辛苦了","謝謝",
    "感謝","不客氣","沒問題","OK","收到","了解","好喔","好的",
    "太好了","讚","超讚","棒棒的","恭喜","祝福你","一起加油",
    "慢慢來","等等我","馬上來","我來了","出發","回來了","先這樣",
    "掰掰","再見","哈哈哈","笑死","真的嗎","真的假的","好開心",
    "好幸福","太可愛了","我愛你","想你","抱抱","親親","不要啦",
    "不要鬧","傻眼","無言","生氣","氣死我了","好累","累了",
    "忙死了","休息一下","我不行了","好餓","吃飯了嗎","等等再說",
    "拜託","求你了","可以嗎","好嗎","當然可以","當然好","隨便你",
    "沒事","沒關係","別擔心","放心","我懂","我知道","我明白",
    "太扯了","救命","完蛋了","糟糕","慘了","好可怕","不要怕","冷靜"
]

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

defaults = {
    "uploaded_image_bytes": None,
    "generated_4x2_bytes": None,
    "last_prompt": "",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

for i in range(8):
    key = f"sticker_text_{i}"
    if key not in st.session_state:
        st.session_state[key] = ""

# 每格裁切四邊偏移量
# 相對於 4×2 自動基準格：
# left / top / right / bottom
for i in range(8):
    for side in ("left", "top", "right", "bottom"):
        key = f"crop_{i}_{side}"
        if key not in st.session_state:
            st.session_state[key] = 0


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
        parts.append(f"使用者自定風格：{custom_style.strip()}。")

    if selected_character:
        parts.append(
            "人物與畫面特色：" + "、".join(selected_character) + "。"
        )

    if custom_character.strip():
        parts.append(
            f"使用者自定人物／場景要求：{custom_character.strip()}。"
        )

    parts.extend([
        "請一次生成一張 4×2 的八格 LINE 貼圖總圖。",
        "總圖必須是清楚的兩排四欄構圖。",
        "第一排為第1至第4格，第二排為第5至第8格。",
        "八格由左至右、由上至下依序對應使用者輸入的八個貼圖文字。",
        "每一格只對應一個指定文字，不得交換、遺漏或合併。",
        "八格人物維持同一人物身份與主要視覺風格。",
        "每格人物完整呈現，不要裁切頭部、臉部、身體或四肢。",
        "人物與該格邊界保持安全距離。",
        "不要讓人物因為畫面比例而被拉伸、變形或壓縮。",
        "非常重要：圖片中禁止出現 01、02、03、04、05、06、07、08 等編號。",
        "禁止加入任何格號、編號、序號、標籤、位置文字或數字標記。",
        "只有使用者指定的貼圖文字可以出現在圖片中。",
    ])

    for i, text in enumerate(sticker_texts):
        content = text.strip() or "（此格未指定文字）"
        parts.append(f"第{i + 1}格的指定貼圖文字為：「{content}」。")

    if transparent_bg:
        parts.append(
            "請使用透明背景 PNG。背景保持真正透明，"
            "不要用白色、黑色或其他純色填滿背景。"
        )

    parts.append("整體具有 LINE 貼圖的清楚、可讀、可愛與完整構圖感。")
    return "\n".join(parts)


def make_dashed_rectangle(draw, box, color, dash=12, width=4):
    """在 PIL 圖片上畫出彩色虛線矩形。"""
    x1, y1, x2, y2 = box

    def dashed_line(a, b):
        ax, ay = a
        bx, by = b
        dx = bx - ax
        dy = by - ay
        length = max(abs(dx), abs(dy))
        if length == 0:
            return
        steps = max(1, int(length / dash))
        for i in range(steps):
            if i % 2 == 0:
                t1 = i / steps
                t2 = min(1, (i + 1) / steps)
                p1 = (ax + dx * t1, ay + dy * t1)
                p2 = (ax + dx * t2, ay + dy * t2)
                draw.line([p1, p2], fill=color, width=width)

    dashed_line((x1, y1), (x2, y1))
    dashed_line((x2, y1), (x2, y2))
    dashed_line((x2, y2), (x1, y2))
    dashed_line((x1, y2), (x1, y1))


def calculate_boxes(width, height):
    """依 4×2 建立基準裁切格。"""
    boxes = []
    cell_w = width / 4
    cell_h = height / 2

    for i in range(8):
        row = i // 4
        col = i % 4

        x1 = int(round(col * cell_w))
        y1 = int(round(row * cell_h))
        x2 = int(round((col + 1) * cell_w))
        y2 = int(round((row + 1) * cell_h))

        boxes.append((x1, y1, x2, y2))

    return boxes


def get_adjusted_box(index, base_box, width, height):
    x1, y1, x2, y2 = base_box

    left = int(st.session_state[f"crop_{index}_left"])
    top = int(st.session_state[f"crop_{index}_top"])
    right = int(st.session_state[f"crop_{index}_right"])
    bottom = int(st.session_state[f"crop_{index}_bottom"])

    x1 += left
    y1 += top
    x2 -= right
    y2 -= bottom

    x1 = max(0, min(x1, width - 2))
    y1 = max(0, min(y1, height - 2))
    x2 = max(x1 + 2, min(x2, width))
    y2 = max(y1 + 2, min(y2, height))

    return x1, y1, x2, y2


def fit_to_line_canvas(crop):
    """
    將裁切內容等比例放入 LINE 常用 370×320 透明畫布。
    不拉伸人物。
    """
    canvas_w, canvas_h = 370, 320

    if crop.mode != "RGBA":
        crop = crop.convert("RGBA")

    scale = min(
        canvas_w / crop.width,
        canvas_h / crop.height
    )

    new_w = max(1, int(round(crop.width * scale)))
    new_h = max(1, int(round(crop.height * scale)))

    resized = crop.resize(
        (new_w, new_h),
        Image.Resampling.LANCZOS
    )

    canvas = Image.new(
        "RGBA",
        (canvas_w, canvas_h),
        (255, 255, 255, 0)
    )

    x = (canvas_w - new_w) // 2
    y = (canvas_h - new_h) // 2

    canvas.alpha_composite(resized, (x, y))
    return canvas


# ============================================================
# UI
# ============================================================

st.title("🎨 LINE 貼圖創作工作室")
st.caption("V10 STEP 10C｜4×2 → 手動定位裁切")
st.divider()

# ============================================================
# A. 人物
# ============================================================

st.header("📷 ① 上傳人物照片")

uploaded_file = st.file_uploader(
    "選擇人物照片",
    type=["jpg", "jpeg", "png", "webp"]
)

if uploaded_file is not None:
    try:
        uploaded_file.seek(0)
        input_image = Image.open(uploaded_file)
        input_image.load()

        buffer = BytesIO()
        input_image.convert("RGBA").save(buffer, format="PNG")
        st.session_state.uploaded_image_bytes = buffer.getvalue()

        st.image(
            input_image,
            caption="人物照片",
            width=420
        )
        st.success("✅ 人物照片已載入")

    except Exception as e:
        st.error("❌ 無法讀取人物照片")
        st.code(str(e))

# ============================================================
# B. 風格
# ============================================================

st.divider()
st.header("🎨 ② 貼圖風格")

style = st.selectbox("熱門風格", POPULAR_STYLES)

custom_style = st.text_area(
    "⭐ 我的自定風格",
    height=90
)

# ============================================================
# C. 人物特色
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
    height=110
)

# ============================================================
# D. 01～08
# ============================================================

st.divider()
st.header("💬 ④ 01～08 貼圖文字")

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("🎲 隨機填入 8 格", use_container_width=True):
        set_sticker_texts(
            random.sample(COMMON_PHRASES, 8)
        )
        st.rerun()

with c2:
    if st.button("🔄 清空 8 格", use_container_width=True):
        set_sticker_texts([""] * 8)
        st.rerun()

with c3:
    st.write(f"隨機用語池：{len(COMMON_PHRASES)} 句")

row1 = st.columns(4)
for i, col in enumerate(row1):
    with col:
        st.text_input(
            f"{i + 1:02d}",
            key=f"sticker_text_{i}"
        )

row2 = st.columns(4)
for i, col in enumerate(row2, start=4):
    with col:
        st.text_input(
            f"{i + 1:02d}",
            key=f"sticker_text_{i}"
        )

st.info(
    f"已填寫 {sum(bool(x.strip()) for x in get_sticker_texts())} / 8 格"
)

# ============================================================
# E. 生成
# ============================================================

st.divider()
st.header("✨ ⑤ 生成 4×2 原始總圖")

transparent_bg = st.checkbox(
    "使用透明背景 PNG",
    value=False
)

prompt = build_prompt(
    style,
    custom_style,
    selected_character,
    custom_character,
    get_sticker_texts(),
    transparent_bg
)

with st.expander("🔍 查看 AI Prompt"):
    st.code(prompt, language="text")

if st.button(
    "✨ 生成 4×2 八格總圖",
    type="primary",
    use_container_width=True
):
    if st.session_state.uploaded_image_bytes is None:
        st.warning("請先上傳人物照片。")
        st.stop()

    if not any(x.strip() for x in get_sticker_texts()):
        st.warning("請至少輸入一格貼圖文字。")
        st.stop()

    with st.spinner("AI 正在生成 4×2 原始總圖……"):
        try:
            image_buffer = BytesIO(
                st.session_state.uploaded_image_bytes
            )

            result = client.images.edit(
                model="gpt-image-2",
                image=("person.png", image_buffer, "image/png"),
                prompt=prompt,
                size="1536x1024"
            )

            raw = base64.b64decode(result.data[0].b64_json)

            # 強制轉成 PNG 保存，不改變圖片內容
            img = Image.open(BytesIO(raw))
            out = BytesIO()
            img.save(out, format="PNG")

            st.session_state.generated_4x2_bytes = out.getvalue()
            st.success("🎉 4×2 原始總圖生成成功！")

        except Exception as e:
            st.error("❌ 生成失敗")
            st.code(str(e))

# ============================================================
# F. STEP 10C 裁切
# ============================================================

if st.session_state.generated_4x2_bytes:

    st.divider()
    st.header("✂️ ⑥ STEP 10C｜手動定位裁切")

    source = Image.open(
        BytesIO(st.session_state.generated_4x2_bytes)
    ).convert("RGBA")

    width, height = source.size
    base_boxes = calculate_boxes(width, height)

    st.info(
        "目前以 4×2 自動格線作為基準。"
        "每格可以用左／上／右／下數值微調。"
        "預覽中的彩色虛線就是實際裁切範圍。"
    )

    # --------------------------------------------------------
    # 全圖裁切預覽
    # --------------------------------------------------------

    preview = source.copy()
    draw = ImageDraw.Draw(preview)

    line_colors = [
        (255, 70, 70, 255),
        (70, 130, 255, 255),
        (70, 190, 100, 255),
        (180, 90, 220, 255),
        (255, 150, 40, 255),
        (40, 180, 180, 255),
        (220, 80, 150, 255),
        (150, 110, 60, 255),
    ]

    adjusted_boxes = []

    for i, base_box in enumerate(base_boxes):
        box = get_adjusted_box(
            i,
            base_box,
            width,
            height
        )
        adjusted_boxes.append(box)

        make_dashed_rectangle(
            draw,
            box,
            line_colors[i],
            dash=14,
            width=4
        )

    st.image(
        preview,
        caption="✂️ 彩色虛線＝實際裁切區域",
        use_container_width=True
    )

    # --------------------------------------------------------
    # 個別調整
    # --------------------------------------------------------

    st.subheader("🛠️ 個別裁切位置微調")

    for i in range(8):

        with st.expander(
            f"貼圖 {i + 1:02d}｜{get_sticker_texts()[i] or '未輸入文字'}",
            expanded=(i == 0)
        ):
            st.caption(
                "數值單位：原始 4×2 圖片 pixel。"
                "正數代表向內縮。"
            )

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.number_input(
                    "← 左",
                    min_value=0,
                    max_value=500,
                    step=1,
                    key=f"crop_{i}_left"
                )

            with col2:
                st.number_input(
                    "↑ 上",
                    min_value=0,
                    max_value=500,
                    step=1,
                    key=f"crop_{i}_top"
                )

            with col3:
                st.number_input(
                    "→ 右",
                    min_value=0,
                    max_value=500,
                    step=1,
                    key=f"crop_{i}_right"
                )

            with col4:
                st.number_input(
                    "↓ 下",
                    min_value=0,
                    max_value=500,
                    step=1,
                    key=f"crop_{i}_bottom"
                )

            x1, y1, x2, y2 = get_adjusted_box(
                i,
                base_boxes[i],
                width,
                height
            )

            st.caption(
                f"目前裁切：X {x1}～{x2}｜Y {y1}～{y2}｜"
                f"{x2-x1} × {y2-y1} px"
            )

    # --------------------------------------------------------
    # 重新產生預覽
    # --------------------------------------------------------

    st.divider()

    if st.button(
        "🔄 更新彩色虛線預覽",
        use_container_width=True
    ):
        st.rerun()

    # --------------------------------------------------------
    # 裁切輸出
    # --------------------------------------------------------

    st.subheader("📦 輸出 01～08")

    if st.button(
        "✂️ 執行裁切並輸出 01～08 PNG",
        type="primary",
        use_container_width=True
    ):
        output_files = []

        for i in range(8):

            x1, y1, x2, y2 = get_adjusted_box(
                i,
                base_boxes[i],
                width,
                height
            )

            crop = source.crop(
                (x1, y1, x2, y2)
            )

            final_image = fit_to_line_canvas(crop)

            buffer = BytesIO()
            final_image.save(
                buffer,
                format="PNG"
            )

            output_files.append(
                (
                    f"{i + 1:02d}.png",
                    buffer.getvalue()
                )
            )

        st.session_state["cropped_files"] = output_files

        st.success(
            "🎉 裁切完成！已產生 01～08 共 8 張 PNG。"
        )

    # --------------------------------------------------------
    # 輸出結果
    # --------------------------------------------------------

    if st.session_state.get("cropped_files"):

        st.subheader("🖼️ 裁切結果")

        result_cols = st.columns(4)

        for i, (filename, data) in enumerate(
            st.session_state["cropped_files"]
        ):
            with result_cols[i % 4]:
                st.image(
                    data,
                    caption=filename,
                    use_container_width=True
                )

                st.download_button(
                    f"⬇️ {filename}",
                    data=data,
                    file_name=filename,
                    mime="image/png",
                    key=f"download_{i}"
                )

        st.info(
            "以上輸出為 370×320 PNG，並保留透明 Alpha。"
        )

st.divider()
st.caption(
    "V10 STEP 10C｜AI負責內容｜程式負責定位與裁切"
)
