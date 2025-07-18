import unittest
import sys
from pathlib import Path
from unittest.mock import patch, Mock
from PyQt6.QtWidgets import QApplication
from main_gui import VibeGanttApp
from engine import VibeTask

import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

class TestVibeGanttApp(unittest.TestCase):

    def setUp(self):
        with patch('main_gui.VibeGanttApp.load_project'):
            self.app = QApplication(sys.argv)
            self.main_window = VibeGanttApp()

    def tearDown(self):
        self.main_window.close()

    @patch('main_gui.Tk')
    @patch('main_gui.filedialog.askdirectory', return_value='fake_path')
    @patch('main_gui.ingest_project_data')
    def test_load_project(self, mock_ingest, mock_askdirectory, mock_tk):
        task1 = VibeTask(Mock(), {"task_name": "Task 1", "project_name": "Project A", "date_start": "2024-01-01", "date_end": "2024-01-05"}, "")
        mock_ingest.return_value = ([task1], [])

        self.main_window.load_project()

        self.assertEqual(len(self.main_window.tasks), 1)
        self.assertEqual(self.main_window.tasks[0].metadata['task_name'], "Task 1")
        self.assertEqual(len(self.main_window.errors), 0)

    @patch('main_gui.frontmatter.dump')
    @patch('main_gui.os.replace')
    @patch('main_gui.QMessageBox')
    def test_save_all_changes(self, mock_messagebox, mock_replace, mock_dump):
        task1 = VibeTask(Mock(spec=Path), {"task_name": "Task 1", "project_name": "Project A", "date_start": "2024-01-01", "date_end": "2024-01-05"}, "")
        task1.file_path.with_suffix.return_value = "fake_path.md.tmp"
        task1.is_dirty = True
        self.main_window.tasks = [task1]
        self.main_window.details_panel = Mock()
        self.main_window.details_panel.current_task = task1

        self.main_window.save_all_changes()

        mock_dump.assert_called_once()
        mock_replace.assert_called_once()
        self.assertFalse(task1.is_dirty)

if __name__ == '__main__':
    unittest.main()
