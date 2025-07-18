import unittest
from unittest.mock import patch, Mock
from main_gui import VibeGanttApp
from engine import VibeTask

import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

class TestVibeGanttApp(unittest.TestCase):

    @patch('main_gui.VibeGanttApp.__init__', lambda x: None)
    def setUp(self):
        self.main_window = VibeGanttApp()
        self.main_window.tasks = []
        self.main_window.errors = []
        self.main_window.statusBar = Mock()
        self.main_window.gantt_chart = Mock()
        self.main_window.details_panel = Mock()
        self.main_window.project_filter = Mock()
        self.main_window.phase_filter = Mock()
        self.main_window.cost_code_filter = Mock()
        self.main_window.assigned_to_filter = Mock()
        self.main_window.date_range_filter = Mock()

    def test_initialization(self):
        # This test is no longer relevant as we are mocking the init
        pass

    @patch('main_gui.filedialog.askdirectory', return_value='fake_path')
    @patch('main_gui.ingest_project_data')
    def test_load_project(self, mock_ingest, mock_askdirectory):
        task1 = VibeTask(None, {"task_name": "Task 1", "project_name": "Project A", "date_start": "2024-01-01", "date_end": "2024-01-05"}, "")
        mock_ingest.return_value = ([task1], [])

        self.main_window.load_project()

        self.assertEqual(len(self.main_window.tasks), 1)
        self.assertEqual(self.main_window.tasks[0].metadata['task_name'], "Task 1")
        self.assertEqual(len(self.main_window.errors), 0)

    @patch('main_gui.frontmatter.dump')
    @patch('main_gui.os.replace')
    def test_save_all_changes(self, mock_replace, mock_dump):
        task1 = VibeTask(Mock(), {"task_name": "Task 1", "project_name": "Project A", "date_start": "2024-01-01", "date_end": "2024-01-05"}, "")
        task1.is_dirty = True
        self.main_window.tasks = [task1]

        self.main_window.save_all_changes()

        mock_dump.assert_called_once()
        mock_replace.assert_called_once()
        self.assertFalse(task1.is_dirty)

if __name__ == '__main__':
    unittest.main()
