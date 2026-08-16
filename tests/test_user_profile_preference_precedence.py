from antigravity_k.engine.user_model import UserIntentModeler


def test_explicit_style_preference_overrides_inferred_profile_for_current_turn(tmp_path) -> None:
    # Given: historical length heuristics strongly favor detailed responses.
    modeler = UserIntentModeler(project_root=str(tmp_path))
    for _ in range(4):
        modeler.observe("상세한 배경이 있는 " + ("긴 요청 " * 60), "analysis")

    # When: the user explicitly changes the response style.
    modeler.observe("이제부터 답변은 간결하게 해줘", "simple_chat")
    context = modeler.build_context()

    # Then: explicit intent replaces rather than coexists with the inferred style.
    assert "소통 스타일: 간결한 응답 선호" in context
    assert "상세한 응답 선호" not in context


def test_explicit_language_preference_overrides_character_count_inference(tmp_path) -> None:
    # Given: historical character counts strongly favor Korean.
    modeler = UserIntentModeler(project_root=str(tmp_path))
    for _ in range(4):
        modeler.observe("한국어 문장을 계속 사용합니다", "simple_chat")

    # When: an English request explicitly selects English for future responses.
    modeler.observe("From now on always respond in English", "simple_chat")
    context = modeler.build_context()

    # Then: the explicit preference has the only injected language value.
    assert "선호 언어: 영어" in context
    assert "선호 언어: 한국어\n" not in context
