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

class GanttChartWidget(QWidget):
    task_clicked = pyqtSignal(VibeTask)
    def __init__(self):
        super().__init__()
        self.tasks_to_display = []
        self.start_date, self.end_date = date.today(), date.today() + timedelta(days=60)
        self.task_rects = []
        self.scroll_y = 0
        self.zoom_factor = 1.0

    def set_tasks(self, tasks: list[VibeTask], start_date: date, end_date: date):
        self.tasks_to_display = tasks
        self.start_date, self.end_date = start_date, end_date
        self.update()

    def wheelEvent(self, event):
        """Handles mouse wheel scrolling for panning and zooming."""
        modifiers = QApplication.keyboardModifiers()
        delta = event.angleDelta().y()

        if modifiers == Qt.KeyboardModifier.ControlModifier:
            self.zoom(delta > 0, event.position().x())
        elif modifiers == Qt.KeyboardModifier.ShiftModifier:
            # Vertical scroll
            self.scroll_y += delta / 120 * 10 # Scroll by 10 pixels
            self.scroll_y = min(0, self.scroll_y) # Prevent scrolling past the top
        else:
            # Horizontal scroll
            days_to_scroll = -int(delta / 120) * 2  # Scroll by 2 days
            self.start_date += timedelta(days=days_to_scroll)
            self.end_date += timedelta(days=days_to_scroll)

        self.update()
        event.accept()

    def keyPressEvent(self, event):
        """Handles key presses for zooming."""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
                self.zoom(True, self.width() / 2)
            elif event.key() == Qt.Key.Key_Minus:
                self.zoom(False, self.width() / 2)
        else:
            super().keyPressEvent(event)

    def zoom(self, zoom_in, mouse_x):
        """Zooms the Gantt chart in or out, centered on the mouse position."""
        zoom_in_factor = 1.1
        zoom_out_factor = 1 / zoom_in_factor

        # Calculate the date at the mouse position before zooming
        total_days = (self.end_date - self.start_date).days
        if total_days <= 0: return

        pixels_per_day = (self.width() - 170) / total_days
        days_from_start = (mouse_x - 170) / pixels_per_day
        center_date = self.start_date + timedelta(days=days_from_start)

        # Apply zoom
        if zoom_in:
            self.zoom_factor *= zoom_in_factor
        else:
            self.zoom_factor *= zoom_out_factor
        self.zoom_factor = max(0.1, min(self.zoom_factor, 10.0))

        # Recalculate the date range to keep the center_date at the same mouse position
        new_total_days = total_days / self.zoom_factor
        new_days_from_start = days_from_start / self.zoom_factor

        self.start_date = center_date - timedelta(days=new_days_from_start)
        self.end_date = self.start_date + timedelta(days=new_total_days)

        self.update()

    def mousePressEvent(self, event):
        for rect, task in self.task_rects:
            if rect.contains(event.position()):
                self.task_clicked.emit(task)
                return

    def paintEvent(self, event):
        painter, self.task_rects = QPainter(self), []
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()
        header_height, row_height, left_margin = 40, 25, 170
        if not self.tasks_to_display:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Load a project and apply filters.")
            return
        total_days = (self.end_date - self.start_date).days
        if total_days <= 0: return
        pixels_per_day = (width - left_margin) / total_days * self.zoom_factor
        current_date = self.start_date
        while current_date <= self.end_date:
            x_pos = left_margin + (current_date - self.start_date).days * pixels_per_day
            is_month_start, is_week_start = current_date.day == 1, current_date.weekday() == 0
            pen_color = "#888" if is_month_start else "#666" if is_week_start else "#444"
            painter.setPen(QPen(QColor(pen_color), 1 if is_month_start else 0.5))
            if is_month_start: painter.drawText(int(x_pos) + 4, 18, current_date.strftime('%b %Y'))
            painter.drawLine(int(x_pos), header_height if is_week_start else 25, int(x_pos), height)
            current_date += timedelta(days=1)
        painter.setPen(QColor("#555"))
        painter.drawLine(0, header_height, width, header_height)
        for i, task in enumerate(self.tasks_to_display):
            y_pos = header_height + (i * row_height) + self.scroll_y
            if y_pos < header_height: continue # Don't draw tasks that are scrolled off the top
            task_name = f"* {task.metadata.get('task_name', '')}" if task.is_dirty else task.metadata.get('task_name', '')
            painter.setPen(QColor("#ccc"))
            painter.drawText(QRectF(5, y_pos, left_margin - 10, row_height), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, task_name)
            task_start, task_end = task.metadata.get('date_start'), task.metadata.get('date_end')
            if not isinstance(task_start, date) or not isinstance(task_end, date): continue
            x_start_offset = (task_start - self.start_date).days * pixels_per_day
            bar_width = max(1, (task_end - task_start + timedelta(days=1)).days * pixels_per_day)
            bar_rect = QRectF(left_margin + x_start_offset, y_pos + 5, bar_width, row_height - 10)
            self.task_rects.append((bar_rect, task))
            base_color = generate_color_from_text(task.metadata.get('project_name'))
            validation_issues = validate_task_data(task.metadata)
            final_color = QColor.fromHsv(base_color.hue(), 255, 255) if validation_issues and "impossible_timeline" in validation_issues else base_color
            painter.setBrush(final_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_rect, 5, 5)

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