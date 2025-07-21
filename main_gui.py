import sys
import os
from tkinter import filedialog, Tk
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QMenuBar,
                             QStatusBar, QWidget, QVBoxLayout, QListWidget,
                             QSplitter, QPushButton, QAbstractItemView, QFormLayout,
                             QLineEdit, QTextEdit, QComboBox, QMessageBox, QWidget, QSizePolicy)
from PyQt6.QtGui import QAction, QPainter, QColor, QPen, QTextOption, QFont
from PyQt6.QtCore import Qt, QRectF, QDate, pyqtSignal, QPointF
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
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
        self.content_edit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)


        for widget in [self.task_name_edit, self.project_name_edit, self.date_start_edit, self.date_end_edit, self.hours_est_edit, self.location_edit, self.content_edit]:
            widget.textChanged.connect(self.mark_as_dirty)

        layout.addRow("Task Name:", self.task_name_edit)
        layout.addRow("Project Name:", self.project_name_edit)
        layout.addRow("Start Date (YYYY-MM-DD):", self.date_start_edit)
        layout.addRow("End Date (YYYY-MM-DD):", self.date_end_edit)
        layout.addRow("Hours Est:", self.hours_est_edit)
        layout.addRow("Location:", self.location_edit)
        layout.addRow(QLabel("Note Content (Markdown/Text):"))
        layout.addRow(self.content_edit)
        self.setLayout(layout)

    def display_task(self, task: VibeTask):
        self.setDisabled(False)
        self.current_task = task
        for widget in [self.task_name_edit, self.project_name_edit, self.date_start_edit, self.date_end_edit, self.content_edit]:
            widget.blockSignals(True)
        self.task_name_edit.setText(task.metadata.get('task_name', ''))
        
        project_name_val = task.metadata.get('project_name', '')
        if isinstance(project_name_val, list):
            self.project_name_edit.setText(str(project_name_val[0]) if project_name_val else '')
        else:
            self.project_name_edit.setText(str(project_name_val))

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
        
        task_name = self.task_name_edit.text()
        project_name = self.project_name_edit.text()
        start_date_str = self.date_start_edit.text()
        end_date_str = self.date_end_edit.text()
        hours_est = self.hours_est_edit.text()
        location = self.location_edit.text()
        content = self.content_edit.toPlainText()

        parsed_start_date = None
        if start_date_str:
            try:
                parsed_start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                QMessageBox.warning(self, "Invalid Start Date Format",
                                    "Start Date could not be parsed. Please use YYYY-MM-DD format.")
                parsed_start_date = self.current_task.metadata.get('date_start', None)


        parsed_end_date = None
        if end_date_str:
            try:
                parsed_end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                QMessageBox.warning(self, "Invalid End Date Format",
                                    "End Date could not be parsed. Please use YYYY-MM-DD format.")
                parsed_end_date = self.current_task.metadata.get('date_end', None)


        temp_metadata = {
            'task_name': task_name,
            'project_name': project_name,
            'date_start': parsed_start_date,
            'date_end': parsed_end_date,
            'date_due': self.current_task.metadata.get('date_due') 
        }

        validation_issues = validate_task_data(temp_metadata)
        
        if validation_issues:
            display_issues = [issue for issue in validation_issues if issue != 'using_date_due_for_date_end']
            if display_issues:
                issue_msg = ", ".join(display_issues)
                QMessageBox.warning(self, "Date Validation Info/Warning",
                                    f"Issues with dates for '{temp_metadata.get('task_name', 'Current Task')}': {issue_msg}\n"
                                    "Dates have been adjusted to defaults or corrected to maintain timeline validity. "
                                    "Please check the values displayed.")
            
        self.current_task.metadata['task_name'] = task_name
        
        if isinstance(project_name, list):
            self.current_task.metadata['project_name'] = project_name[0] if project_name else ''
        else:
            self.current_task.metadata['project_name'] = project_name


        self.current_task.metadata['date_start'] = temp_metadata['date_start']
        self.current_task.metadata['date_end'] = temp_metadata['date_end']
        self.current_task.metadata['hours_est'] = hours_est
        self.current_task.metadata['location'] = location
        self.current_task.content = content

        self.date_start_edit.blockSignals(True)
        self.date_end_edit.blockSignals(True)
        self.date_start_edit.setText(self.current_task.metadata['date_start'].strftime('%Y-%m-%d'))
        self.date_end_edit.setText(self.current_task.metadata['date_end'].strftime('%Y-%m-%d'))
        self.date_start_edit.blockSignals(False)
        self.date_end_edit.blockSignals(False)


class VibeGanttApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VibeGantt - Project Flow IDE")
        self.setGeometry(100, 100, 1600, 900)
        self.tasks, self.errors = [], []
        self._create_menu_bar()
        self._setup_ui()
        self.load_project() # Automatically load project on startup

    def closeEvent(self, event):
        QApplication.instance().quit()
        event.accept()

    def _setup_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.filter_panel = QWidget()
        self.filter_panel.setMinimumWidth(200)
        self.filter_panel.setMaximumWidth(400)
        self.filter_layout = QVBoxLayout()
        self.filter_panel.setLayout(self.filter_layout)
        self.filter_layout.addWidget(QLabel("Date Range:"))
        self.date_range_filter = QComboBox()
        self.date_range_filter.addItems(["Next 30 Days", "Next 60 Days", "Next 90 Days", "This Year", "All Time"])
        self.date_range_filter.currentIndexChanged.connect(self.apply_filters)
        self.filter_layout.addWidget(self.date_range_filter)
        self.project_filter = self._create_filter_widget("Project Name")
        self.phase_filter = self._create_filter_widget("Phase")
        self.cost_code_filter = self._create_filter_widget("Cost Code")
        self.assigned_to_filter = self._create_filter_widget("Assigned To")

        for lw in [self.project_filter, self.phase_filter, self.cost_code_filter, self.assigned_to_filter]:
            lw.itemSelectionChanged.connect(self.apply_filters)

        self.filter_layout.addStretch(1)

        splitter.addWidget(self.filter_panel)
        
        self.gantt_chart = GanttChartWidget()
        splitter.addWidget(self.gantt_chart)
        
        self.details_panel = DetailsPanel()
        splitter.addWidget(self.details_panel)
        self.gantt_chart.task_clicked.connect(self.details_panel.display_task)
        self.details_panel.task_edited.connect(self.gantt_chart.update) # Trigger chart repaint on task edit

        splitter.setSizes([220, 1000, 380])
        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar(self))

    def _create_filter_widget(self, name):
        label = QLabel(f"{name}:")
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.filter_layout.addWidget(label)
        list_widget = QListWidget()
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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

        print_action = QAction("&Print Gantt Chart...", self)
        print_action.setShortcut("Ctrl+P")
        print_action.triggered.connect(self.print_gantt_chart)
        file_menu.addAction(print_action)

        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def load_project(self):
        root = Tk()
        root.withdraw()
        root_path_str = filedialog.askdirectory(title="Select Root Project Folder")
        root.destroy()
        if not root_path_str:
            self.statusBar().showMessage("Project loading cancelled.", 5000)
            return

        self.tasks, self.errors = ingest_project_data(root_path_str)
        status_message = f"Loaded {len(self.tasks)} tasks."
        if self.errors: status_message += f" Found {len(self.errors)} issues."
        self.statusBar().showMessage(status_message)
        self._populate_filter_options()
        self.apply_filters() # Apply initial filter after loading tasks
        self.details_panel.setDisabled(True)

    def _populate_filter_options(self):
        def get_all_values(metadata_key):
            all_values = set()
            for t in self.tasks:
                value = t.metadata.get(metadata_key)
                if value:
                    values = value if isinstance(value, list) else [value]
                    all_values.update(str(v) for v in values) # Ensure values are string for set/sorting
            return sorted(list(all_values))
        
        self.project_filter.clearSelection()
        self.phase_filter.clearSelection()
        self.cost_code_filter.clearSelection()
        self.assigned_to_filter.clearSelection()

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
            if not (isinstance(task_start, date) and isinstance(task_end, date)):
                continue

            if task_start > view_end or task_end < view_start:
                continue

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
        self.gantt_chart.set_tasks(self.tasks, filtered_tasks, view_start, view_end)
        self.statusBar().showMessage(f"Rendering {len(filtered_tasks)} tasks.", 3000)

    def save_all_changes(self):
        if self.details_panel.current_task and self.details_panel.current_task.is_dirty:
            self.details_panel.update_current_task_object()

        saved_count = 0
        for task in self.tasks:
            if task.is_dirty:
                try:
                    temp_path = task.file_path.with_suffix('.md.tmp')
                    post_to_dump = frontmatter.Post(task.content)
                    
                    clean_metadata = {}
                    problematic_keys = {'date_order_due', 'date_precon_due'}

                    for key, value in task.metadata.items():
                        if key in problematic_keys and isinstance(value, str) and ("=" in value or "$=" in value):
                            # Skip saving problematic Obsidian DataviewJS expressions directly
                            continue 
                        elif isinstance(value, (date, datetime)):
                            clean_metadata[key] = value.strftime('%Y-%m-%d')
                        elif isinstance(value, list):
                            # Ensure all items in the list are strings before joining
                            clean_metadata[key] = ", ".join(map(str, value))
                        elif value is None:
                            clean_metadata[key] = ""
                        else:
                            clean_metadata[key] = str(value)
                    
                    if task.linked_tasks:
                        clean_metadata['linked_tasks'] = ", ".join(task.linked_tasks)

                    post_to_dump.metadata = clean_metadata
                    
                    with open(temp_path, 'wb') as f:
                        frontmatter.dump(post_to_dump, f)
                    os.replace(temp_path, task.file_path)
                    task.is_dirty = False
                    saved_count += 1
                except Exception as e:
                    print(f"CRITICAL: Failed to save {task.file_path.name}. Error: {e}")
                    QMessageBox.critical(self, "Save Error", f"Failed to save {task.file_path.name}.\nError: {e}")
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
        self.statusBar().showMessage(f"Successfully saved {saved_count} tasks.", 5000)
        self.gantt_chart.update()

    def print_gantt_chart(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        print_dialog = QPrintDialog(printer, self)
        if print_dialog.exec() == QPrintDialog.DialogCode.Accepted:
            # Set a fixed high resolution for rendering the image
            render_dpi = 300

            gantt_content_size = self.gantt_chart.sizeHint()
            if gantt_content_size.width() == 0 or gantt_content_size.height() == 0:
                QMessageBox.warning(self, "Print Error", "Gantt chart has no content to print.")
                return

            # Create an image with a size that matches the aspect ratio of the content
            # and is scaled by our desired DPI for high quality.
            image_size = QSize(
                int(gantt_content_size.width() * render_dpi / 96), # 96 is a typical screen DPI
                int(gantt_content_size.height() * render_dpi / 96)
            )
            image = QImage(image_size, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.white) # White background for printing

            # Create a painter to draw the Gantt chart onto the QImage
            image_painter = QPainter(image)
            image_painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Use a QTransform to scale the painter to fit the content to the image
            source_rect = QRectF(0, 0, gantt_content_size.width(), gantt_content_size.height())
            target_rect = QRectF(0, 0, image.width(), image.height())

            transform = QTransform()
            transform.scale(target_rect.width() / source_rect.width(), target_rect.height() / source_rect.height())
            image_painter.setTransform(transform)

            # Render the full Gantt chart widget to the image
            self.gantt_chart.render(image_painter)
            image_painter.end()

            # Now, draw the high-resolution image onto the printer
            printer_painter = QPainter(printer)
            page_rect = printer.pageRect(QPrinter.Unit.Point) # Use points for physical measurements

            # Scale the image to fit the printable area of the page while maintaining aspect ratio
            image_aspect_ratio = image.width() / image.height()
            page_aspect_ratio = page_rect.width() / page_rect.height()

            if image_aspect_ratio > page_aspect_ratio:
                # Image is wider than page -> scale to page width
                scaled_width = page_rect.width()
                scaled_height = scaled_width / image_aspect_ratio
            else:
                # Image is taller than page -> scale to page height
                scaled_height = page_rect.height()
                scaled_width = scaled_height * image_aspect_ratio

            # Center the image on the page
            x_offset = (page_rect.width() - scaled_width) / 2
            y_offset = (page_rect.height() - scaled_height) / 2

            target_draw_rect = QRectF(page_rect.left() + x_offset, page_rect.top() + y_offset, scaled_width, scaled_height)

            printer_painter.drawImage(target_draw_rect, image)
            printer_painter.end()
            
            self.statusBar().showMessage("Gantt Chart printed successfully.", 3000)
        else:
            self.statusBar().showMessage("Print cancelled.", 3000)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_QSS)
    main_window = VibeGanttApp()
    main_window.show()

    if os.environ.get('QT_QPA_PLATFORM') != 'offscreen':
        sys.exit(app.exec())