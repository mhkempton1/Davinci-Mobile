import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import date, timedelta

# Mock tkinter before it's imported by engine
import sys
sys.modules['tkinter'] = MagicMock()
sys.modules['tkinter.filedialog'] = MagicMock()

from engine import VibeTask, validate_task_data

class TestEngine(unittest.TestCase):

    def test_vibe_task_creation(self):
        task = VibeTask(Path("test.md"), {"task_name": "Test Task"}, "Test Content")
        self.assertEqual(task.metadata["task_name"], "Test Task")
        self.assertEqual(task.content, "Test Content")
        self.assertFalse(task.is_dirty)

    def test_validate_task_data_success(self):
        metadata = {
            "task_name": "Test Task",
            "date_start": "2024-01-01",
            "date_end": "2024-01-02"
        }
        issues = validate_task_data(metadata)
        self.assertIsNone(issues)
        self.assertEqual(metadata["date_start"], date(2024, 1, 1))
        self.assertEqual(metadata["date_end"], date(2024, 1, 2))

    def test_validate_task_data_missing_fields(self):
        metadata = {}
        issues = validate_task_data(metadata)
        self.assertIn("missing_task_name", issues)
        self.assertIn("missing_date_start", issues)
        self.assertIn("missing_date_end", issues)

    def test_validate_task_data_impossible_timeline(self):
        metadata = {
            "task_name": "Test Task",
            "date_start": "2024-01-02",
            "date_end": "2024-01-01"
        }
        issues = validate_task_data(metadata)
        self.assertIn("impossible_timeline", issues)
        self.assertEqual(metadata["date_end"], metadata["date_start"])


if __name__ == '__main__':
    unittest.main()
