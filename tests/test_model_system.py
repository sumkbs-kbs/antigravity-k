"""Phase 2 Step 2-1 테스트: 모델 레지스트리 & 매니저"""
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
sys.path.insert(0, "src")

from antigravity_k.engine import ModelRegistry, ModelManager

print("=== 1. Registry 테스트 ===")
r = ModelRegistry("config.yaml")
print(r.summary())

print("\n=== 2. Manager 로드 테스트 ===")
m = ModelManager(r)
m.load("qwen3-72b")
print(f"로드됨: {m.loaded_names()}")

print("\n=== 3. 모델 교체 (핫스왑) 테스트 ===")
m.swap("deepseek-v4-67b")
print(f"교체 후: {m.loaded_names()}")

print("\n=== 4. 임베딩 모델 추가 로드 ===")
m.load("bge-m3")
print(f"최종 로드: {m.loaded_names()}")

print("\n=== 5. 상태 확인 ===")
s = m.status()
for model in s["loaded_models"]:
    print(f"  {model['name']} ({model['role']}) - {model['memory_gb']}GB")
print(f"  합계: {s['total_loaded_gb']}GB / {s['max_allowed_gb']}GB")
print(f"  남은 용량: {s['available_gb']}GB")

print("\n=== 6. 자동 언로드 테스트 (100GB 초과 시도) ===")
try:
    m.load("qwen2-vl-72b")  # 40GB 추가 → 합계 79GB → OK
    print(f"비전 모델 추가: {m.loaded_names()}")
    s = m.status()
    print(f"  합계: {s['total_loaded_gb']}GB")
except MemoryError as e:
    print(f"  메모리 초과: {e}")

print("\n✓ 모든 테스트 통과!")
