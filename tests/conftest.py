"""Antigravity-K 테스트 설정 파일.
모든 테스트에서 src/ 디렉토리를 sys.path에 추가합니다.
"""

import os
import sys

# src/ 디렉토리를 sys.path에 추가 (antigravity_k 패키지 임포트 가능)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
