import os
import sys
import time
from pathlib import Path
from antigravity_k.agents.skills_registry import SkillsRegistry

def log_agent_message(agent_name: str, message: str, color_code: str = "\033[0m"):
    print(f"{color_code}[{agent_name}]\033[0m: {message}")
    time.sleep(1)

def run_debate_demo():
    print("=" * 60)
    print("Antigravity-K Agentic Framework Debate & Autopilot Demo")
    print("=" * 60)
    
    # 1. 스킬 로드
    registry = SkillsRegistry()
    profiles = registry.list_profiles()
    print(f"\n[SYSTEM] 로드된 에이전트 스킬: {', '.join(profiles)}")
    print("[SYSTEM] 목표 태스크: '간단한 보안이 강화된 파일 업로드 API 개발'")
    print("-" * 60)

    # 2. 토론 과정 모의
    log_agent_message("PM", "목표를 확인했습니다. BACKEND 에이전트는 파일 업로드 API 초기 계획을 제안해 주세요.", "\033[94m")
    
    plan_draft = """
# File Upload API Plan
1. FastAPI 사용
2. /upload 엔드포인트 생성
3. 파일을 특정 디렉토리에 저장
    """
    log_agent_message("BACKEND", f"초기 계획안입니다:\n{plan_draft}", "\033[92m")
    
    log_agent_message("SECURITY_REVIEWER", "계획을 검토 중입니다...", "\033[93m")
    log_agent_message("SECURITY_REVIEWER", "거부(REJECT). 제안된 계획에는 파일 확장자 검증, 최대 크기 제한, 악성 코드 스캔 로직이 빠져 있습니다. 보안 취약점(Path Traversal 등)이 발생할 수 있습니다.", "\033[91m")
    
    log_agent_message("ARCHITECTURE_CRITIC", "동의합니다. 확장성 측면에서도 로컬 디스크 저장은 위험합니다. 추후 S3나 클라우드 스토리지 인터페이스로 추상화해야 합니다.", "\033[93m")
    
    log_agent_message("BACKEND", "피드백을 수용하여 계획을 수정하겠습니다. 파일 크기 제한, 확장자 화이트리스트, 그리고 스토리지 인터페이스를 추가했습니다.", "\033[92m")
    
    log_agent_message("PM", "수정된 계획이 안전해보입니다. 이제 체크리스트(Checklist) 아티팩트를 자동 생성하고 코딩 작업에 돌입합니다.", "\033[94m")
    
    # 3. 아티팩트 자동 생성 및 git 커밋 모의
    print("\n[SYSTEM] Autopilot 모드 동작 중: 아티팩트 작성 및 Git Checkpoint 생성...")
    
    artifacts_dir = Path("demo_artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    plan_file = artifacts_dir / "upload_api_plan.md"
    plan_file.write_text("# Secure Upload API Plan\n- [ ] Extension whitelist\n- [ ] Size limit\n- [ ] Abstract Storage Interface", encoding="utf-8")
    
    print(f"[SYSTEM] '{plan_file}' 파일이 생성되었습니다.")
    
    # Mock Git Commit
    os.system('git add demo_artifacts/upload_api_plan.md')
    os.system('git commit -m "docs: auto-generated secure file upload API plan via debate"')
    print("[SYSTEM] Git Checkpoint 생성이 완료되었습니다.")
    print("=" * 60)
    print("데모 완료")

if __name__ == "__main__":
    run_debate_demo()
