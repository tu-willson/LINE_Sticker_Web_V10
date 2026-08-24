import streamlit as st
from openai import OpenAI
try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_AVAILABLE = True
except ImportError:
    CANVAS_AVAILABLE = False
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
    st.header("✂️ ⑥ STEP 10C｜滑鼠直接調整裁切框")

    source = Image.open(
        BytesIO(st.session_state.generated_4x2_bytes)
    ).convert("RGBA")

    width, height = source.size
    base_boxes = calculate_boxes(width, height)

    st.info(
        "🖱️ 直接點選彩色虛線框後拖曳即可移動；"
        "拖曳四角控制點即可調整大小。"
        "不需要逐張開啟設定。"
    )

    if not CANVAS_AVAILABLE:
        st.error(
            "目前環境缺少互動裁切元件。請在 requirements.txt 加入："
            " streamlit-drawable-canvas"
        )
        st.stop()

    # --------------------------------------------------------
    # 互動裁切畫布
    # --------------------------------------------------------
    # 關鍵修正：
    # 舊版每次 Streamlit rerun 都重新建立 initial_drawing，
    # 所以滑鼠拖曳後畫面立刻被舊座標覆蓋，看起來就像「不能拖」。
    #
    # 本版把 Fabric.js 的目前 JSON 存進 session_state，
    # 下一次 rerun 直接沿用上一個畫面狀態。
    # --------------------------------------------------------

    canvas_w = 1000
    canvas_h = max(1, int(round(height * canvas_w / width)))

    line_colors = [
        "#ff4545", "#4387ff", "#35a85a", "#a34bd6",
        "#ff922e", "#20a6a6", "#d94b91", "#9a6b36",
    ]

    scale_x = canvas_w / width
    scale_y = canvas_h / height

    if "crop_canvas_version" not in st.session_state:
        st.session_state.crop_canvas_version = 0

    if "crop_canvas_drawing" not in st.session_state:
        initial_objects = []

        for i, (x1, y1, x2, y2) in enumerate(base_boxes):
            sx = x1 * scale_x
            sy = y1 * scale_y
            sw = max(10, (x2 - x1) * scale_x)
            sh = max(10, (y2 - y1) * scale_y)

            initial_objects.append({
                "type": "rect",
                "left": sx,
                "top": sy,
                "width": sw,
                "height": sh,
                "scaleX": 1,
                "scaleY": 1,
                "fill": "rgba(255,255,255,0.01)",
                "stroke": line_colors[i],
                "strokeWidth": 4,
                "strokeDashArray": [12, 8],
                "selectable": True,
                "evented": True,
                "hasControls": True,
                "hasBorders": True,
                "lockRotation": True,
                "lockUniScaling": False,
                "objectCaching": False,
                "transparentCorners": False,
                "cornerSize": 14,
                "padding": 2,
                "data_index": i,
            })

        st.session_state.crop_canvas_drawing = {
            "version": "4.4.0",
            "objects": initial_objects
        }

    st.caption(
        "🟥01　🟦02　🟩03　🟪04　🟧05　🩵06　🩷07　🟫08"
        "　｜點一下框線後直接拖曳"
    )

    canvas_key = f"step10c_direct_crop_canvas_{st.session_state.crop_canvas_version}"

    canvas_result = st_canvas(
        fill_color="rgba(0,0,0,0)",
        stroke_width=3,
        stroke_color="#ff4545",
        background_image=source,
        update_streamlit=True,
        height=canvas_h,
        width=canvas_w,
        drawing_mode="transform",
        initial_drawing=st.session_state.crop_canvas_drawing,
        display_toolbar=False,
        key=canvas_key,
    )

    # 只要 Fabric.js 回傳有效 JSON，就立刻保存。
    # 這是讓「拖曳 → Streamlit rerun → 位置仍然保留」的關鍵。
    if canvas_result.json_data:
        objects = canvas_result.json_data.get("objects", [])
        rects = [
            obj for obj in objects
            if obj.get("type") == "rect"
        ]
        if len(rects) >= 8:
            st.session_state.crop_canvas_drawing = canvas_result.json_data

    # --------------------------------------------------------
    # 套用 / 重設
    # --------------------------------------------------------

    col_a, col_b = st.columns([2, 2])

    with col_a:
        apply_crop = st.button(
            "✅ 套用目前裁切框",
            type="primary",
            use_container_width=True
        )

    with col_b:
        reset_crop = st.button(
            "↩️ 恢復 4×2 預設位置",
            use_container_width=True
        )

    if reset_crop:
        st.session_state.pop("crop_canvas_drawing", None)
        for i in range(8):
            st.session_state.pop(f"manual_box_{i}", None)
        st.session_state.crop_canvas_version += 1
        st.rerun()

    if apply_crop:
        drawing = st.session_state.get("crop_canvas_drawing", {})
        objects = drawing.get("objects", [])
        rects = [
            obj for obj in objects
            if obj.get("type") == "rect"
        ]

        if len(rects) < 8:
            st.warning(
                f"目前只讀到 {len(rects)} 個裁切框，"
                "請確認 8 個彩色框都還在畫面上。"
            )
        else:
            converted = []

            for obj in rects[:8]:
                left = float(obj.get("left", 0))
                top = float(obj.get("top", 0))
                obj_w = float(obj.get("width", 0))
                obj_h = float(obj.get("height", 0))
                sx = float(obj.get("scaleX", 1))
                sy = float(obj.get("scaleY", 1))

                box_w = max(4, obj_w * sx)
                box_h = max(4, obj_h * sy)

                x1 = int(round(left / scale_x))
                y1 = int(round(top / scale_y))
                x2 = int(round((left + box_w) / scale_x))
                y2 = int(round((top + box_h) / scale_y))

                x1 = max(0, min(x1, width - 2))
                y1 = max(0, min(y1, height - 2))
                x2 = max(x1 + 2, min(x2, width))
                y2 = max(y1 + 2, min(y2, height))

                converted.append((x1, y1, x2, y2))

            # 用中心點重新排序，避免拖曳後物件內部順序改變。
            converted.sort(
                key=lambda b: (
                    (b[1] + b[3]) / 2,
                    (b[0] + b[2]) / 2
                )
            )

            for i, box in enumerate(converted[:8]):
                st.session_state[f"manual_box_{i}"] = box

            st.success("🎉 8 個裁切框已套用！")

    # --------------------------------------------------------
    # 目前位置
    # --------------------------------------------------------

    current_boxes = []

    for i, base_box in enumerate(base_boxes):
        current_boxes.append(
            st.session_state.get(
                f"manual_box_{i}",
                base_box
            )
        )

    with st.expander("📐 查看目前 01～08 裁切座標", expanded=False):
        for i, box in enumerate(current_boxes):
            x1, y1, x2, y2 = box
            st.write(
                f"{i+1:02d}｜X {x1}～{x2}｜Y {y1}～{y2}｜"
                f"{x2-x1} × {y2-y1}px"
            )

    # --------------------------------------------------------
    # 執行裁切
    # --------------------------------------------------------

    st.subheader("📦 輸出 01～08")

    if st.button(
        "✂️ 執行裁切並輸出 01～08 PNG",
        type="primary",
        use_container_width=True
    ):
        output_files = []

        for i, (x1, y1, x2, y2) in enumerate(current_boxes):
            crop = source.crop((x1, y1, x2, y2))
            final_image = fit_to_line_canvas(crop)

            buffer = BytesIO()
            final_image.save(buffer, format="PNG")

            output_files.append(
                (f"{i + 1:02d}.png", buffer.getvalue())
            )

        st.session_state["cropped_files"] = output_files
        st.success("🎉 裁切完成！已產生 01～08 共 8 張 PNG。")

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
                # 固定 CSS 寬度；不使用 use_container_width。
                st.image(
                    data,
                    caption=filename,
                    width=260
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
