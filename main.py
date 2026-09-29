import base64
import json
import os
import pandas as pd
from openai import OpenAI

# 1. API 클라이언트 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY)

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def process_bay_plan_strict(image_path):
    if not os.path.exists(image_path):
        print(f"❌ 에러: {image_path} 파일을 찾을 수 없습니다.")
        return

    print("🔍 [1/3] 서류 이미지 정밀 분석 및 컬럼 분리 중...")
    base64_image = encode_image(image_path)

    # 문자열 분리를 완벽히 강제하는 프롬프트
    prompt = """
    이 이미지는 부산항 항만 현장에서 사용되는 컨테이너 배치 도면(Bay Plan)입니다.
    이미지 내의 상단 헤더, 표 안의 인쇄 텍스트, 손글씨 메모를 정밀 분석하세요.

    [주의] 각 그리드 셀에 적힌 텍스트(예: INC/INC*PUS DYS E 4.5 RPHC)를 절대로 한 텍스트로 묶지 말고, 반드시 공백과 구분자를 기준으로 3개의 개별 필드로 엄격히 분리하세요.

    추출 항목:
    1. ship_info: vessel(선박명), voy_no(항차번호)
    2. handwritten_notes: 손글씨 한글 메모 및 숫자의 배열 (예: ["FR 4개 연결", "4482", "5006"])
    3. containers: 
       - cell_code: 위치 번호 (예: "06", "04", "02")
       - company_code: 선사/화주 코드 (예: "INC/INC*PUS", "YNT/YNT*PUS")
       - spec_code: 규격 코드 (예: "DYS E 4.5", "DYS E 2.1")
       - type_code: 타입 코드 (예: "RPHC", "DC20")

    응답은 반드시 아래 JSON 구조로만 출력하세요:
    {
      "ship_info": {"vessel": "PEGASUS PETA", "voy_no": "2512W"},
      "handwritten_notes": ["FR 4개 연결", "4482"],
      "containers": [
        {
          "cell_code": "06",
          "company_code": "INC/INC*PUS",
          "spec_code": "DYS E 4.5",
          "type_code": "RPHC"
        }
      ]
    }
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            temperature=0.0
        )

        data = json.loads(response.choices[0].message.content)
        print("✅ [2/3] AI 분석 완료!")

        # 2. 데이터프레임 구조화 (명시적 컬럼 구성)
        containers = data.get("containers", [])
        vessel = data.get("ship_info", {}).get("vessel", "")
        voy_no = data.get("ship_info", {}).get("voy_no", "")
        notes = ", ".join(data.get("handwritten_notes", []))

        table_rows = []
        for item in containers:
            table_rows.append({
                "선박명": vessel,
                "항차번호": voy_no,
                "위치(Cell)": item.get("cell_code", ""),
                "선사/화주코드": item.get("company_code", ""),
                "규격코드": item.get("spec_code", ""),
                "타입코드": item.get("type_code", ""),
                "현장 수기메모": notes
            })

        df = pd.DataFrame(table_rows)

        # 3. 진짜 엑셀(.xlsx) 저장
        excel_filename = "bay_plan_perfect.xlsx"
        df.to_excel(excel_filename, index=False)
        print(f"\n🎉 [3/3] 완벽 분리 엑셀 저장 완료: {excel_filename}")
        print("\n[미리보기]")
        print(df.head())

    except Exception as e:
        print(f"❌ 에러 발생: {e}")

if __name__ == "__main__":
    IMAGE_FILE = "bay_plan.jpg.jfif"  # 또는 본인의 이미지 파일명
    process_bay_plan_strict(IMAGE_FILE)