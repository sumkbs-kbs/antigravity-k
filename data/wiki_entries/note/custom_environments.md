---
id: 8
category: note
tags: []
created: 2026-05-04T09:42:52.087624
---

# 사용자 정의 환경 구축 (Custom Environments)

tinker-nemogym은 NeMo-Gym을 기반으로 하고 있으므로, 자신만의 강화학습 환경(도메인 규칙 및 보상 함수)을 5분 안에 새롭게 정의하여 적용할 수 있습니다.

아래는 JSON 형식을 올바르게 반환하는지에 따라 보상을 주는 간단한 예제(`json_format`)의 구축 과정입니다.

## 1. 보상 함수 서버 만들기 (Resources Server)

`BaseRunRequest`와 `BaseVerifyResponse`를 상속받는 Pydantic 모델을 만들고, FastAPI 형태의 검증(Verify) 라우트를 구현합니다.

```python
# tinker_nemogym/environments/json_format/nemogym_server/app.py
from nemo_gym.base_resources_server import (
    BaseRunRequest, BaseVerifyRequest, BaseVerifyResponse, SimpleResourcesServer,
)
import json

class JSONRunRequest(BaseRunRequest):
    required_keys: list[str] | None = None
    expected_count: int | None = None

class JSONVerifyRequest(JSONRunRequest, BaseVerifyRequest): pass

server = SimpleResourcesServer[JSONVerifyRequest, BaseVerifyResponse](...)

@server.app.post("/verify")
async def verify(req: JSONVerifyRequest) -> BaseVerifyResponse:
    # 텍스트 추출 및 정제
    text = _extract_text(req.response)
    try:
        parsed = json.loads(_strip_fence(text))
    except json.JSONDecodeError:
        return BaseVerifyResponse(reward=0.0)           # 파싱 실패 → 보상 0

    if _keys_match(parsed, req.required_keys, req.expected_count):
        return BaseVerifyResponse(reward=1.0)           # 완벽 일치 → 보상 1

    return BaseVerifyResponse(reward=0.5)               # 형태는 맞으나 키 불일치 → 보상 0.5
```

## 2. 데이터셋 구성 (JSONL)

환경 검증 로직에 맞추어 모델에게 제공할 초기 프롬프트 데이터셋을 생성합니다.
파라미터들은 위에서 정의한 `JSONRunRequest` 스키마와 동일하게 맵핑되어야 합니다.

```json
{"responses_create_params": {"input": [{"role":"user","content":"List 3 fruits as a JSON array with keys \"name\" and \"color\"."}]}, "required_keys": ["name","color"], "expected_count": 3}
{"responses_create_params": {"input": [{"role":"user","content":"Give 2 planets with keys \"name\" and \"distance_au\"."}]}, "required_keys": ["name","distance_au"], "expected_count": 2}
```

## 3. 트레이너 설정 파일 구성 (YAML)

마지막으로, 훈련할 모델과 방금 만든 환경 리소스를 이어주는 `config.yaml` 훈련 설정 파일을 구성합니다.

```yaml
# configs/smoke_json_format_nemotron.yaml
schema_version: 1
tinker:
  base_model: nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16   # 훈련할 베이스 모델
  lora_rank: 32
  learning_rate: 5.0e-4
  loss_fn: importance_sampling
  wandb_project: tinker-nemogym-json-format                # 로깅
  checkpoint_dir: ./checkpoints/smoke_json_format

model_server: { host: 127.0.0.1, port: 8001 }              # FastAPI Shim 서버 포트
nemogym:
  agent_url: null                                          # HeadServer를 통해 런타임에 자동 검색됨
  head_url: http://127.0.0.1:11000                         # NeMo-Gym 헤드 서버
  dataset_jsonl: tinker_nemogym/environments/json_format/dataset.jsonl
  group_size: 8                                            # GRPO 그룹 사이즈

training: { n_steps: 5, batch_size: 2, max_tokens: 512, temperature: 1.0 }
```

## 4. 실행하기

스크립트를 구성하고 훈련을 론칭합니다. 스크립트 실행 전 `TINKER_API_KEY` 환경 변수와 `nemo-gym` 패키지가 의존성으로 구동 중인지 확인하세요.

```bash
export TINKER_API_KEY=tml-...
bash scripts/smoke_json_format.sh
```
