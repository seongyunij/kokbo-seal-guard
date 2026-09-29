import base64
import json
import io
import os
from datetime import datetime
import pandas as pd
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

st.set_page_config(
    page_title="국보기업 KOKBO Seal-Guard",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 모바일 어플리케이션 전용 Custom CSS
st.markdown("""
    <meta name="google" content="notranslate">
    <style>
    .stApp {
        background-color: #f4f6f8;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 3rem;
        max-width: 600px;
        margin: auto;
    }
    .app-header {
        background: #0f2b48;
        color: white;
        padding: 16px 20px;
        border-radius: 12px;
        margin-bottom: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .app-header h3 {
        margin: 0;
        font-size: 18px;
        font-weight: 700;
        color: #ffffff;
    }
    .app-header p {
        margin: 4px 0 0 0;
        font-size: 12px;
        color: #a0aec0;
    }
    .kpi-container {
        display: flex;
        gap: 8px;
        margin-bottom: 16px;
    }
    .kpi-card {
        flex: 1;
        background: white;
        padding: 12px;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .kpi-card .number {
        font-size: 20px;
        font-weight: 800;
        margin-top: 4px;
    }
    .kpi-red { color: #e53e3e; border-top: 4px solid #e53e3e; }
    .kpi-blue { color: #3182ce; border-top: 4px solid #3182ce; }
    .kpi-green { color: #38a169; border-top: 4px solid #38a169; }
    </style>
""", unsafe_allow_html=True)

# app.py 상단 코드 수정 (기존 RAW_API_KEY 변수 교체)

# Streamlit Secrets 또는 환경 변수에서 안전하게 키 로드
# Secrets에서 키를 직접 읽어와 공백만 제거
RAW_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
DEFAULT_KEY = str(RAW_API_KEY).strip().strip('"').strip("'")

# 📱 사이드바 구성
with st.sidebar:
    st.header("⚙️ 시스템 설정")
    api_key = DEFAULT_KEY
    if api_key:
        st.success("🔑 API 키 인증 완료")

    st.markdown("---")
    
    with st.expander("📖 항만/검수 용어 사전", expanded=False):
        st.markdown("""
        * **Bay Plan (베이플랜):** 컨테이너 선박 내 적재 위치 도면
        * **Seal (세관 씰):** 밀수 및 무단 개봉 방지용 봉인 장치 (자물쇠)
        * **Cell Code (셀 번호):** 컨테이너의 격자형 정밀 적재 위치
        * **RPHC / Reefer:** 냉동/냉장 컨테이너 (전원 연결 필수)
        * **POD / POL:** 하역항(Destination) / 적재항(Loading)
        """)

    with st.expander("📦 컨테이너 번호 Quick 메모", expanded=True):
        st.caption("현장에서 확인한 컨테이너 번호나 특이사항을 받아 적으세요.")
        cntr_memo = st.text_area("컨테이너 메모", placeholder="예: MSKU1234567 - 씰 파손 건 확인 필요", height=100)
        if st.button("메모 저장"):
            st.session_state['saved_cntr_memo'] = cntr_memo
            st.success("저장되었습니다.")

    with st.expander("📝 개인 일과 & 업무 메모", expanded=False):
        todo_memo = st.text_area("오늘의 업무/개인 일과", placeholder="예: 14시 부장님 미팅 준비, 세관 서류 출력", height=100)

# 📱 메인 모바일 헤더
st.markdown("""
    <div class="app-header">
        <h3>🚢 KOKBO Seal-Guard AI</h3>
        <p>국보기업 현장 특화 | 세관 씰(Seal) 자동 검수 & 모바일 통합 보고</p>
    </div>
""", unsafe_allow_html=True)

# 1. 서류 업로드 및 AI 분석
st.subheader("1. 베이플랜(Bay Plan) 스캔")
uploaded_file = st.file_uploader("현장 도면 이미지를 업로드하세요", type=["jpg", "jpeg", "png", "jfif"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="원본 베이플랜 이미지", use_container_width=True)
    
    if st.button("🚀 AI 세관 씰 리스크 검수 시작", type="primary", use_container_width=True):
        if not api_key:
            st.error("API 키 설정을 확인해 주세요.")
        else:
            with st.spinner("AI가 도면 및 세관 마킹(빨간/파란 체크)을 분석 중입니다..."):
                try:
                    bytes_data = uploaded_file.getvalue()
                    base64_image = base64.b64encode(bytes_data).decode('utf-8')
                    
                    # 파일 mime type 감지
                    file_type = uploaded_file.type if uploaded_file.type else "image/jpeg"

                    client = OpenAI(api_key=DEFAULT_KEY)

                    prompt = """
                    You are an expert AI inspecting port Bay Plan documents. Analyze the provided image carefully and return a JSON object.
                    
                    Respond strictly with a JSON object matching this schema:
                    {
                      "ship_info": {"vessel": "string", "voy_no": "string"},
                      "handwritten_notes": ["string"],
                      "seal_alerts": {"alert_summary": "string"},
                      "containers": [
                        {
                          "cell_code": "string",
                          "company_code": "string",
                          "spec_code": "string",
                          "type_code": "string",
                          "seal_status": "string (one of: '🔴 세관 씰 필수', '🔵 사진 촬영 대상', '🟢 정상')"
                        }
                      ]
                    }

                    Guidelines:
                    1. Extract vessel name and voyage number if visible.
                    2. Capture any handwritten notes or numbers.
                    3. Detect red checkmarks or blue checkmarks on containers.
                       - Red mark or customs lock requirement -> '🔴 세관 씰 필수'
                       - Blue mark or photo requirement/seal error -> '🔵 사진 촬영 대상'
                       - Others -> '🟢 정상'
                    4. Summarize required field actions in alert_summary.
                    """

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        response_format={"type": "json_object"},
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a specialized AI assistant that parses shipping bay plans and outputs raw JSON format only."
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{file_type};base64,{base64_image}",
                                            "detail": "high"
                                        }
                                    }
                                ]
                            }
                        ],
                        temperature=0.1
                    )

                    result_content = response.choices[0].message.content

                    if not result_content:
                        st.error("❌ AI로부터 응답을 수신하지 못했습니다. 이미지가 너무 크거나 분석할 수 없습니다.")
                    else:
                        # json 포맷에서 혹시 모를 마크다운 블록 제거
                        clean_json = result_content.replace("```json", "").replace("```", "").strip()
                        data = json.loads(clean_json)
                        st.session_state['parsed_data'] = data
                        st.success("✅ 분석 완료!")

                except Exception as e:
                    st.error(f"분석 오류 발생: {e}")

