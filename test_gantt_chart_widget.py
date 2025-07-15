import unittest
from unittest.mock import Mock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSize
from datetime import date, timedelta
from GanttChartWidget import GanttChartWidget
from engine import VibeTask

import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

class TestGanttChartWidget(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication([])

    def setUp(self):
        self.widget = GanttChartWidget()

    def test_initialization(self):
        self.assertEqual(self.widget.tasks, [])
        self.assertEqual(self.widget.tasks_to_display, [])
        self.assertEqual(self.widget.start_date, date.today())
        self.assertEqual(self.widget.end_date, date.today() + timedelta(days=60))

    def test_set_tasks(self):
        task1 = VibeTask(None, {"task_name": "Task 1", "project_name": "Project A", "date_start": date(2024, 1, 1), "date_end": date(2024, 1, 5)}, "")
        task2 = VibeTask(None, {"task_name": "Task 2", "project_name": "Project B", "date_start": date(2024, 1, 3), "date_end": date(2024, 1, 8)}, "")
        all_tasks = [task1, task2]
        filtered_tasks = [task1]
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        self.widget.set_tasks(all_tasks, filtered_tasks, start_date, end_date)

        self.assertEqual(self.widget.tasks, all_tasks)
        self.assertEqual(self.widget.tasks_to_display, filtered_tasks)
        self.assertEqual(self.widget.start_date, start_date)
        self.assertEqual(self.widget.end_date, end_date)

    def test_size_hint(self):
        task1 = VibeTask(None, {"task_name": "Task 1", "project_name": "Project A", "date_start": date(2024, 1, 1), "date_end": date(2024, 1, 5)}, "")
        self.widget.set_tasks([task1], [task1], date(2024, 1, 1), date(2024, 1, 31))

        size = self.widget.sizeHint()

        self.assertIsInstance(size, QSize)
        self.assertGreater(size.width(), 0)
        self.assertGreater(size.height(), 0)

    def test_get_pixels_per_day(self):
        self.widget.zoom_factor = 2.0
        self.assertEqual(self.widget.get_pixels_per_day(), 60.0)

    @classmethod
    def tearDownClass(cls):
        pass

if __name__ == '__main__':
    unittest.main()
