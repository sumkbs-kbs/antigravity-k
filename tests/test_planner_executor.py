from antigravity_k.engine.cognitive_loop import PlannerExecutor


class TestDecomposeTask:
    def test_decomposes_numbered_multi_part_task_into_separate_steps(self):
        planner = PlannerExecutor()

        task = (
            "다음 세 가지를 해줘.\n"
            "1. README.md 파일을 읽어줘.\n"
            "2. config.yaml의 model 값을 보여줘.\n"
            "3. 테스트를 실행해줘."
        )

        plan = planner.decompose_task(task)

        assert len(plan.steps) == 3
        assert plan.steps[0].step_id == 1
        assert "README" in plan.steps[0].description
        assert plan.steps[1].step_id == 2
        assert "config" in plan.steps[1].description.lower()
        assert plan.steps[2].step_id == 3
        assert "테스트" in plan.steps[2].description or "test" in plan.steps[2].description.lower()

    def test_single_part_task_stays_one_step(self):
        planner = PlannerExecutor()

        plan = planner.decompose_task("피보나치 함수를 작성해줘.")

        assert len(plan.steps) == 1
        assert plan.steps[0].step_id == 1

    def test_bullet_list_task_decomposes_into_steps(self):
        planner = PlannerExecutor()

        task = "작업 목록:\n" "- 첫 번째 작업\n" "- 두 번째 작업\n" "- 세 번째 작업"

        plan = planner.decompose_task(task)

        assert len(plan.steps) == 3

    def test_execution_trace_records_each_step_outcome(self):
        import asyncio

        planner = PlannerExecutor()
        plan = planner.decompose_task("1. 첫 단계\n2. 두 번째 단계")

        async def fake_executor(step):
            return f"done:{step.step_id}"

        result = asyncio.run(planner.execute_plan(plan, fake_executor))

        assert result["success"] is True
        assert len(result["results"]) == 2
        assert planner.get_execution_trace()
