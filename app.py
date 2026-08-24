import zipfile
import streamlit as st
from openai import OpenAI
import base64
from io import BytesIO
from PIL import Image
import random
from pathlib import Path
import json

V10_PRESET_FILE = Path(__file__).with_name("V10_user_presets.json")

def _load_v10_presets():
    d={"style_custom":[""]*10,
       "style_custom_names":[f"使用者自定{i}" for i in range(1,11)],
       "character_custom":["","",""],
       "character_enabled":[False,False,False]}
    try:
        if V10_PRESET_FILE.exists():
            x=json.loads(V10_PRESET_FILE.read_text(encoding="utf-8"))
            d.update(x)
    except Exception:
        pass
    return d

def _save_v10_presets():
    d={
        "style_custom":[st.session_state.get(f"v10_style_custom_{i}","") for i in range(1,11)],
        "style_custom_names":[st.session_state.get(f"v10_style_name_{i}",f"使用者自定{i}") for i in range(1,11)],
        "character_custom":[st.session_state.get(f"v10_character_custom_{i}","") for i in range(1,4)],
        "character_enabled":[bool(st.session_state.get(f"v10_character_enabled_{i}",False)) for i in range(1,4)],
    }
    try:
        tmp=V10_PRESET_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
        tmp.replace(V10_PRESET_FILE)
        return True
    except Exception:
        return False

_pd=_load_v10_presets()
for _i in range(1,11):
    st.session_state.setdefault(f"v10_style_custom_{_i}", (_pd.get("style_custom") or [""]*10)[_i-1])
    st.session_state.setdefault(f"v10_style_name_{_i}", (_pd.get("style_custom_names") or [f"使用者自定{i}" for i in range(1,11)])[_i-1])
for _i in range(1,4):
    st.session_state.setdefault(f"v10_character_custom_{_i}", (_pd.get("character_custom") or ["","",""])[_i-1])
    st.session_state.setdefault(f"v10_character_enabled_{_i}", (_pd.get("character_enabled") or [False,False,False])[_i-1])
import streamlit.components.v1 as components

# ============================================================
# V10 STEP 10C
# 原生 HTML Canvas 滑鼠裁切版
#
# 核心：
# - 不使用 streamlit-drawable-canvas
# - 8 個裁切框同時顯示
# - 滑鼠拖曳框中央：移動
# - 拖曳四角：縮放
# - 拖曳四邊：單方向縮放
# - 顯示座標與原圖座標分離
# - 固定預覽上限，不跟 Streamlit 容器無限放大
# - Chrome 80/100/125/150% 仍以原始圖片座標計算
# - 01～08 不會送給 AI 當作圖片編號
# ============================================================

