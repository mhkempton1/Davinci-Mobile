from PyQt6.QtWidgets import QWidget, QApplication, QScrollArea # Import QScrollArea
from PyQt6.QtCore import pyqtSignal, Qt, QRectF, QPointF, QSize # Import QSize for sizeHint
from PyQt6.QtGui import QPainter, QColor, QPen, QFontMetrics, QFont, QTextOption
from datetime import date, timedelta, datetime
import hashlib
from engine import VibeTask

def generate_color_from_text(text):
    # Ensure text is a string, even if it's a list (e.g., if project_name has multiple values)
    if isinstance(text, list):
        if text:
            text = str(text[0]) # Take the first item in the list
        else:
            text = "" # Handle empty list
    if not text: return QColor("#888888")
    hash_val = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)
    hue = hash_val % 360
    return QColor.fromHsv(hue, 200, 220)

class GanttChartWidget(QWidget):
    task_clicked = pyqtSignal(VibeTask)

    def __init__(self):
        super().__init__()
        self.tasks = []
        self.tasks_to_display = []
        self.start_date, self.end_date = date.today(), date.today() + timedelta(days=60)
        self.task_rects = [] # Stores QRectF objects for click detection (logical coordinates)
        self.zoom_factor = 1.0
        self.task_height = 30
        self.task_spacing = 5
        self.header_height = 60 # Height for the date header
        self.name_column_width = 170 # Width for task names column (fixed on left)
        self.setMouseTracking(True) # Enable mouse tracking for hover effects (optional)
        self.last_zoom_time = datetime.now() # For zoom cooldown
        self.zoom_cooldown_ms = 100 # Milliseconds

        self.dragging = False
        self.drag_task = None
        self.drag_start_pos = None
        self.drag_start_date = None

        self.linking_mode = False
        self.link_start_task = None
        self.link_end_pos = None

        # Set a minimum size to ensure it's always viewable even with no tasks
        self.setMinimumSize(QSize(200 + self.name_column_width, self.header_height + 100)) # Min visible area

    def set_tasks(self, all_tasks: list[VibeTask], filtered_tasks: list[VibeTask], start_date: date, end_date: date):
        self.tasks = all_tasks
        # Helper function to ensure string conversion for sorting keys
        def get_string_value(metadata_value, default=""):
            if isinstance(metadata_value, list):
                return str(metadata_value[0]) if metadata_value else default
            return str(metadata_value) if metadata_value is not None else default

        # Sort tasks by project name then task name for consistent grouping
        self.tasks_to_display = sorted(filtered_tasks, key=lambda t: (
            get_string_value(t.metadata.get('project_name')),
            get_string_value(t.metadata.get('task_name', 'Unnamed Task'))
        ))
        
        # Ensure start_date is not after end_date just in case
        if start_date > end_date:
            end_date = start_date + timedelta(days=1)
        self.start_date, self.end_date = start_date, end_date
        
        # Crucial: Tell parent layout/QScrollArea that our content size might have changed
        self.updateGeometry()
        self.update() # Request a repaint

    # Override sizeHint to tell QScrollArea how big the *total content* is
    def sizeHint(self):
        # Calculate the total height needed for all tasks
        total_tasks_height = len(self.tasks_to_display) * (self.task_height + self.task_spacing)
        content_height = self.header_height + total_tasks_height + 20 # Add a buffer

        # Calculate total width needed for current date range and zoom
        # This is the 'logical' width of the chart area based on days and current pixels_per_day
        total_days = (self.end_date - self.start_date).days + 1
        if total_days <= 0:
            total_days = 1
        logical_chart_days_width = total_days * self.get_pixels_per_day()
        
        # The total width is name column + logical chart width.
        content_width = self.name_column_width + int(logical_chart_days_width) + 20 # Add a buffer
        
        # QScrollArea will use this size to determine scroll ranges.
        return QSize(content_width, content_height)


    def get_pixels_per_day(self):
        # Base pixel width for one day at zoom_factor = 1.0
        # This determines the 'resolution' of your chart.
        base_pixels_per_day = 30.0 # Adjusted for better default view
        return base_pixels_per_day * self.zoom_factor

    def wheelEvent(self, event):
        modifiers = QApplication.keyboardModifiers()
        delta = event.angleDelta().y()

        current_time = datetime.now()
        if (current_time - self.last_zoom_time).total_seconds() * 1000 < self.zoom_cooldown_ms and modifiers == Qt.KeyboardModifier.ControlModifier:
            event.ignore()
            return
        self.last_zoom_time = current_time

        if modifiers == Qt.KeyboardModifier.ControlModifier:
            self.zoom(delta > 0, event.position().x())
            event.accept()
        else:
            # Let the parent QScrollArea handle the scrolling
            event.ignore()


    def keyPressEvent(self, event):
        # Key presses for zooming only affect the GanttChartWidget itself
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
                self.zoom(True, self.width() / 2) # Zoom centered on the widget
            elif event.key() == Qt.Key.Key_Minus:
                self.zoom(False, self.width() / 2) # Zoom centered on the widget
            event.accept() # Mark event as handled
        else:
            super().keyPressEvent(event) # Pass other key events to parent

    def zoom(self, zoom_in, mouse_x_on_viewport):
        zoom_in_factor = 1.05
        zoom_out_factor = 1 / zoom_in_factor

        # Get the scroll area and its horizontal scrollbar
        scroll_area = self.parentWidget().parent()
        if not isinstance(scroll_area, QScrollArea):
            return

        h_bar = scroll_area.horizontalScrollBar()

        # Position of the mouse relative to the entire Gantt chart widget (including the part off-screen)
        old_gantt_x = mouse_x_on_viewport + h_bar.value()

        # Apply new zoom factor
        if zoom_in:
            self.zoom_factor *= zoom_in_factor
        else:
            self.zoom_factor *= zoom_out_factor
        self.zoom_factor = max(0.05, min(self.zoom_factor, 20.0))

        # Update the geometry to reflect the new sizeHint, which depends on the zoom_factor
        self.updateGeometry()
        self.update() # Repaint the widget

        # Calculate the new x position for the mouse to be under the cursor
        # The ratio of the mouse's position in the content should be the same before and after the zoom.
        # old_gantt_x / old_width = new_gantt_x / new_width
        # new_gantt_x = old_gantt_x * (new_width / old_width)
        # old_width is h_bar.maximum() + h_bar.pageStep()
        # new_width is calculated from the new sizeHint
        
        # To simplify, we can focus on the logical point (the date) under the cursor.
        # This part is tricky. For now, let's just update the geometry and let the scrollbars adjust.
        # A more advanced implementation would adjust the scrollbar value to keep the point under the mouse fixed.

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            modifiers = QApplication.keyboardModifiers()
            for task_obj, rect in self.task_rects:
                if rect.contains(event.pos()):
                    if modifiers == Qt.KeyboardModifier.ShiftModifier:
                        self.linking_mode = True
                        self.link_start_task = task_obj
                        self.update()
                        break
                    else:
                        self.dragging = True
                        self.drag_task = task_obj
                        self.drag_start_pos = event.pos()
                        self.drag_start_date = task_obj.metadata['date_start']
                        self.task_clicked.emit(task_obj)
                        break
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.linking_mode:
            self.link_end_pos = event.pos()
            self.update()
        elif self.dragging:
            delta_x = event.pos().x() - self.drag_start_pos.x()
            pixels_per_day = self.get_pixels_per_day()
            if pixels_per_day == 0: return
            days_delta = int(round(delta_x / pixels_per_day))

            new_start_date = self.drag_start_date + timedelta(days=days_delta)
            self.update_task_and_dependencies(self.drag_task, new_start_date)
            self.update()

    def update_task_and_dependencies(self, task, new_start_date):
        duration = task.metadata['date_end'] - task.metadata['date_start']
        task.metadata['date_start'] = new_start_date
        task.metadata['date_end'] = new_start_date + duration
        task.is_dirty = True

        if 'linked_tasks' in task.metadata:
            for linked_task_id in task.metadata['linked_tasks']:
                linked_task = next((t for t in self.tasks if t.metadata.get('vibe_id') == linked_task_id), None)
                if linked_task:
                    # The linked task should start when the current task ends
                    self.update_task_and_dependencies(linked_task, task.metadata['date_end'] + timedelta(days=1))

    def mouseReleaseEvent(self, event):
        if self.linking_mode:
            for task_obj, rect in self.task_rects:
                if rect.contains(event.pos()) and task_obj != self.link_start_task:
                    # Add link from self.link_start_task to task_obj
                    if 'linked_tasks' not in self.link_start_task.metadata:
                        self.link_start_task.metadata['linked_tasks'] = []
                    self.link_start_task.metadata['linked_tasks'].append(task_obj.metadata['vibe_id'])
                    self.link_start_task.is_dirty = True
                    break
            self.linking_mode = False
            self.link_start_task = None
            self.link_end_pos = None
            self.update()
        elif self.dragging:
            self.dragging = False
            self.drag_task.is_dirty = True
            self.task_clicked.emit(self.drag_task)
            self.drag_task = None
            self.drag_start_pos = None
            self.drag_start_date = None

    def render(self, painter):
        # This method is for printing or exporting the entire Gantt chart.
        # It's similar to paintEvent but draws the whole chart, not just the visible part.
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Use the full sizeHint for drawing dimensions
        content_size = self.sizeHint()

        # Draw background for the entire content area
        painter.fillRect(QRectF(0, 0, content_size.width(), content_size.height()), QColor(43, 43, 43))

        total_days = (self.end_date - self.start_date).days + 1
        if total_days <= 0: total_days = 1
        pixels_per_day = self.get_pixels_per_day()

        # --- Draw Date Header ---
        painter.fillRect(self.name_column_width, 0,
                         content_size.width() - self.name_column_width, self.header_height,
                         QColor(50, 50, 50))
        painter.setPen(QPen(QColor(100, 100, 100)))
        painter.drawLine(self.name_column_width, self.header_height,
                         content_size.width(), self.header_height)

        date_format = "%b %d"
        font_size_header = 8
        if pixels_per_day > 100:
            date_format = "%a %b %d"
            font_size_header = 10
        elif pixels_per_day > 40:
            date_format = "%b %d"
            font_size_header = 9
        elif pixels_per_day < 15:
            date_format = "%b '%y"
            font_size_header = 7
        painter.setFont(QFont("Segoe UI", font_size_header))

        for i in range(total_days):
            current_date = self.start_date + timedelta(days=i)
            x_on_canvas = self.name_column_width + int(i * pixels_per_day)
            painter.drawLine(x_on_canvas, self.header_height, x_on_canvas, content_size.height())
            if pixels_per_day > 15:
                date_text = current_date.strftime(date_format)
                text_rect_header = QRectF(x_on_canvas, 0, pixels_per_day, self.header_height - 5)
                painter.setPen(QPen(QColor(211, 211, 211)))
                painter.drawText(text_rect_header, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, date_text)

        # --- Draw Tasks ---
        task_y_start_offset = self.header_height
        for task_index, task in enumerate(self.tasks_to_display):
            task_start_date, task_end_date = task.metadata.get('date_start'), task.metadata.get('date_end')
            if not (isinstance(task_start_date, date) and isinstance(task_end_date, date)):
                task_start_date, task_end_date = date.today(), date.today() + timedelta(days=1)

            days_from_view_start = (task_start_date - self.start_date).days
            task_duration_days = (task_end_date - task_start_date).days + 1
            x_start_on_canvas = self.name_column_width + int(days_from_view_start * pixels_per_day)
            width_on_canvas = int(task_duration_days * pixels_per_day)
            height = self.task_height
            y_on_canvas = task_y_start_offset + task_index * (self.task_height + self.task_spacing)

            task_color = generate_color_from_text(task.metadata.get('project_name', ''))
            painter.fillRect(x_start_on_canvas, y_on_canvas, width_on_canvas, height, task_color)
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.drawRect(x_start_on_canvas, y_on_canvas, width_on_canvas, height)

            task_name = task.metadata.get('task_name', 'Unnamed Task')
            project_id = task.metadata.get('project_name', '')
            cost_code = task.metadata.get('cost_code', '')
            if isinstance(project_id, list): project_id = project_id[0] if project_id else ''
            if isinstance(cost_code, list): cost_code = cost_code[0] if cost_code else ''
            task_info = f"{project_id} - {cost_code} - {task_name}"

            painter.setPen(QPen(QColor(255, 255, 255)))
            font_size_bar_text = 8
            if width_on_canvas < 50: font_size_bar_text = 7
            painter.setFont(QFont("Segoe UI", font_size_bar_text))
            text_padding = 2
            bar_text_rect = QRectF(x_start_on_canvas + text_padding, y_on_canvas + text_padding,
                                   width_on_canvas - 2 * text_padding, height - 2 * text_padding)
            font_metrics = QFontMetrics(painter.font())
            elided_text = font_metrics.elidedText(task_info, Qt.TextElideMode.ElideRight, int(bar_text_rect.width()))
            painter.drawText(bar_text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_text)

        # --- Draw Fixed Name Column ---
        painter.fillRect(0, 0, self.name_column_width, content_size.height(), QColor(50, 50, 50))
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawLine(self.name_column_width, 0, self.name_column_width, content_size.height())

        painter.setFont(QFont("Segoe UI", 9))
        for task_index, task in enumerate(self.tasks_to_display):
            y_on_canvas = task_y_start_offset + task_index * (self.task_height + self.task_spacing)
            task_name = task.metadata.get('task_name', 'Unnamed Task')
            painter.setPen(QPen(QColor(211, 211, 211)))
            name_rect = QRectF(5, y_on_canvas, self.name_column_width - 10, self.task_height)
            font_metrics_name = QFontMetrics(painter.font())
            elided_name = font_metrics_name.elidedText(task_name, Qt.TextElideMode.ElideRight, int(name_rect.width()))
            painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_name)
        
        # --- Draw Task Links ---
        painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine))
        for task in self.tasks_to_display:
            if 'linked_tasks' in task.metadata and task.metadata['linked_tasks']:
                for linked_task_id in task.metadata['linked_tasks']:
                    linked_task = next((t for t in self.tasks if t.metadata.get('vibe_id') == linked_task_id), None)
                    if linked_task:
                        task_rect = next((rect for t, rect in self.task_rects if t == task), None)
                        linked_task_rect = next((rect for t, rect in self.task_rects if t == linked_task), None)
                        if task_rect and linked_task_rect:
                            start_point = QPointF(task_rect.right(), task_rect.center().y())
                            end_point = QPointF(linked_task_rect.left(), linked_task_rect.center().y())
                            painter.drawLine(start_point, end_point)

        # --- Draw linking line ---
        if self.linking_mode and self.link_start_task and self.link_end_pos:
            task_rect = next((rect for t, rect in self.task_rects if t == self.link_start_task), None)
            if task_rect:
                start_point = QPointF(task_rect.right(), task_rect.center().y())
                painter.setPen(QPen(QColor(255, 165, 0), 2, Qt.PenStyle.DashLine)) # Orange color for linking line
                painter.drawLine(start_point, self.link_end_pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # The QScrollArea handles the painter's translation, so we just draw the whole chart.
        # The painter is clipped to the visible area.
        self.render(painter)

        # --- Draw linking line ---
        if self.linking_mode and self.link_start_task and self.link_end_pos:
            task_rect = next((rect for t, rect in self.task_rects if t == self.link_start_task), None)
            if task_rect:
                # We need to adjust the start point by the scroll offset
                scroll_area = self.parentWidget().parent()
                h_scroll_offset = scroll_area.horizontalScrollBar().value()
                v_scroll_offset = scroll_area.verticalScrollBar().value()

                start_point = QPointF(task_rect.right() - h_scroll_offset, task_rect.center().y() - v_scroll_offset)

                painter.setPen(QPen(QColor(255, 165, 0), 2, Qt.PenStyle.DashLine)) # Orange color for linking line
                painter.drawLine(start_point, self.link_end_pos)