import os
from pathlib import Path
from antigravity_k.agents.skills_registry import SkillsRegistry

def test_skills_registry_initialization(tmp_path):
    skills_dir = tmp_path / ".agent" / "skills"
    registry = SkillsRegistry(skills_dir=str(skills_dir))
    
    profiles = registry.list_profiles()
    assert len(profiles) >= 5
    assert "PM" in profiles
    assert "BACKEND" in profiles
    assert "FRONTEND" in profiles

def test_skills_registry_dynamic_load(tmp_path):
    skills_dir = tmp_path / ".agent" / "skills"
    
    # 미리 임의의 스킬 파일 작성
    test_skill_dir = skills_dir / "testskill"
    test_skill_dir.mkdir(parents=True)
    (test_skill_dir / "SKILL.md").write_text("Test Skill Description")

    registry = SkillsRegistry(skills_dir=str(skills_dir))
    profiles = registry.list_profiles()
    
    assert "TESTSKILL" in profiles
    profile = registry.get_profile("TESTSKILL")
    assert profile.name == "TESTSKILL"
    assert profile.system_prompt == "Test Skill Description"

def test_skills_registry_save_skill(tmp_path):
    skills_dir = tmp_path / ".agent" / "skills"
    registry = SkillsRegistry(skills_dir=str(skills_dir))
    
    registry.save_skill("new_skill", "This is a dynamically created skill")
    
    profiles = registry.list_profiles()
    assert "NEW_SKILL" in profiles
    
    profile = registry.get_profile("NEW_SKILL")
    assert profile.system_prompt == "This is a dynamically created skill"

def test_skills_registry_get_invalid_profile(tmp_path):
    skills_dir = tmp_path / ".agent" / "skills"
    registry = SkillsRegistry(skills_dir=str(skills_dir))
    try:
        registry.get_profile("NON_EXISTENT")
        assert False, "Should raise ValueError"
    except ValueError:
        pass
