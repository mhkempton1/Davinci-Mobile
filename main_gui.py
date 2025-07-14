import sys
import hashlib
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QMenuBar,
                             QStatusBar, QWidget, QVBoxLayout, QListWidget,
                             QSplitter, QPushButton, QAbstractItemView, QFormLayout,
                             QLineEdit, QTextEdit, QComboBox)
from PyQt6.QtGui import QAction, QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QRectF, QDate, pyqtSignal
from datetime import date, timedelta, datetime

from engine import ingest_project_data, VibeTask, validate_task_data
from GanttChartWidget import GanttChartWidget
import frontmatter

DARK_THEME_QSS = """
    QWidget {
        background-color: #2b2b2b;
        color: #d3d3d3;
        font-size: 10pt;
    }
    QMainWindow, QMenuBar, QMenu {
        background-color: #3c3c3c;
    }
    QMenuBar::item:selected, QMenu::item:selected {
        background-color: #5a5a5a;
    }
    QPushButton {
        background-color: #5a5a5a;
        border: 1px solid #1e1e1e;
        padding: 5px;
        border-radius: 3px;
    }
    QPushButton:hover { background-color: #6a6a6a; }
    QPushButton:pressed { background-color: #7a7a7a; }
    QListWidget, QLineEdit, QTextEdit, QComboBox {
        background-color: #3c3c3c;
        border: 1px solid #5a5a5a;
        border-radius: 3px;
        padding: 3px;
    }
    QListWidget::item { padding: 3px; }
    QListWidget::item:selected {
        background-color: #0078d4;
    }
    QSplitter::handle {
        background-color: #5a5a5a;
        width: 1px;
    }
    QSplitter::handle:hover {
        background-color: #0078d4;
    }
    QStatusBar {
        background-color: #3c3c3c;
    }
"""

def generate_color_from_text(text):
    if not text: return QColor("#888888")
    hash_val = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)
    hue = hash_val % 360
    return QColor.fromHsv(hue, 200, 220)

class DetailsPanel(QWidget):
    task_edited = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.current_task = None
        self.setDisabled(True)
        layout = QFormLayout()
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.task_name_edit = QLineEdit()
        self.project_name_edit = QLineEdit()
        self.date_start_edit = QLineEdit()
        self.date_end_edit = QLineEdit()
        self.hours_est_edit = QLineEdit()
        self.location_edit = QLineEdit()
        self.content_edit = QTextEdit()
        for widget in [self.task_name_edit, self.project_name_edit, self.date_start_edit, self.date_end_edit, self.hours_est_edit, self.location_edit, self.content_edit]:
            widget.textChanged.connect(self.mark_as_dirty)
        layout.addRow("Task Name:", self.task_name_edit)
        layout.addRow("Project Name:", self.project_name_edit)
        layout.addRow("Start Date:", self.date_start_edit)
        layout.addRow("End Date:", self.date_end_edit)
        layout.addRow("Hours Est:", self.hours_est_edit)
        layout.addRow("Location:", self.location_edit)
        layout.addRow(QLabel("Note Content:"))
        layout.addRow(self.content_edit)
        self.setLayout(layout)

    def display_task(self, task: VibeTask):
        self.setDisabled(False)
        self.current_task = task
        for widget in [self.task_name_edit, self.project_name_edit, self.date_start_edit, self.date_end_edit, self.content_edit]:
            widget.blockSignals(True)
        self.task_name_edit.setText(task.metadata.get('task_name', ''))
        self.project_name_edit.setText(task.metadata.get('project_name', ''))
        start_date, end_date = task.metadata.get('date_start'), task.metadata.get('date_end')
        self.date_start_edit.setText(start_date.strftime('%Y-%m-%d') if isinstance(start_date, date) else "")
        self.date_end_edit.setText(end_date.strftime('%Y-%m-%d') if isinstance(end_date, date) else "")
        self.hours_est_edit.setText(str(task.metadata.get('hours_est', '')))
        self.location_edit.setText(task.metadata.get('location', ''))
        self.content_edit.setPlainText(task.content)
        for widget in [self.task_name_edit, self.project_name_edit, self.date_start_edit, self.date_end_edit, self.hours_est_edit, self.location_edit, self.content_edit]:
            widget.blockSignals(False)

    def mark_as_dirty(self):
        if self.current_task and not self.current_task.is_dirty:
            self.current_task.is_dirty = True
            self.task_edited.emit()

    def update_current_task_object(self):
        if not self.current_task: return
        self.current_task.metadata['task_name'] = self.task_name_edit.text()
        self.current_task.metadata['project_name'] = self.project_name_edit.text()
        try:
            self.current_task.metadata['date_start'] = datetime.strptime(self.date_start_edit.text(), '%Y-%m-%d').date()
            self.current_task.metadata['date_end'] = datetime.strptime(self.date_end_edit.text(), '%Y-%m-%d').date()
        except ValueError:
            print(f"Warning: Invalid date format for task '{self.current_task.metadata.get('task_name')}'. Not updating dates.")
        self.current_task.metadata['hours_est'] = self.hours_est_edit.text()
        self.current_task.metadata['location'] = self.location_edit.text()
        self.current_task.content = self.content_edit.toPlainText()

class VibeGanttApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VibeGantt - Project Flow IDE")
        self.setGeometry(100, 100, 1600, 900)
        self.tasks, self.errors = [], []
        self._create_menu_bar()
        self._setup_ui()

    def _setup_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.filter_panel, self.filter_layout = QWidget(), QVBoxLayout()
        self.filter_panel.setLayout(self.filter_layout)
        self.filter_layout.addWidget(QLabel("Date Range:"))
        self.date_range_filter = QComboBox()
        self.date_range_filter.addItems(["Next 30 Days", "Next 60 Days", "Next 90 Days", "This Year", "All Time"])
        self.filter_layout.addWidget(self.date_range_filter)
        self.project_filter = self._create_filter_widget("Project Name")
        self.phase_filter = self._create_filter_widget("Phase")
        self.cost_code_filter = self._create_filter_widget("Cost Code")
        self.assigned_to_filter = self._create_filter_widget("Assigned To")
        self.apply_button = QPushButton("Apply Filters")
        self.apply_button.clicked.connect(self.apply_filters)
        self.filter_layout.addWidget(self.apply_button)
        splitter.addWidget(self.filter_panel)
        self.gantt_chart = GanttChartWidget()
        splitter.addWidget(self.gantt_chart)
        self.details_panel = DetailsPanel()
        splitter.addWidget(self.details_panel)
        self.gantt_chart.task_clicked.connect(self.details_panel.display_task)
        self.details_panel.task_edited.connect(self.gantt_chart.update)
        splitter.setSizes([220, 1000, 380])
        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar(self))

    def _create_filter_widget(self, name):
        self.filter_layout.addWidget(QLabel(f"{name}:"))
        list_widget = QListWidget()
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.filter_layout.addWidget(list_widget)
        return list_widget

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        load_action = QAction("&Load Project Folder...", self)
        load_action.triggered.connect(self.load_project)
        file_menu.addAction(load_action)
        save_all_action = QAction("&Save All Changes", self)
        save_all_action.setShortcut("Ctrl+S")
        save_all_action.triggered.connect(self.save_all_changes)
        file_menu.addAction(save_all_action)
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def load_project(self):
        self.tasks, self.errors = ingest_project_data()
        status_message = f"Loaded {len(self.tasks)} tasks."
        if self.errors: status_message += f" Found {len(self.errors)} issues."
        self.statusBar().showMessage(status_message)
        self._populate_filter_options()
        self.gantt_chart.set_tasks([], date.today(), date.today())
        self.details_panel.setDisabled(True)

    def _populate_filter_options(self):
        def get_all_values(metadata_key):
            all_values = set()
            for t in self.tasks:
                value = t.metadata.get(metadata_key)
                if value:
                    values = value if isinstance(value, list) else [value]
                    all_values.update(str(v) for v in values)
            return sorted(list(all_values))
        for list_widget, items in [(self.project_filter, get_all_values('project_name')),
                                   (self.phase_filter, get_all_values('phase')),
                                   (self.cost_code_filter, get_all_values('cost_code')),
                                   (self.assigned_to_filter, get_all_values('assigned_to'))]:
            list_widget.clear()
            list_widget.addItems(items)

    def apply_filters(self):
        today = date.today()
        selected_range = self.date_range_filter.currentText()
        if selected_range == "All Time":
            valid_dates = [d for t in self.tasks for d in [t.metadata.get('date_start'), t.metadata.get('date_end')] if isinstance(d, date)]
            view_start, view_end = (min(valid_dates), max(valid_dates)) if valid_dates else (today, today + timedelta(days=1))
        else:
            days = int(selected_range.split()[1]) if "Days" in selected_range else 365
            view_start, view_end = (today, today + timedelta(days=days)) if "Next" in selected_range else (date(today.year, 1, 1), date(today.year, 12, 31))

        selected_projects = {item.text() for item in self.project_filter.selectedItems()}
        selected_phases = {item.text() for item in self.phase_filter.selectedItems()}
        selected_cost_codes = {item.text() for item in self.cost_code_filter.selectedItems()}
        selected_assignees = {item.text() for item in self.assigned_to_filter.selectedItems()}
        filtered_tasks = []
        for task in self.tasks:
            task_start, task_end = task.metadata.get('date_start'), task.metadata.get('date_end')
            if not (isinstance(task_start, date) and isinstance(task_end, date)): continue
            if task_start > view_end or task_end < view_start: continue
            def check_match(key, selections):
                if not selections: return True
                value = task.metadata.get(key)
                if not value: return False
                value_list = value if isinstance(value, list) else [value]
                return any(str(item) in selections for item in value_list)
            if (check_match('project_name', selected_projects) and
                check_match('phase', selected_phases) and
                check_match('cost_code', selected_cost_codes) and
                check_match('assigned_to', selected_assignees)):
                filtered_tasks.append(task)
        self.gantt_chart.set_tasks(filtered_tasks, view_start, view_end)
        self.statusBar().showMessage(f"Rendering {len(filtered_tasks)} tasks.", 3000)

    def save_all_changes(self):
        if self.details_panel.current_task and self.details_panel.current_task.is_dirty:
            self.details_panel.update_current_task_object()
        saved_count = 0
        for task in self.tasks:
            if task.is_dirty:
                try:
                    temp_path = task.file_path.with_suffix('.md.tmp')
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        frontmatter.dump(task, f)
                    os.replace(temp_path, task.file_path)
                    task.is_dirty = False
                    saved_count += 1
                except Exception as e:
                    print(f"CRITICAL: Failed to save {task.file_path.name}. Error: {e}")
                    if os.path.exists(temp_path): os.remove(temp_path)
        self.statusBar().showMessage(f"Successfully saved {saved_count} tasks.", 5000)
        self.gantt_chart.update()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_QSS)
    main_window = VibeGanttApp()
    main_window.show()
    sys.exit(app.exec())
