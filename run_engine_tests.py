from test_engine import TestEngine

test = TestEngine()
test.test_vibe_task_creation()
test.test_validate_task_data_success()
test.test_validate_task_data_missing_fields()
test.test_validate_task_data_impossible_timeline()
print("Engine tests passed!")
