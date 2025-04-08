import sys
import os

# 프로젝트 루트 디렉토리를 패스에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# src 디렉토리에 있는 markitdown 패키지에서 MarkItDown 클래스 임포트
from src.markitdown import MarkItDown

# MarkItDown 인스턴스 생성
md = MarkItDown()

# PDF 파일 변환 - 간단하게 경로 지정
sample_path = os.path.join(os.path.dirname(__file__), "../samples/sample.pdf")
result = md.convert(sample_path)

# 결과 출력
print(result.text_content)