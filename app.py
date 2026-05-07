import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
import random
from streamlit_image_coordinates import streamlit_image_coordinates

# 1. 페이지 설정 및 성능 최적화 스타일
st.set_page_config(page_title="교육학 암기 마스터 PRO", layout="wide")

st.markdown("""
    <style>
    [data-testid="stSelectbox"] { max-width: 33%; }
    .stRadio > label { font-weight: bold; font-size: 1.1em; color: #1E88E5; }
    .stButton > button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
    /* 이미지 로딩 시 깜빡임 방지 */
    .stApp { transition: none !important; }
    </style>
""", unsafe_allow_html=True)

# --- [캐싱 엔진: 데이터 분석 및 이미지 바이트 보관] ---

@st.cache_data(show_spinner="페이지 분석 중...")
def get_cached_analysis(pdf_bytes, page_num):
    """PDF에서 파란색 단어 좌표를 정밀 추출하여 캐싱"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_num]
    word_list = page.get_text("words")
    raw_dict = page.get_text("dict")
    
    blue_word_boxes = []
    for b in raw_dict["blocks"]:
        if "lines" in b:
            for l in b["lines"]:
                for s in l["spans"]:
                    color = s["color"]
                    r, g, bl = (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
                    # 원본의 가장 정확했던 파란색 판정 로직 유지
                    if bl > r and bl > g and bl > 45:
                        blue_word_boxes.append(s["bbox"])

    final_blue_targets = []
    for w in word_list:
        w_box = w[:4]
        mid_x, mid_y = (w_box[0] + w_box[2]) / 2, (w_box[1] + w_box[3]) / 2
        for bb in blue_word_boxes:
            if bb[0]-2 <= mid_x <= bb[2]+2 and bb[1]-2 <= mid_y <= bb[3]+2:
                final_blue_targets.append(w_box)
                break
    return final_blue_targets

@st.cache_resource(show_spinner=False)
def get_cached_image_bytes(pdf_bytes, page_num, zoom=2.5):
    """이미지 생성 속도를 위해 줌 수치를 최적화(2.5)하여 바이트로 캐싱"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_num]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    return pix.tobytes("png")

# --- [메인 로직부] ---

st.title("❤ 여보 사랑해 화이팅 😍🤞")

uploaded_file = st.file_uploader("PDF 파일을 업로드하세요", type="pdf")

if uploaded_file is not None:
    # 세션 상태 관리
    if 'clicked_ids' not in st.session_state: st.session_state.clicked_ids = set()
    if 'random_seed' not in st.session_state: st.session_state.random_seed = 42

    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # 상단 페이지 선택 (너비 1/3)
    page_num = st.selectbox("페이지 선택", range(len(doc)), format_func=lambda x: f"{x+1} 페이지")
    
    with st.sidebar:
        st.header("🛠️ 설정")
        step = st.select_slider(
            "가리기 단계 설정",
            options=["1단계", "2단계", "3단계", "4단계", "5단계(전체)"],
            value="2단계"
        )
        st.write("---")
        if st.button("🎲 블랭크 위치 섞기"):
            st.session_state.random_seed = random.randint(1, 1000)
            st.session_state.clicked_ids = set()
            st.rerun()
        if st.button("🔄 리셋"):
            st.session_state.clicked_ids = set()
            st.rerun()

    # 1. 데이터 로드 (캐시 사용)
    final_blue_targets = get_cached_analysis(pdf_bytes, page_num)
    img_bytes = get_cached_image_bytes(pdf_bytes, page_num)
    # 바이트로부터 이미지 객체 생성 (매우 빠름)
    base_img = Image.open(io.BytesIO(img_bytes))

    # 2. 단계별 블랭크 타겟 확정
    display_targets = []
    random.seed(st.session_state.random_seed)
    
    if step == "5단계(전체)":
        display_targets = list(final_blue_targets)
    else:
        line_groups = {}
        for t in final_blue_targets:
            line_key = round(t[1] / 3) * 3
            if line_key not in line_groups: line_groups[line_key] = []
            line_groups[line_key].append(t)
        
        step_map = {"1단계": (1, 1), "2단계": (1, 2), "3단계": (2, 3), "4단계": (3, 5)}
        min_c, max_c = step_map[step]
        for l in sorted(line_groups.keys()):
            row = line_groups[l]
            count = min(len(row), random.randint(min_c, max_c))
            display_targets.extend(random.sample(row, count))

    # 3. 드로잉 최적화
    zoom = 2.5
    draw = ImageDraw.Draw(base_img)
    for box in display_targets:
        tid = f"{page_num}_{box}"
        if tid not in st.session_state.clicked_ids:
            db = [v * zoom for v in box]
            # 상하 여백 보정 (+2, -2) 유지
            draw.rectangle([db[0], db[1]+2, db[2], db[3]-2], fill="black")

    # 4. 인터랙티브 클릭 (전송 속도 향상 버전)
    res = streamlit_image_coordinates(
        base_img, 
        key=f"v_{st.session_state.random_seed}_{page_num}_{step}", 
        use_column_width=True
    )
    
    if res:
        # 클릭 좌표 보정
        rx, ry = base_img.size[0] / res["width"], base_img.size[1] / res["height"]
        cx, cy = res["x"] * rx, res["y"] * ry
        
        for box in display_targets:
            tid = f"{page_num}_{box}"
            db = [v * zoom for v in box]
            if db[0] <= cx <= db[2] and db[1] <= cy <= db[3]:
                if tid not in st.session_state.clicked_ids:
                    st.session_state.clicked_ids.add(tid)
                    st.rerun()

    st.write("---")
    if step == "5단계(전체)":
        st.success(f"🔥 모든 파란색 용어를 가렸습니다.")
    else:
        st.info(f"📍 {step} 진행 중")
else:
    st.info("파일을 업로드하면 고성능 학습 엔진이 가동됩니다.")