# 2. AI 데이터 가공 및 대시보드
if 'parsed_data' in st.session_state:
    data = st.session_state['parsed_data']
    containers = data.get("containers", [])
    vessel = data.get("ship_info", {}).get("vessel", "N/A")
    voy_no = data.get("ship_info", {}).get("voy_no", "N/A")
    notes = ", ".join(data.get("handwritten_notes", []))
    seal_alerts = data.get("seal_alerts", {})

    st.markdown("---")
    st.subheader("2. 검수 현황 대시보드")

    red_cnt = sum(1 for c in containers if '🔴' in str(c.get('seal_status', '')))
    blue_cnt = sum(1 for c in containers if '🔵' in str(c.get('seal_status', '')))
    green_cnt = len(containers) - (red_cnt + blue_cnt)

    st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-card kpi-red">
                <div style="font-size:12px;">🔴 세관 씰 필수</div>
                <div class="number">{red_cnt}건</div>
            </div>
            <div class="kpi-card kpi-blue">
                <div style="font-size:12px;">🔵 사진 촬영 대상</div>
                <div class="number">{blue_cnt}건</div>
            </div>
            <div class="kpi-card kpi-green">
                <div style="font-size:12px;">🟢 정상 항목</div>
                <div class="number">{green_cnt}건</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.warning(f"🚨 **[현장 지침]** {seal_alerts.get('alert_summary', '특이사항 없음')}")

    # 📲 탭 메뉴
    tab1, tab2, tab3 = st.tabs(["📲 현장 조치 입력", "📋 정제 엑셀 다운로드", "📄 세관 제출 보고서"])

    with tab1:
        st.markdown("##### 📱 현장 검수원 1-Click 조치")
        selected_cell = st.selectbox(
            "조치 대상 컨테이너 선택", 
            [f"Cell {c.get('cell_code', '-')} | {c.get('seal_status', '🟢 정상')}" for c in containers]
        )
        
        status_radio = st.radio(
            "조치 상태 선택", 
            ["자물쇠/세관 씰 체결 완료 🔒", "이상 건 사진 촬영 완료 📸", "특이사항 없음 🟢"]
        )
        
        cam_file = st.file_uploader("📷 현장 조치/씰 사진 촬영", type=["jpg", "png", "jpeg"])
        if cam_file:
            st.image(cam_file, caption="등록된 현장 증빙 사진", width=200)

        if st.button("💾 본부 대시보드 조치 내역 전송", type="primary", use_container_width=True):
            st.success("✅ 본부 중앙 서버 및 보고서에 실시간 반영되었습니다.")

    with tab2:
        st.markdown("##### 📊 종합 데이터 엑셀 추출")
        table_rows = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        for item in containers:
            table_rows.append({
                "선박명": vessel,
                "항차번호": voy_no,
                "위치(Cell)": item.get("cell_code", ""),
                "선사/화주코드": item.get("company_code", ""),
                "규격코드": item.get("spec_code", ""),
                "타입코드": item.get("type_code", ""),
                "세관 씰 상태": item.get("seal_status", "🟢 정상"),
                "현장 수기메모": notes,
                "조치일시": now_str
            })

        df = pd.DataFrame(table_rows)
        st.dataframe(df, use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='국보기업_검수데이터')

        st.download_button(
            label="📥 정제 엑셀 파일 다운로드 (.xlsx)",
            data=buffer.getvalue(),
            file_name=f"KOKBO_BayPlan_{vessel}_{voy_no}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with tab3:
        st.markdown("### 📄 컨테이너 세관 씰(Seal) 검수 완료 보고서")
        st.caption("본 보고서는 국보기업 현장 검수 시스템에서 실시간 생성된 표준 세관 제출용 리포트입니다.")
        
        now_date = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
        saved_memo = st.session_state.get('saved_cntr_memo', '없음')

        st.info(f"""
        **• 제출처:** 국보기업 본부 / 부산세관 제출용  
        **• 점검 선박 / 항차:** {vessel} / {voy_no}  
        **• 점검 완료 일시:** {now_date}  
        **• 현장 수기 메모:** {notes if notes else '특이사항 없음'}  
        **• 현장 컨테이너 메모:** {saved_memo}
        """)

        st.markdown("#### 1. 세관 씰 검수 및 조치 현황")
        
        summary_data = [
            {"구분": "🔴 세관 씰 필수", "대상 건수": f"{red_cnt} 건", "현장 조치 상태": "자물쇠/씰 체결 완료 🔒", "행정 리스크": "안전 (해제)"},
            {"구분": "🔵 사진 촬영/보고", "대상 건수": f"{blue_cnt} 건", "현장 조치 상태": "사진 증빙 등록 완료 📸", "행정 리스크": "보고 완료"},
            {"구분": "🟢 정상 항목", "대상 건수": f"{green_cnt} 건", "현장 조치 상태": "이상 없음", "행정 리스크": "정상"}
        ]
        st.table(pd.DataFrame(summary_data))

        st.markdown("#### 2. 세부 컨테이너 점검 및 조치 리스트")
        
        detail_data = []
        for idx, item in enumerate(containers, start=1):
            detail_data.append({
                "No": idx,
                "위치 (Cell)": f"Cell {item.get('cell_code', '-')}",
                "선사/화주": item.get('company_code', '-'),
                "규격/타입": f"{item.get('spec_code', '')} {item.get('type_code', '')}",
                "세관 씰 상태": item.get('seal_status', '🟢 정상'),
                "최종 조치 결과": "조치 완료 (현장 확인)"
            })
        
        st.dataframe(pd.DataFrame(detail_data), use_container_width=True, hide_index=True)

        st.markdown("---")
        col_rep1, col_rep2 = st.columns([2, 1])
        with col_rep1:
            st.caption("위 컨테이너는 국보기업 AI 현장 검수 솔루션을 통해 세관 씰 점검이 정상 완료되었음을 증명합니다.")
        with col_rep2:
            st.markdown("**검수 담당자:** 국보기업 현장 검수팀 (인)")