st.set_page_config(
    page_title="LINE 貼圖創作工作室",
    page_icon="🎨",
    layout="wide",
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

# ============================================================
# V8.6.4 資料模組移植：語詞／風格／貼圖字型／125 帶圖字型
# 資料內容沿用 V8，不改名稱與排列順序。
# ============================================================
V8_STYLES = ['Q版黏土3D', 'Q版收藏公仔', '3D收藏公仔', '軟陶公仔', '木雕玩具', '微縮場景', '療癒系Cute風', '日系可愛插畫', '韓系簡約插畫', '手繪水彩', '色鉛筆手繪', '粉彩蠟筆', '扁平插畫', '貼紙插畫風', '復古漫畫', '美式漫畫', '日系漫畫', '像素藝術', '毛氈玩偶', '羊毛氈手作', '紙雕立體', '紙黏土手作', '奶油霧面3D', '玻璃質感3D', '玩具盒收藏風', '盲盒公仔風', '電影級3D', '黏土定格動畫風', '低多邊形Low Poly', 'Dreamy夢幻療癒', '童話繪本風', '森林療癒風', '極簡精品風', '復古80年代', '復古90年代', '街頭潮流插畫', 'Emoji表情貼風', 'LINE訊息貼圖風', '透明背景貼圖風', '⭐ 自訂1', '⭐ 自訂2', '⭐ 自訂3', '⭐ 自訂4', '⭐ 自訂5']
V8_DEFAULT_CONTENT = ['早安', '晚安', '謝謝', '收到', 'OK', '加油', '辛苦了', '太棒了']
V8_RANDOM_POOLS = {'日常對話': ['你好', '哈囉', 'Hello', 'Hi', '安安', '嗨嗨', '請多多指教', '是我', '我來了', '來打聲招呼', '很高興認識你', '好久不見', '我來了', '想我了嗎', '在忙嗎？', '掰掰', 'Bye', '再聊', '再會', '再見', '晚點聊'], '生活應用': ['OK', '好的', '沒問題', '嗯嗯', '可以呀', '我可以', '收到', '了解', '知道了', '加油', '你可以的', '我相信你', '別緊張', '給你加加油', '生日快樂'], '時間問候': ['早安', '早呀', '早上好', '咕摸寧', '午安', '下午好', '晚安', '咕奈', '好好睡', '一覺好眠'], '溫暖關愛': ['愛你', '給你愛心', '給你一個小心心', '抱', '別哭', '抱一個', '給你大大的擁抱', '別擔心', '別想太多'], '歡樂笑聲': ['哈哈哈', '好好笑', '也太好笑', '笑死', '笑爛', '廢到笑', '呵呵', '嘻嘻', '噗', '開心', '耶耶耶', '耶伊', 'YEAH', '呀比', '好開心', '撒花', '讚', '棒', '100分', '優秀', '厲害', '好可愛'], '表現難過': ['哭哭', '嗚嗚', '傷心', '桑心', '難過', '難受', '崩潰', '今天心情不美麗'], '祝賀對方': ['恭喜', '可喜可賀', '以你為榮', '替你開心', '給你第一名', '你真的hen棒', '這感覺太美妙'], '帶點懷疑': ['真的嗎', '真的假的', '真假', '是喔？', '屁啦', '你騙人', '我不相信'], '尷尬反應': ['尷尬了', '好尷尬', '誤會大了', '希望沒事'], '驚訝震驚': ['哇哇哇', '哇嗚', '哇塞', '哇靠', '到底', '這…', '驚', 'OMG', '天啊', '驚訝', '好Shock', '我的天'], '無言傻眼': ['瞎', '扯', '蛤', '呃', '呿', '…', '無言', '傻眼', '暈倒', '我暈'], '誇張荒謬': ['誇張', '離譜', '有事嗎', '很有事', '很有病', '太扯了', '沒救了', '忘了吃藥', '比扯鈴還扯'], '調皮搗蛋': ['幹嘛', '幹什麼', '想幹嘛', '你怪怪的'], '衷心感謝': ['謝謝', '感謝你', '大感激', '甘溫', '乾蝦', '辛苦了', '有你真好', '好貼心'], '誠摯道歉': ['抱歉', '對不起', 'Sorry', '拍謝', '不好意思'], '不必客氣': ['不客氣', '小事啦', '一塊小蛋糕', '沒關係', '沒事的', '應該的', '別介意', 'No mind', '別放心上'], '時間行程': ['等我一下', '等等我', '等你', '我等你', '晚點見', '明天見', 'See you', '路上小心', '一路順風'], '交通出門': ['在路上了', '我快到了', 'on the way', '我出門了', '出發', '剛出發', '已離開', '走囉'], '地點詢問': ['約哪兒', '在哪', '到哪裡了'], '忙碌相關': ['好忙', '忙翻', '忙到爆', '有話快說!'], '用餐相關': ['一起吃飯吧', '吃飯', '開飯', '開動', '開吃', '好好吃', '好美味', '吃飽沒'], '休息睡覺': ['好睏', '好想睡', '我先睡了', '想睡覺', '小睡片刻', '補眠中', '補眠去'], '天氣感受': ['好熱', '好冷', '快中暑了', '瑟瑟發抖', '秋風氣爽'], '注意提醒': ['注意', '緊盯', '嗶嗶嗶', '提高警覺', '給我小心點'], '意見表達': ['YES', '沒錯', '就是這樣', '同意', 'NO', '不行啦', '不可以', '我拒絕', '放過我', '母湯'], '參與話題': ['加1', '+1', '加我一個', '一起一起', '我也要'], '表態行動': ['我會加油的', '交給我吧', '使命必達', '為你效勞'], '約定承諾': ['打勾勾', '一言為定', '成交', '說好囉', '就這麼說定', '+1+1'], '思考回應': ['這樣啊', '我想想', '晚點回', '晚點再說', '我考慮一下'], '請求拜託': ['拜託拜託', '麻煩你了', '求求你', '考慮考慮麻!'], '正向情緒': ['打起精神來', '一切都會越來越好', '一切都是最好的安排', '好感動', '好感人', '活在當下', '珍惜當下', '期待', '充滿希望', '羨慕', '好幸福', '小確幸', '真幸運'], '負面情緒': ['好累', '心累', '累歪', '已攤', '心好累', '好無奈', '別逼我', '讓我靜靜', '懷疑人生', '為什麼要逼我', '好衰', '衰衰的', '有夠衰', '好倒霉哦', '惡人退散', '也太衰了吧'], '緊張憤怒': ['生氣', '氣死', '森77', '超級不爽', '好可怕', '嚇到我', '嚇我一跳'], '逃避現實': ['裝死', '逃避', '不想面對', '不想努力', '來啊', '我就爛', '誰怕誰', '來互相傷害啊'], '職場學習': ['開會中', '忙碌中', '加班中', '信回不完', '事情做不完', '耍廢中', '休假中', '別吵我', '今天放假', '要正向', '馬上處理', '考試加油', '一起努力', '想下班', '想放假', '不想上班', '週末快樂', '放假愉快', '下班啦', '可以回家了', '現在是星期五晚上', '來杯咖啡', '打起精神吧'], '幽默趣味': ['穴穴尼', 'ㄎㄎ', 'ㄏㄏ', '喵', '哼', '啾咪', '就醬吧', '美麥', '好開勳', '轉圈圈', '棒棒der', '開玩笑的啦', '認真就輸了', '登愣', '蝦毀', '突破盲點', '我的老天鵝', '聽你在唬爛', '要不要聽聽你在說什麼', '腦波弱', '當仙女好累', '靜靜的看著你', '沒看過仙女嗎？', '給你尷尬又不失禮的微笑', '不要問 很可怕'], '戀愛表達': ['我愛你', '最愛你了', '喜歡你', '妳是最可愛的', '有妳好幸福', '啾', '親親', '抱抱', '吻你', '親一個', '好想抱抱你', '想你', '想念你', '好想你', '期待重逢', '期待見面', '期待約會', '陪我', '來接我', '一起吃飯吧']}
V8_TEXT_EFFECT_CATALOG = {1: '胖胖貼紙字', 2: '棉花糖圓字', 3: '果凍QQ字', 4: '奶油餅乾字', 5: '糖霜甜點字', 6: '蠟筆童趣字', 7: '軟萌手寫字', 8: '日系手帳圓字', 9: '韓系軟萌字', 10: '漫畫衝擊字', 11: '對話泡泡字', 12: '貼紙白邊字', 13: '泡棉玩具字', 14: '橡膠軟墊字', 15: '樹脂亮面字', 16: '壓克力透明字', 17: '珐瑯徽章字', 18: '刺繡布章字', 19: '羊毛氈字', 20: '皮革壓印字', 21: '紙雕層疊字', 22: '摺紙立體字', 23: '陶瓷裂釉字', 24: '玉石浮雕字', 25: '大理石雕字', 26: '銀鋼浮雕字', 27: '黃金立體字', 28: '青銅復古字', 29: '冰晶透明字', 30: '水晶玻璃字', 31: '霓虹發光字', 32: '香港霓虹字', 33: '燈泡招牌字', 34: '木雕質感字', 35: '石刻厚重字', 36: '毛筆書法字', 37: '印章篆刻字', 38: '剪紙藝術字', 39: '復古海報字', 40: '打字機復古字', 41: '塗鴉潮流字', 42: '街頭塗鴉字', 43: '漫畫爆炸字', 44: '熱血漫畫字', 45: '手繪塗鴉字', 46: '極簡手寫字', 47: '浪漫手寫字', 48: '粉筆黑板字', 49: '神聖光輝字', 50: '暗黑哥德字', 51: '黏土手作字', 52: '拼布縫線字', 53: '珍珠貝殼字', 54: '羽毛飄逸字', 55: '竹編工藝字', 56: '稻草編織字', 57: '苔蘚森林字', 58: '藤蔓花園字', 59: '花瓣拼貼字', 60: '水彩暈染字', 61: '墨彩渲染字', 62: '彩鉛塗層字', 63: '蠟染布紋字', 64: '馬賽克磚字', 65: '植絨絨面字', 66: '蒸汽齒輪字', 67: '像素電玩字', 68: '八位元方塊字', 69: '故障數位字', 70: '全息雷射字', 71: '雲朵蓬鬆字', 72: '海鹽砂粒字', 73: '珊瑚海洋字', 74: '星砂夢幻字', 75: '宇宙星雲字', 76: '巧克力糖漿字', 77: '爆米花零食字', 78: '棉麻編織字', 79: '牛仔布貼字', 80: '蕾絲花邊字', 81: '鈕扣拼貼字', 82: '鉤針編織字', 83: '彩窗教堂字', 84: '鐵鐵鉚釘字', 85: '鐵鏽工業字', 86: '電路晶片字', 87: '液晶螢幕字', 88: '雷達掃描字', 89: '橡皮印刷字', 90: '油畫筆觸字', 91: '膠卷電影字', 92: '報紙剪貼字', 93: '牛皮紙包裝字', 94: '露珠葉脈字', 95: '螢火森林字', 96: '星座占卜字', 97: '草本藥鋪字', 98: '珍奶Q彈字', 99: '壽司食玩字', 100: '甜甜圈糖針字', 101: '水墨毛筆字', 102: '行書連筆字', 103: '潑墨寫意字', 104: '篆刻印章字', 105: '鋼筆流線字', 106: '打字機復古字', 107: '粉筆手繪字', 108: '彩虹手繪字', 109: '塗鴉手繪字', 110: '立體貼紙字', 111: '氣球立體字', 112: '布料拼貼字', 113: '草地綠植字', 114: '沙灘沙粒字', 115: '雲朵棉花字', 116: '寒霜冰裂字', 117: '熔岩裂石字', 118: '鏽蝕金屬字', 119: '乾裂泥土字', 120: '鑽石切割字', 121: '雷射幻彩字', 122: '液態金屬字', 123: '霓虹燈管字', 124: '復古燈泡字', 125: '像素點陣字'}
V8_TEXT_STYLE_OPTIONS = ["高級立體金字","彩色漫畫爆炸","柔和立體氣泡","霓虹發光字","手寫貼紙字","清爽白底字"]
V8_TEXT_EFFECT_VALUES = [f"{i:03d}｜{V8_TEXT_EFFECT_CATALOG[i]}" for i in range(1,126)]
V8_FONT_PREVIEW_DIR = Path(__file__).with_name("font_reference") / "previews"

POPULAR_STYLES = [
    "↓ 請選擇風格","Q版黏土3D","Q版收藏公仔","3D收藏公仔",
    "療癒系Cute Wstyle","大頭小身","LINE貼圖風","柔和光影",
    "手作玩偶風","可愛漫畫風","立體卡通風",
]

CHARACTER_OPTIONS = [
    "五官比例保留","服飾配件保留","人物辨識度保留",
    "Q版收藏公仔","療癒系 Cute Wstyle","大頭小身",
    "LINE貼圖風","柔和光影",
]

for i in range(8):
    st.session_state.setdefault(f"sticker_text_{i}", "")
st.session_state.setdefault("uploaded_image_bytes", None)
st.session_state.setdefault("generated_4x2_bytes", None)
st.session_state.setdefault("last_prompt", "")
st.session_state.setdefault("crop_boxes", None)

def get_texts():
    return [st.session_state.get(f"sticker_text_{i}", "") for i in range(8)]

def set_texts(values):
    values = list(values)[:8] + [""] * 8
    for i in range(8):
        st.session_state[f"sticker_text_{i}"] = str(values[i])

def base_boxes(w, h):
    boxes = []
    for i in range(8):
        c, r = i % 4, i // 4
        x1 = round(c * w / 4)
        x2 = round((c + 1) * w / 4)
        y1 = round(r * h / 2)
        y2 = round((r + 1) * h / 2)
        boxes.append([x1, y1, x2, y2])
    return boxes

def build_prompt(style, custom_style, selected_character, custom_character,
                 texts, transparent):
    p = [
        "請以我提供的人物照片作為主要人物參考。",
        "保留人物身份辨識特徵，不任意改變人物核心外觀。",
        "請一次生成一張清楚的4×2八格LINE貼圖總圖。",
        "第一排四格、第二排四格；依使用者輸入順序由左至右、由上至下對應。",
        "八格人物維持同一人物身份與主要視覺風格。",
        "每格人物完整呈現，不要裁切頭部、臉部、身體或四肢。",
        "人物與該格邊界保持安全距離。",
        "不要拉伸、變形或壓縮人物。",
        "非常重要：圖片中禁止出現01、02、03、04、05、06、07、08等編號。",
        "禁止加入格號、序號、位置標籤或數字標記。",
        "只有使用者指定的貼圖文字可以出現在圖片中。",
    ]
    if style != "↓ 請選擇風格":
        p.append(f"主要貼圖風格：{style}。")
    if custom_style.strip():
        p.append(f"使用者自定風格：{custom_style.strip()}。")
    if selected_character:
        p.append("人物與畫面特色：" + "、".join(selected_character) + "。")
    if custom_character.strip():
        p.append(f"使用者自定人物／場景要求：{custom_character.strip()}。")
    for i, t in enumerate(texts):
        p.append(f"第{i+1}格的指定貼圖文字為：「{t.strip() or '（此格未指定文字）'}」。")
    if transparent:
        p.append("請使用透明背景PNG，背景保持真正透明，不要以白色或黑色填滿。")
    p.append("整體具有LINE貼圖的清楚、可讀、可愛與完整構圖感。")
    return "\n".join(p)

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
st.markdown("""<style>
.v10-rainbow-title{padding:8px 14px;border-radius:12px;margin:8px 0 12px;font-weight:700;background:linear-gradient(90deg,#fff1f2,#fff7ed,#fefce8,#f0fdf4,#eff6ff,#f5f3ff);}
.v10-soft-box{padding:8px 12px;border-radius:10px;background:#fafafa;border:1px solid #e5e7eb;}
</style>""",unsafe_allow_html=True)

st.title("🎨 LINE 貼圖創作工作室")
st.caption("V10 STEP 10C｜原生 Canvas 直接拖曳裁切")
st.divider()

st.header("📷 ① 上傳人物照片")
uploaded = st.file_uploader("選擇人物照片", type=["jpg","jpeg","png","webp"])
if uploaded:
    try:
        uploaded.seek(0)
        im = Image.open(uploaded)
        im.load()
        b = BytesIO()
        im.convert("RGBA").save(b, "PNG")
        st.session_state.uploaded_image_bytes = b.getvalue()
        st.image(im, caption="人物照片", width=420)
        st.success("✅ 人物照片已載入")
    except Exception as e:
        st.error("❌ 無法讀取人物照片")
        st.code(str(e))

st.divider()
st.header("🎨 ② 貼圖風格")
st.caption("🌈 先選一種模式：V8 預設風格，或「自定義風格」。兩者不會同時生效。")

# ------------------------------------------------------------
# 風格主選單：
# 第一層直接選 V8 風格
# 最後一項才是「⭐ 自定義風格」
# ------------------------------------------------------------
V8_STYLE_CUSTOM_OPTION = "⭐ 自定義風格"
style_options = ["↓ 請選擇風格"] + [
    x for x in V8_STYLES if not x.startswith("⭐ 自訂")
] + [V8_STYLE_CUSTOM_OPTION]

style_mode = st.selectbox(
    "🌈 貼圖風格",
    style_options,
    key="v10_style_mode",
)

# ------------------------------------------------------------
# 預設風格模式
# ------------------------------------------------------------
if style_mode != V8_STYLE_CUSTOM_OPTION:
    style = style_mode

    # 正常 V8 風格時，不顯示自定義欄位。
    # 這樣使用者不會產生「Q版黏土＋自定義，到底誰生效？」的疑問。
    custom_style = ""

# ------------------------------------------------------------
# 自定義風格模式
# 只有選到「⭐ 自定義風格」才顯示
# ------------------------------------------------------------
else:
    st.success("✨ 已切換到「自定義風格」模式")

    _custom_style_slots = []
    for _i in range(1, 11):
        _sv = st.session_state.get(f"v10_style_custom_{_i}", "").strip()
        _sn = st.session_state.get(
            f"v10_style_name_{_i}",
            f"使用者自定{_i}"
        ).strip() or f"使用者自定{_i}"

        if _sv:
            _custom_style_slots.append((_i, _sn, _sv))

    if _custom_style_slots:
        _saved_labels = [
            f"{i:02d}｜{name}"
            for i, name, _ in _custom_style_slots
        ]

        _selected_saved = st.selectbox(
            "💾 選擇已儲存的自定義風格",
            ["✏️ 直接輸入新的自定義風格"] + _saved_labels,
            key="v10_saved_custom_style_choice",
        )

        if _selected_saved != "✏️ 直接輸入新的自定義風格":
            _selected_index = _saved_labels.index(_selected_saved)
            _selected_slot = _custom_style_slots[_selected_index]
            custom_style = _selected_slot[2]
            st.info(
                f"💾 已套用：{_selected_slot[0]:02d}｜{_selected_slot[1]}"
            )
        else:
            custom_style = ""
    else:
        _selected_saved = "✏️ 直接輸入新的自定義風格"
        custom_style = ""

    # 只有在自定義模式才出現 1～10 編輯區。
    with st.expander("💾 編輯／儲存自定義風格 1～10", expanded=False):
        for _i in range(1, 11):
            _a, _b = st.columns([1, 4])

            with _a:
                st.text_input(
                    f"名稱 {_i:02d}",
                    key=f"v10_style_name_{_i}",
                )

            with _b:
                st.text_area(
                    f"自定義風格 {_i:02d}",
                    key=f"v10_style_custom_{_i}",
                    height=65,
                )

        if st.button(
            "💾 儲存 10 組自定風格",
            key="v10_save_styles",
            use_container_width=True,
        ):
            if _save_v10_presets():
                st.success("✅ 10 組自定風格已儲存")
                st.rerun()
            else:
                st.error("❌ 儲存失敗")

    # 本次臨時輸入，只在自定義模式有效。
    _direct_custom = st.text_area(
        "✏️ 本次自定義風格",
        value="" if custom_style else custom_style,
        height=90,
        key="v10_custom_style_current",
        help="只有「自定義風格」模式會使用這裡的內容。",
    )

    # 如果使用者有直接輸入，就以本次輸入為最終自定義風格。
    if _direct_custom.strip():
        custom_style = _direct_custom.strip()

    # 自定義模式下，style 不再使用 V8 預設風格。
    style = "↓ 請選擇風格"

    st.warning(
        "ℹ️ 目前為「自定義風格」模式：V8 預設風格不會同時套用。"
    )

with st.expander("📚 查看 V8 全部風格", expanded=False):
    st.write("、".join([
        x for x in V8_STYLES if not x.startswith("⭐ 自訂")
    ]))

st.divider()
st.header("👤 ③ 人物與畫面特色")
st.caption("可複選；以下 3 組自定義人物／場景需求，只有打勾才會啟用。")
selected_character=st.multiselect("🎯 V8 人物／畫面特色（可複選）",CHARACTER_OPTIONS,key="v10_character_options")
for _i in range(1,4):
    _c1,_c2=st.columns([1,8])
    with _c1:
        st.checkbox("啟用",key=f"v10_character_enabled_{_i}")
    with _c2:
        st.text_area(f"自定義人物／場景需求 {_i}",key=f"v10_character_custom_{_i}",height=70)
_custom_character_values=[st.session_state.get(f"v10_character_custom_{_i}","").strip() for _i in range(1,4) if st.session_state.get(f"v10_character_enabled_{_i}",False)]
custom_character="\n".join(_custom_character_values)
if st.button("💾 儲存人物／場景設定",key="v10_save_character",use_container_width=True):
    st.success("✅ 3 組人物／場景設定已儲存") if _save_v10_presets() else st.error("❌ 儲存失敗")

st.header("💬 ④ 01～08 貼圖文字（V8完整語詞庫）")

# V8 全部隨機用語池。
_pool_names = list(V8_RANDOM_POOLS.keys())
_pool_choice = st.selectbox(
    "🎲 隨機用語分類",
    ["全部隨機"] + _pool_names,
    key="v8_pool_choice"
)

a,b,c = st.columns(3)
with a:
    if st.button("🎲 骰一次 8 句", use_container_width=True):
        if _pool_choice == "全部隨機":
            pool = [x for vals in V8_RANDOM_POOLS.values() for x in vals]
        else:
            pool = V8_RANDOM_POOLS.get(_pool_choice, [])
        vals = random.sample(pool, min(8, len(pool)))
        while len(vals) < 8 and pool:
            vals.append(random.choice(pool))
        random.shuffle(vals)
        set_texts(vals)
        st.rerun()
with b:
    if st.button("🔄 清空 8 格", use_container_width=True):
        set_texts([""]*8)
        st.rerun()
with c:
    st.write(f"V8 語詞分類：{len(_pool_names)} 類")

# V8 常用語參考：選分類 → 選語句 → 指定格。
p1,p2,p3 = st.columns([1.2,2.4,0.8])
with p1:
    _common_cat = st.selectbox("常用語分類", _pool_names, key="v8_common_cat")
with p2:
    _common_phrase = st.selectbox("常用語參考", V8_RANDOM_POOLS.get(_common_cat, []), key="v8_common_phrase")
with p3:
    _target_slot = st.selectbox("放入第", [f"{i:02d}" for i in range(1,9)], key="v8_target_slot")
if st.button("➕ 放入選定格", key="v8_insert_phrase"):
    set_texts([
        _common_phrase if i == int(_target_slot)-1 else st.session_state.get(f"sticker_text_{i}","")
        for i in range(8)
    ])
    st.rerun()

cols = st.columns(4)
for i, col in enumerate(cols):
    with col:
        st.text_input(f"{i+1:02d}", key=f"sticker_text_{i}")
cols = st.columns(4)
for i, col in enumerate(cols, start=4):
    with col:
        st.text_input(f"{i+1:02d}", key=f"sticker_text_{i}")

texts = get_texts()
filled = sum(bool(x.strip()) for x in texts)
st.info(f"已填寫 {filled} / 8 格")

with st.expander("📚 查看 V8 全部語詞分類與內容", expanded=False):
    for cat, vals in V8_RANDOM_POOLS.items():
        st.markdown(f"**{cat}**")
        st.write("、".join(vals))


st.divider()
st.header("🔤 ⑤ 貼圖字型＋125 種帶圖字型")

text_style = st.selectbox(
    "文字貼圖效果",
    V8_TEXT_STYLE_OPTIONS,
    index=0,
    key="v8_text_style"
)

_selected_font = st.session_state.get("v8_selected_font", None)
if _selected_font:
    st.success(f"🎨 已選擇 125 字型：{_selected_font:03d}｜{V8_TEXT_EFFECT_CATALOG[_selected_font]}")
else:
    st.info("尚未指定 125 種字型；可從下方總覽選用。")

# ------------------------------------------------------------
# 125 種帶圖字型總覽
# 選中後「整個區塊不再渲染」，因此會真正收起，而不是只抖動。
# ------------------------------------------------------------
if "v10_font_gallery_open" not in st.session_state:
    st.session_state.v10_font_gallery_open = False

if st.button(
    "📚 125 種帶圖字型總覽" if not st.session_state.v10_font_gallery_open
    else "📖 關閉 125 種帶圖字型總覽",
    key="v10_font_gallery_toggle",
    use_container_width=True,
):
    st.session_state.v10_font_gallery_open = not st.session_state.v10_font_gallery_open
    st.rerun()

if st.session_state.v10_font_gallery_open:
    st.caption("🖱️ 點選字型後會立即關閉總覽，並回到目前選擇結果。")

    _font_cols = st.columns(5)
    for _i in range(1, 126):
        _p = V8_FONT_PREVIEW_DIR / f"{_i:03d}.jpg"
        if not _p.exists():
            continue

        with _font_cols[(_i - 1) % 5]:
            st.image(str(_p), use_container_width=True)
            st.caption(f"{_i:03d}｜{V8_TEXT_EFFECT_CATALOG[_i]}")

            if st.button(
                f"選用 {_i:03d}",
                key=f"font_pick_{_i}",
                use_container_width=True,
            ):
                st.session_state.v8_selected_font = _i

                # 核心：下一次 rerun 時完全不渲染 125 總覽。
                st.session_state.v10_font_gallery_open = False

                st.rerun()


with st.expander("🔎 已選字型大圖", expanded=False):
    if _selected_font:
        _p = V8_FONT_PREVIEW_DIR / f"{_selected_font:03d}.jpg"
        if _p.exists():
            st.image(str(_p), caption=f"{_selected_font:03d}｜{V8_TEXT_EFFECT_CATALOG[_selected_font]}", use_container_width=True)
            st.caption("以上為 V8 參考效果；實際生成會由 AI 依人物、文字與整體風格重新詮釋。")
    else:
        st.write("尚未選擇。")

st.divider()
st.header("🌈 ⑥ 背景設定")
transparent = st.checkbox("使用透明背景 PNG", value=False)

prompt = build_prompt(style, custom_style, selected_character,
                      custom_character, texts, transparent)

if style_mode == V8_STYLE_CUSTOM_OPTION:
    prompt += (
        "\n【V10 風格模式】目前使用「自定義風格」模式。"
        "請不要另外套用任何 V8 預設風格，只依照使用者自定義風格描述生成。"
    )
else:
    prompt += (
        f"\n【V10 風格模式】目前使用 V8 預設風格：「{style_mode}」。"
        "不要把未選取的自定義風格加入生成。"
    )

_selected_font_for_prompt = st.session_state.get("v8_selected_font")
if text_style:
    prompt += f"\n文字貼圖效果（V8）：{text_style}。"
if _selected_font_for_prompt:
    prompt += (
        f"\n125種帶圖字型參考：{_selected_font_for_prompt:03d}｜"
        f"{V8_TEXT_EFFECT_CATALOG[_selected_font_for_prompt]}。"
        "\n請把此字型當作文字材質與視覺參考，不要照搬參考圖中的人物或其他內容。"
    )
with st.expander("🔍 查看 AI Prompt"):
    st.code(prompt, language="text")

st.header("✨ ⑦ 生成 4×2 原始總圖")
if st.button("✨ 生成 4×2 八格總圖", type="primary", use_container_width=True):
    if not st.session_state.uploaded_image_bytes:
        st.warning("請先上傳人物照片。")
        st.stop()
    if not filled:
        st.warning("請至少輸入一格貼圖文字。")
        st.stop()
    with st.spinner("AI 正在生成 4×2 原始總圖……"):
        try:
            ib = BytesIO(st.session_state.uploaded_image_bytes)
            result = client.images.edit(
                model="gpt-image-2",
                image=("person.png", ib, "image/png"),
                prompt=(
                    prompt
                    + "\n\n【透明背景強制要求】"
                    + "\n輸出必須是真正的透明 PNG Alpha 背景。"
                    + "\n背景區域必須為 Alpha=0，不得繪製白色、灰色或任何棋盤格圖案。"
                    + "\n絕對不要用棋盤格、灰白方格或任何圖案來模擬透明背景。"
                    + "\n人物、物件與文字保留正常不透明像素，只有背景透明。"
                ),
                size="1536x1024",
                background="transparent",
                output_format="png",
            )
            raw = base64.b64decode(result.data[0].b64_json)
            img = Image.open(BytesIO(raw)).convert("RGBA")
            out = BytesIO()
            img.save(out, "PNG")
            st.session_state.generated_4x2_bytes = out.getvalue()
            st.session_state.crop_boxes = None
            st.success("🎉 4×2 原始總圖生成成功！")

            # ============================================================
            # 🔎 透明背景診斷：檢查「AI剛生成的原始4×2 PNG」
            # ============================================================
            alpha = img.getchannel("A")
            amin, amax = alpha.getextrema()
            hist = alpha.histogram()
            transparent_px = int(hist[0])
            total_px = int(img.width * img.height)
            transparent_pct = transparent_px / total_px * 100 if total_px else 0

            st.markdown("### 🔎 透明背景診斷")
            d1, d2, d3 = st.columns(3)
            d1.metric("圖片模式", img.mode)
            d2.metric("透明像素", f"{transparent_pct:.2f}%")
            d3.metric("Alpha 範圍", f"{amin} ～ {amax}")

            if transparent_px > 0:
                st.success(
                    f"🟢 **原始生成圖確認含有真正透明像素**："
                    f"{transparent_px:,} / {total_px:,} "
                    f"({transparent_pct:.2f}%) Alpha=0。"
                )
            else:
                st.error(
                    "🔴 **原始生成圖沒有任何透明像素！** "
                    "如果畫面看起來像棋盤格，棋盤格很可能已經被生成成圖片內容。"
                )

            if amin == 255 and amax == 255:
                st.warning("⚠️ Alpha 全部為 255：這張原始圖實際上是完全不透明的。")
            elif amin == 0 and amax == 255:
                st.info("ℹ️ Alpha 同時存在 0 與 255：這是正常透明 PNG 的典型狀態。")
            elif amin == 0:
                st.info("ℹ️ 有 Alpha=0，但透明像素分布需要進一步判斷。")
        except Exception as e:
            st.error("❌ 生成失敗")
            st.code(str(e))

# ------------------------------------------------------------
# STEP 10C native component
# ------------------------------------------------------------
if st.session_state.generated_4x2_bytes:
    st.divider()
    st.header("✂️ ⑦ 直接用滑鼠調整 8 個裁切框")

    src = Image.open(BytesIO(st.session_state.generated_4x2_bytes)).convert("RGBA")
    w, h = src.size

    if st.session_state.crop_boxes is None:
        st.session_state.crop_boxes = base_boxes(w, h)

    st.info(
        "直接拖曳：移動裁切框。拖曳四角：改變大小。"
        "拖曳四邊：單方向調整。8 個框同時顯示，不需要逐張打開。"
    )

    # --------------------------------------------------------
    # 明確顯示原始 4×2 圖
    # 不依賴 Canvas 是否成功載入圖片。
    # 固定預覽寬度，避免隨網頁容器無限放大。
    # --------------------------------------------------------
    st.subheader("🖼️ 原始 4×2 圖片")
    st.image(
        st.session_state.generated_4x2_bytes,
        caption=f"原始生成圖：{w} × {h} px",
        width=900,
    )

    st.caption(
        "上方是原始圖片預覽；下方 Canvas 才是可直接拖曳的裁切操作區。"
    )

    _CROP_HTML_TEMPLATE = '<!doctype html>\n<html><head><meta charset="utf-8">\n<style>\n*{box-sizing:border-box}\nbody{margin:0;font-family:Arial,"Microsoft JhengHei",sans-serif;color:#333}\n.help{font-size:14px;line-height:1.6;background:#f5f7fa;padding:10px;border-radius:8px}\n.viewer{position:relative;width:720px;max-width:100%;margin:10px auto 0;border:1px solid #bbb;border-radius:8px;overflow:hidden;background:#eee}\n#cv{display:block;width:720px;max-width:100%;height:auto;touch-action:none;user-select:none}\n.status{font-size:14px;padding:8px 0;color:#555}\n.actions{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}\nbutton{border:0;border-radius:8px;padding:9px 13px;cursor:pointer}\nbutton.primary{background:#222;color:#fff}\nbutton.lock{background:#333;color:#fff}\nbutton:disabled{opacity:.45;cursor:not-allowed}\n.coords{font:13px/1.5 Consolas,monospace;white-space:pre-wrap;background:#f7f7f7;padding:10px;border-radius:8px}\n.legend{font-size:13px;padding:6px 0}\n</style></head><body>\n<div class="help">\n<b>📍 定位點裁切</b><br>\n先用 3 條垂直定位線＋1 條水平定位線微調 4×2 分割位置。\n拖曳定位線即可調整；按「🔒 鎖定定位」後，程式會由定位線自動產生 01～08 裁切框。\n</div>\n<div class="viewer"><canvas id="cv"></canvas></div>\n<div class="status" id="status">正在建立定位線……</div>\n<div class="legend">🔴 左邊界\u3000🔵 內部分隔線\u3000🟢 右邊界\u3000🟠 水平分隔線\u3000｜\u3000🔒 鎖定後可進行裁切</div>\n<div class="actions">\n<button onclick="resetGuides()">↩️ 恢復標準4×2</button>\n<button id="lockBtn" class="lock" onclick="toggleLock()">🔒 鎖定定位</button>\n<button id="downloadBtn" class="primary" onclick="downloadAll()" disabled>✂️ 裁切並下載01～08</button>\n</div>\n<div class="coords" id="coords"></div>\n\n<script>\nconst B64="__IMAGE_B64__", IW=__IW__, IH=__IH__;\nconst cv=document.getElementById("cv"),ctx=cv.getContext("2d");\nconst statusEl=document.getElementById("status"),coordsEl=document.getElementById("coords");\nconst lockBtn=document.getElementById("lockBtn"),downloadBtn=document.getElementById("downloadBtn");\nconst colors=["#ff4040","#3987ff","#32ad61","#ff922e"];\nlet scale=1,locked=false,active=-1,startX=0,startY=0,snap=null;\n\nfunction clamp(v,a,b){return Math.max(a,Math.min(b,v))}\nfunction guidesDefault(){\n  return {\n    x:[0,IW/4,IW/2,3*IW/4,IW],\n    y:[0,IH/2,IH]\n  };\n}\nlet g=guidesDefault();\n\nconst image=new Image();\nimage.src="data:image/png;base64,"+B64;\n\nfunction resize(){\n  const viewer=cv.parentElement;\n  const mw=Math.min(720,Math.max(320,viewer.clientWidth||720));\n  cv.width=Math.round(mw);\n  cv.height=Math.round(mw*IH/IW);\n  scale=cv.width/IW;\n  draw();\n}\n\nfunction boxes(){\n  const out=[];\n  for(let r=0;r<2;r++){\n    for(let c=0;c<4;c++){\n      out.push([g.x[c],g.y[r],g.x[c+1],g.y[r+1]]);\n    }\n  }\n  return out;\n}\n\nfunction draw(){\n  ctx.clearRect(0,0,cv.width,cv.height);\n  ctx.drawImage(image,0,0,cv.width,cv.height);\n\n  // Slight guide shading.\n  ctx.save();\n  ctx.fillStyle="rgba(255,255,255,.08)";\n  ctx.fillRect(0,0,cv.width,cv.height);\n  ctx.restore();\n\n  // Draw 5 vertical guide lines.\n  for(let i=0;i<5;i++){\n    const x=g.x[i]*scale;\n    ctx.save();\n    ctx.strokeStyle=i===0||i===4?"#ff4040":"#3987ff";\n    ctx.lineWidth=i===0||i===4?2.5:2;\n    ctx.setLineDash([10,7]);\n    ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,cv.height);ctx.stroke();\n    ctx.setLineDash([]);\n    ctx.fillStyle=i===0||i===4?"#ff4040":"#3987ff";\n    ctx.fillRect(x-5,4,10,18);\n    ctx.restore();\n  }\n\n  // Draw 3 horizontal guide lines.\n  for(let i=0;i<3;i++){\n    const y=g.y[i]*scale;\n    ctx.save();\n    ctx.strokeStyle="#ff922e";\n    ctx.lineWidth=i===1?2.5:2;\n    ctx.setLineDash([10,7]);\n    ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(cv.width,y);ctx.stroke();\n    ctx.setLineDash([]);\n    ctx.fillStyle="#ff922e";\n    ctx.fillRect(4,y-5,22,10);\n    ctx.restore();\n  }\n\n  // Number each derived cell; these are guide labels only.\n  const b=boxes();\n  const cellColors=["#ff4040","#3987ff","#32ad61","#a04bd0","#ff922e","#25aeb0","#db3f9b","#956c3c"];\n  for(let i=0;i<8;i++){\n    const x=b[i][0]*scale,y=b[i][1]*scale;\n    ctx.save();\n    ctx.font="bold 17px Arial";\n    ctx.lineWidth=3;\n    ctx.strokeStyle="rgba(255,255,255,.95)";\n    ctx.strokeText(String(i+1).padStart(2,"0"),x+8,y+21);\n    ctx.fillStyle=cellColors[i];\n    ctx.fillText(String(i+1).padStart(2,"0"),x+8,y+21);\n    ctx.restore();\n  }\n\n  updateCoords();\n}\n\nfunction updateCoords(){\n  const b=boxes();\n  let s="";\n  for(let i=0;i<8;i++){\n    const q=b[i].map(v=>Math.round(v));\n    s+=String(i+1).padStart(2,"0")+"：X "+q[0]+"～"+q[2]+"｜Y "+q[1]+"～"+q[3]+"｜"+(q[2]-q[0])+"×"+(q[3]-q[1])+" px\\n";\n  }\n  coordsEl.textContent=s;\n}\n\nfunction pointerPos(e){\n  const r=cv.getBoundingClientRect();\n  return {x:(e.clientX-r.left)*IW/r.width,y:(e.clientY-r.top)*IH/r.height};\n}\n\nfunction nearestGuide(p){\n  const tol=Math.max(16,16/scale);\n  let best=-1,bd=Infinity,type="";\n  for(let i=1;i<4;i++){\n    const d=Math.abs(p.x-g.x[i]);\n    if(d<tol&&d<bd){best=i;bd=d;type="x";}\n  }\n  const dy=Math.abs(p.y-g.y[1]);\n  if(dy<tol&&dy<bd){best=1;bd=dy;type="y";}\n  return {index:best,type:type};\n}\n\ncv.addEventListener("pointerdown",e=>{\n  if(locked)return;\n  const p=pointerPos(e),h=nearestGuide(p);\n  if(h.index<0)return;\n  e.preventDefault();\n  try{cv.setPointerCapture(e.pointerId)}catch(_){}\n  active=h.index;startX=p.x;startY=p.y;snap={x:[...g.x],y:[...g.y],type:h.type};\n  statusEl.textContent="🖱️ 正在調整定位線……";\n});\n\ncv.addEventListener("pointermove",e=>{\n  if(active<0||locked)return;\n  e.preventDefault();\n  const p=pointerPos(e);\n  if(snap.type==="x"){\n    const min=30;\n    const lo=g.x[active-1]+min,hi=g.x[active+1]-min;\n    g.x[active]=clamp(snap.x[active]+(p.x-startX),lo,hi);\n  }else{\n    const min=30;\n    g.y[1]=clamp(snap.y[1]+(p.y-startY),g.y[0]+min,g.y[2]-min);\n  }\n  draw();\n});\n\ncv.addEventListener("pointerup",e=>{\n  if(active>=0){try{cv.releasePointerCapture(e.pointerId)}catch(_){}}\n  active=-1;\n  if(!locked)statusEl.textContent="✅ 定位線已更新";\n});\n\nfunction resetGuides(){\n  locked=false;\n  g=guidesDefault();\n  lockBtn.textContent="🔒 鎖定定位";\n  downloadBtn.disabled=true;\n  statusEl.textContent="↩️ 已恢復標準4×2定位";\n  draw();\n}\n\nfunction toggleLock(){\n  locked=!locked;\n  if(locked){\n    lockBtn.textContent="🔓 解鎖定位";\n    downloadBtn.disabled=false;\n    statusEl.textContent="🔒 定位已鎖定，可以開始裁切";\n  }else{\n    lockBtn.textContent="🔒 鎖定定位";\n    downloadBtn.disabled=true;\n    statusEl.textContent="🛠️ 定位已解鎖，可以繼續微調";\n  }\n  draw();\n}\n\nfunction saveBlob(blob,name){\n  const u=URL.createObjectURL(blob),a=document.createElement("a");\n  a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();\n  setTimeout(()=>URL.revokeObjectURL(u),1000);\n}\n\n// V10 STEP 10C.6：移植 V8「邊界連通背景移除」邏輯。\n// 只移除從圖片邊緣連通、且接近背景色的區域；不整片刪除人物/文字中的白色。\nfunction removeConnectedBackground(canvas, tolerance=30){\n  const ctx2=canvas.getContext("2d",{willReadFrequently:true});\n  const W=canvas.width,H=canvas.height;\n  const img=ctx2.getImageData(0,0,W,H);\n  const px=img.data;\n\n  const pts=[\n    [0,0],[W-1,0],[0,H-1],[W-1,H-1],\n    [Math.min(4,W-1),Math.min(4,H-1)],\n    [Math.max(0,W-5),Math.min(4,H-1)],\n    [Math.min(4,W-1),Math.max(0,H-5)],\n    [Math.max(0,W-5),Math.max(0,H-5)]\n  ];\n\n  let sr=0,sg=0,sb=0,count=0;\n  for(const [x,y] of pts){\n    const k=(y*W+x)*4;\n    if(px[k+3]===0) continue;\n    sr+=px[k]; sg+=px[k+1]; sb+=px[k+2]; count++;\n  }\n  if(count===0) return;\n\n  const bg=[sr/count,sg/count,sb/count];\n  const tol2=tolerance*tolerance;\n\n  function nearBg(k){\n    if(px[k+3]===0) return true;\n    const dr=px[k]-bg[0],dg=px[k+1]-bg[1],db=px[k+2]-bg[2];\n    return dr*dr+dg*dg+db*db<=tol2;\n  }\n\n  const seen=new Uint8Array(W*H);\n  const qx=[],qy=[];\n  let head=0;\n\n  function push(x,y){\n    if(x<0||x>=W||y<0||y>=H) return;\n    const n=y*W+x;\n    if(seen[n]) return;\n    seen[n]=1;\n    qx.push(x);qy.push(y);\n  }\n\n  for(let x=0;x<W;x++){push(x,0);push(x,H-1);}\n  for(let y=0;y<H;y++){push(0,y);push(W-1,y);}\n\n  while(head<qx.length){\n    const x=qx[head],y=qy[head++];\n    const k=(y*W+x)*4;\n    if(!nearBg(k)) continue;\n    px[k+3]=0;\n    push(x-1,y);push(x+1,y);push(x,y-1);push(x,y+1);\n  }\n\n  ctx2.putImageData(img,0,0);\n}\n\nfunction makeSticker(i){\n  const b=boxes()[i].map(v=>Math.round(v));\n  const x1=clamp(b[0],0,IW-2),y1=clamp(b[1],0,IH-2);\n  const x2=clamp(b[2],x1+2,IW),y2=clamp(b[3],y1+2,IH);\n  const cw=370,ch=320,sw=x2-x1,sh=y2-y1;\n  const rat=Math.min(cw/sw,ch/sh),nw=Math.max(1,Math.round(sw*rat)),nh=Math.max(1,Math.round(sh*rat));\n\n  const o=document.createElement("canvas");\n  o.width=cw;o.height=ch;\n  const octx=o.getContext("2d",{willReadFrequently:true});\n  octx.clearRect(0,0,cw,ch);\n\n  // 保留 V10 原本的定位點裁切、等比例縮放、置中。\n  octx.drawImage(\n    image,x1,y1,sw,sh,\n    Math.round((cw-nw)/2),Math.round((ch-nh)/2),nw,nh\n  );\n\n  // 只有勾選「透明背景 PNG」時才套用 V8 邏輯。\n  if(__TRANSPARENT__){\n    removeConnectedBackground(o,30);\n  }\n\n  return new Promise(r=>o.toBlob(r,"image/png"));\n}\n\nasync function downloadAll(){\n  if(!locked)return;\n  statusEl.textContent="⏳ 正在製作01～08 PNG……";\n  for(let i=0;i<8;i++){\n    saveBlob(await makeSticker(i),String(i+1).padStart(2,"0")+".png");\n    await new Promise(r=>setTimeout(r,180));\n  }\n  statusEl.textContent="🎉 01～08 已全部裁切並下載！";\n}\n\nimage.onload=()=>{\n  resize();\n  statusEl.textContent="✅ 定位線已建立，可以直接拖曳藍色垂直線與橙色水平線";\n};\nwindow.addEventListener("resize",resize);\n</script></body></html>'
    _image_b64 = base64.b64encode(st.session_state.generated_4x2_bytes).decode("ascii")
    _boxes_json = __import__("json").dumps(st.session_state.crop_boxes, ensure_ascii=False)
    _crop_html = _CROP_HTML_TEMPLATE.replace("__IMAGE_B64__", _image_b64).replace("__IW__", str(int(w))).replace("__IH__", str(int(h))).replace("__BOXES__", _boxes_json).replace("__TRANSPARENT__", "true" if transparent else "false")
    import streamlit.components.v1 as components
    components.html(
        _crop_html,
        height=760,
        scrolling=False,
    )


    # ============================================================
    # V10 STEP 11B.1
    # 直接從 01～08 選擇 MAIN / TAB＋一鍵打包
    #
    # 設計原則：
    # 1. 不重新上傳 01～08。
    # 2. 不修改 STEP 10C.8 的 AI 生成、透明、定位核心。
    # 3. 使用目前原始 4×2 圖＋定位座標直接在伺服器端裁切。
    # 4. main/tab 選擇與裁切在同一頁完成。
    # ============================================================
    st.divider()
    st.header("⭐ STEP 11B｜選擇 MAIN / TAB")
    st.caption("不用重新上傳圖片。調整好定位線後，直接指定哪一格做 MAIN、哪一格做 TAB。")

    # The browser editor keeps the guide coordinates in JS. For this first
    # stable version, provide a simple 01～08 selector tied to the standard
    # 4×2 positions. The final crop package still uses the original image.
    _main_tab_cols = st.columns(4)
    _main_tab_options = [f"{i:02d}" for i in range(1,9)]

    if "step11b1_main" not in st.session_state:
        st.session_state.step11b1_main = "01"
    if "step11b1_tab" not in st.session_state:
        st.session_state.step11b1_tab = "02"

    with _main_tab_cols[0]:
        st.markdown("### ⭐ MAIN")
    with _main_tab_cols[1]:
        st.markdown("### 🏷️ TAB")
    with _main_tab_cols[2]:
        st.markdown("### 📦 完整套件")
    with _main_tab_cols[3]:
        st.markdown("### 🔎 透明")

    cmain, ctab = st.columns(2)
    with cmain:
        main_no = st.selectbox(
            "選擇 MAIN",
            _main_tab_options,
            index=_main_tab_options.index(st.session_state.step11b1_main),
            key="step11b1_main_select",
            help="此格會製作 main.png（240×240）"
        )
        st.session_state.step11b1_main = main_no

    with ctab:
        tab_choices = [x for x in _main_tab_options if x != main_no]
        if st.session_state.step11b1_tab not in tab_choices:
            st.session_state.step11b1_tab = tab_choices[0]
        tab_no = st.selectbox(
            "選擇 TAB",
            tab_choices,
            index=tab_choices.index(st.session_state.step11b1_tab),
            key="step11b1_tab_select",
            help="此格會製作 tab.png（96×74）"
        )
        st.session_state.step11b1_tab = tab_no

    st.info(
        f"目前設定：⭐ MAIN = {main_no}　｜　🏷️ TAB = {tab_no}　｜　"
        f"其他 6 張照正常 01～08 輸出"
    )

    # Server-side crop helper based on the current original 4x2 image.
    # The initial guide grid is standard 4x2; this is intentionally isolated
    # so the successful STEP 10C.8 browser editor is not changed.
    def _v11b1_crop_cell(sheet, idx):
        sw, sh = sheet.size
        col = idx % 4
        row = idx // 4
        x1 = round(col * sw / 4)
        x2 = round((col + 1) * sw / 4)
        y1 = round(row * sh / 2)
        y2 = round((row + 1) * sh / 2)

        crop = sheet.crop((x1, y1, x2, y2)).convert("RGBA")
        out = Image.new("RGBA", (370, 320), (255,255,255,0))
        scale = min(370 / crop.width, 320 / crop.height)
        nw = max(1, round(crop.width * scale))
        nh = max(1, round(crop.height * scale))
        crop = crop.resize((nw, nh), Image.Resampling.LANCZOS)
        out.alpha_composite(crop, ((370-nw)//2, (320-nh)//2))
        return out

    def _v11b1_special(im, size):
        out = Image.new("RGBA", size, (255,255,255,0))
        scale = min(size[0]/im.width, size[1]/im.height)
        nw=max(1,round(im.width*scale))
        nh=max(1,round(im.height*scale))
        im=im.resize((nw,nh),Image.Resampling.LANCZOS)
        out.alpha_composite(im,((size[0]-nw)//2,(size[1]-nh)//2))
        return out

    if st.button("📦 完成裁切＋製作 MAIN / TAB＋一鍵打包", type="primary", use_container_width=True):
        try:
            _sheet = Image.open(BytesIO(st.session_state.generated_4x2_bytes)).convert("RGBA")
            _zipbuf = BytesIO()

            with zipfile.ZipFile(_zipbuf, "w", zipfile.ZIP_DEFLATED) as _zip:
                cropped_images = {}
                for i in range(8):
                    im = _v11b1_crop_cell(_sheet, i)
                    cropped_images[i+1] = im
                    _b = BytesIO()
                    im.save(_b, "PNG", optimize=True)
                    _zip.writestr(f"{i+1:02d}.png", _b.getvalue())

                main_im = _v11b1_special(cropped_images[int(main_no)], (240,240))
                tab_im = _v11b1_special(cropped_images[int(tab_no)], (96,74))

                _mb=BytesIO(); _tb=BytesIO()
                main_im.save(_mb,"PNG",optimize=True,dpi=(72,72))
                tab_im.save(_tb,"PNG",optimize=True,dpi=(72,72))
                _zip.writestr("main.png",_mb.getvalue())
                _zip.writestr("tab.png",_tb.getvalue())

            _zipbuf.seek(0)
            st.success(
                f"🎉 完成！MAIN={main_no}、TAB={tab_no}，"
                "已將 01～08＋main.png＋tab.png 打包。"
            )
            st.download_button(
                "⬇️ 下載完整 LINE 套件 ZIP",
                data=_zipbuf.getvalue(),
                file_name="LINE_Sticker_01-08_MAIN_TAB.zip",
                mime="application/zip",
                use_container_width=True,
                key="step11b1_download"
            )
        except Exception as e:
            st.error(f"打包失敗：{e}")
    st.caption("V10 STEP 10C.6｜定位點裁切＋V8 邊界連通背景透明化；不改動原本定位點系統。")
st.divider()
st.caption("V10 STEP 10C.5｜定位點裁切版")
