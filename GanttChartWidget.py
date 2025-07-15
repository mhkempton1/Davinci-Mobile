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
        content_height = self.header_height + total_tasks_height

        # Calculate total width needed for current date range and zoom
        # This is the 'logical' width of the chart area based on days and current pixels_per_day
        total_days = (self.end_date - self.start_date).days + 1
        if total_days <= 0:
            total_days = 1
        logical_chart_days_width = total_days * self.get_pixels_per_day()
        
        # The total width is name column + logical chart width.
        content_width = self.name_column_width + int(logical_chart_days_width)
        
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
            event.ignore() # Ignore rapid zoom events
            return
        self.last_zoom_time = current_time

        if modifiers == Qt.KeyboardModifier.ControlModifier:
            # Zoom
            # event.position().x() is already in viewport coordinates relative to widget's top-left
            self.zoom(delta > 0, event.position().x())
        elif modifiers == Qt.KeyboardModifier.ShiftModifier:
            # Horizontal scrolling for the date range
            days_to_scroll = -int(delta / 120) * 2 # Scroll by 2 days per wheel "notch"
            self.start_date += timedelta(days=days_to_scroll)
            self.end_date += timedelta(days=days_to_scroll)
            
            self.updateGeometry() # Recalculate content width for QScrollArea
            self.update() # Request repaint
            event.accept() # Mark event as handled
        else:
            # Default vertical scroll: Let QScrollArea handle it directly
            event.ignore() # Allow default QScrollArea behavior
            super().wheelEvent(event) # Pass the event up the hierarchy


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
        zoom_in_factor = 1.05 # Smaller step for smoother zoom
        zoom_out_factor = 1 / zoom_in_factor

        # Get current pixels_per_day before applying new zoom factor
        current_pixels_per_day = self.get_pixels_per_day()
        
        # Calculate the logical date at the mouse pointer's x-position within the chart area
        days_from_start_to_mouse = (mouse_x_on_viewport - self.name_column_width) / current_pixels_per_day

        # Apply new zoom factor
        if zoom_in:
            self.zoom_factor *= zoom_in_factor
        else:
            self.zoom_factor *= zoom_out_factor
        self.zoom_factor = max(0.05, min(self.zoom_factor, 20.0))

        # Calculate the new pixels per day after zoom
        new_pixels_per_day = self.get_pixels_per_day()
        
        # Calculate how many days are now visible in the fixed width of the widget's chart area
        new_total_days_visible_in_viewport = (self.width() - self.name_column_width) / new_pixels_per_day

        # Adjust self.start_date to keep the date under the mouse_x_on_viewport fixed
        original_date_at_mouse = self.start_date + timedelta(days=days_from_start_to_mouse)
        
        # Calculate the new offset from the start date to the mouse, based on the new scale
        offset_days_new_scale = (mouse_x_on_viewport - self.name_column_width) / new_pixels_per_day
        
        self.start_date = original_date_at_mouse - timedelta(days=offset_days_new_scale)
        self.end_date = self.start_date + timedelta(days=new_total_days_visible_in_viewport)

        self.updateGeometry() # Inform QScrollArea about potential content size change
        self.update() # Request repaint

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scroll_area_widget = self.parentWidget().parentWidget()
            h_scroll_offset = 0
            v_scroll_offset = 0

            if isinstance(scroll_area_widget, QScrollArea):
                h_scroll_offset = scroll_area_widget.horizontalScrollBar().value()
                v_scroll_offset = scroll_area_widget.verticalScrollBar().value()
            
            logical_mouse_x = event.pos().x() + h_scroll_offset
            logical_mouse_y = event.pos().y() + v_scroll_offset

            for task_obj, rect in self.task_rects:
                if rect.contains(logical_mouse_x, logical_mouse_y):
                    self.dragging = True
                    self.drag_task = task_obj
                    self.drag_start_pos = event.pos()
                    self.drag_start_date = task_obj.metadata['date_start']
                    self.task_clicked.emit(task_obj)
                    break
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta_x = event.pos().x() - self.drag_start_pos.x()
            pixels_per_day = self.get_pixels_per_day()
            days_delta = int(delta_x / pixels_per_day)

            new_start_date = self.drag_start_date + timedelta(days=days_delta)

            duration = self.drag_task.metadata['date_end'] - self.drag_task.metadata['date_start']
            new_end_date = new_start_date + duration

            self.drag_task.metadata['date_start'] = new_start_date
            self.drag_task.metadata['date_end'] = new_end_date

            self.update()

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = False
            self.drag_task.is_dirty = True
            self.task_clicked.emit(self.drag_task)
            self.drag_task = None
            self.drag_start_pos = None
            self.drag_start_date = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # The painter's transform is implicitly set by QScrollArea to reflect scrolling.
        # `visible_rect` here is in the painter's logical coordinate system (i.e., the scrolled view).
        visible_rect = painter.viewport() # Get the currently visible area in painter's logical coordinates
        
        # Draw background for the entire *logical* content area (which might be larger than visible_rect)
        # This will be clipped by QPainter to the visible_rect.
        painter.fillRect(self.rect(), QColor(43, 43, 43))

        # Calculate logical chart width (total width if no horizontal scroll)
        total_days = (self.end_date - self.start_date).days + 1
        if total_days <= 0: total_days = 1
        pixels_per_day = self.get_pixels_per_day()
        
        # --- Draw Date Header ---
        # The header background and line should be fixed at the top of the *viewport*
        # so they need to be drawn with respect to `visible_rect.top()`
        
        # Header background (fixed to top of viewport)
        painter.fillRect(visible_rect.left() + self.name_column_width, visible_rect.top(), 
                         visible_rect.width() - self.name_column_width, self.header_height, 
                         QColor(50, 50, 50))
        
        # Header bottom line (fixed to top of viewport)
        painter.setPen(QPen(QColor(100, 100, 100)))
        painter.drawLine(visible_rect.left() + self.name_column_width, visible_rect.top() + self.header_height,
                         visible_rect.right(), visible_rect.top() + self.header_height)

        # Determine date format and font size based on pixels_per_day
        date_format = "%b %d" # Default: Jul 17
        font_size_header = 8 # Base font size
        
        if pixels_per_day > 100:
            date_format = "%a %b %d" # e.g., Mon Jul 17
            font_size_header = 10
        elif pixels_per_day > 40:
            date_format = "%b %d"
            font_size_header = 9
        elif pixels_per_day < 15:
            date_format = "%b '%y" # e.g., Jul '25
            font_size_header = 7
        
        painter.setFont(QFont("Segoe UI", font_size_header)) # Set font for dates

        # Iterate through days for vertical lines and date labels
        for i in range(total_days):
            current_date = self.start_date + timedelta(days=i)
            # x position on the *full logical chart canvas*
            x_on_canvas = self.name_column_width + int(i * pixels_per_day)

            # Only draw grid line if it's within the visible horizontal range of the chart area
            if x_on_canvas >= visible_rect.left() + self.name_column_width - 1 and \
               x_on_canvas <= visible_rect.right() + 1: # Add padding to ensure lines at edge are drawn
                
                # Draw vertical grid line from header bottom to visible bottom
                painter.drawLine(x_on_canvas, visible_rect.top() + self.header_height, x_on_canvas, visible_rect.bottom())

                # Draw date label in header (positioned relative to visible_rect.top())
                if pixels_per_day > 15: # Only draw if enough space to avoid overcrowding
                    date_text = current_date.strftime(date_format)
                    text_rect_header = QRectF(x_on_canvas, visible_rect.top(), pixels_per_day, self.header_height - 5)
                    painter.setPen(QPen(QColor(211, 211, 211)))
                    painter.drawText(text_rect_header, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, date_text)

        # --- Draw Tasks ---
        self.task_rects = [] # Clear for new rendering cycle
        
        # Initial Y position for task drawing, relative to the content's top (0)
        # This is the Y offset FOR the tasks, below the header
        task_y_start_offset = self.header_height

        for task_index, task in enumerate(self.tasks_to_display):
            task_start_date = task.metadata.get('date_start')
            task_end_date = task.metadata.get('date_end')

            # Defensive check: if for some reason dates are still not date objects, assign defaults
            if not (isinstance(task_start_date, date) and isinstance(task_end_date, date)):
                task_start_date = date.today()
                task_end_date = date.today() + timedelta(days=1)

            days_from_view_start = (task_start_date - self.start_date).days
            task_duration_days = (task_end_date - task_start_date).days + 1

            # Calculate task bar position and size on the *full logical chart canvas*
            x_start_on_canvas = self.name_column_width + int(days_from_view_start * pixels_per_day)
            width_on_canvas = int(task_duration_days * pixels_per_day)
            height = self.task_height
            
            # The y-coordinate for the task bar, relative to the content's top (0)
            y_on_canvas = task_y_start_offset + task_index * (self.task_height + self.task_spacing)

            # Store rect for click detection (relative to overall widget content, not the viewport)
            # These are the "true" coordinates of the task bar on the infinite canvas.
            self.task_rects.append((task, QRectF(x_start_on_canvas, y_on_canvas, width_on_canvas, height)))

            # Only draw task bar if it's within the currently visible viewport
            if x_start_on_canvas + width_on_canvas >= visible_rect.left() + self.name_column_width and \
               x_start_on_canvas <= visible_rect.right() and \
               y_on_canvas + height > visible_rect.top() + self.header_height and \
               y_on_canvas < visible_rect.bottom():
                
                task_color = generate_color_from_text(task.metadata.get('project_name', ''))
                painter.fillRect(x_start_on_canvas, y_on_canvas, width_on_canvas, height, task_color)
                painter.setPen(QPen(QColor(0, 0, 0), 1)) # Black border
                painter.drawRect(x_start_on_canvas, y_on_canvas, width_on_canvas, height)

                # --- Draw Task Readout on the Bar ---
                task_name = task.metadata.get('task_name', 'Unnamed Task')
                project_id = task.metadata.get('project_name', '')
                cost_code = task.metadata.get('cost_code', '')

                # Ensure project_id and cost_code are strings
                if isinstance(project_id, list):
                    project_id = project_id[0] if project_id else ''
                if isinstance(cost_code, list):
                    cost_code = cost_code[0] if cost_code else ''

                task_info = f"{project_id} - {cost_code} - {task_name}"

                painter.setPen(QPen(QColor(255, 255, 255))) # White text for readability on colored bar
                font_size_bar_text = 8 # Base font size for text on bars
                if width_on_canvas < 50: # Adjust if bar is too narrow
                    font_size_bar_text = 7
                painter.setFont(QFont("Segoe UI", font_size_bar_text))
                
                # Calculate text rectangle within the task bar, with some padding
                text_padding = 2 # Reduced padding for better fit
                bar_text_rect = QRectF(x_start_on_canvas + text_padding, y_on_canvas + text_padding,
                                       width_on_canvas - 2 * text_padding, height - 2 * text_padding)
                
                # Elide text if it's too long
                font_metrics = QFontMetrics(painter.font())
                elided_text = font_metrics.elidedText(task_info, Qt.TextElideMode.ElideRight, int(bar_text_rect.width()))
                
                painter.drawText(bar_text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_text)


        # --- Draw Fixed Name Column Background and Separator Line ---
        # This part must be drawn *after* all scrolling content to ensure it overlays.
        # These are drawn relative to the painter's viewport (i.e., fixed on screen).
        
        # Background for the fixed name column
        painter.fillRect(visible_rect.left(), visible_rect.top(), 
                         self.name_column_width, visible_rect.height(), 
                         QColor(50, 50, 50))
        
        # Separator line for name column
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawLine(visible_rect.left() + self.name_column_width, visible_rect.top(),
                         visible_rect.left() + self.name_column_width, visible_rect.bottom())

        # --- Draw Fixed Task Names in the Left Column ---
        # These are also drawn relative to the painter's viewport.
        # Their Y positions need to be calculated relative to the viewport's top, considering scroll.
        
        painter.setFont(QFont("Segoe UI", 9)) # Font for fixed names
        for task_index, task in enumerate(self.tasks_to_display):
            # Calculate task's original Y position on the full canvas
            y_on_canvas = task_y_start_offset + task_index * (self.task_height + self.task_spacing)
            
            # Only draw if the name is vertically visible in the viewport
            if y_on_canvas + self.task_height > visible_rect.top() + self.header_height and \
               y_on_canvas < visible_rect.bottom():
                
                task_name = task.metadata.get('task_name', 'Unnamed Task')
                painter.setPen(QPen(QColor(211, 211, 211)))

                # The drawing rectangle for the name in the fixed column
                name_rect = QRectF(visible_rect.left() + 5, y_on_canvas, 
                                   self.name_column_width - 10, self.task_height)
                
                # Elide text if it's too long for the name column
                font_metrics_name = QFontMetrics(painter.font())
                elided_name = font_metrics_name.elidedText(task_name, Qt.TextElideMode.ElideRight, int(name_rect.width()))
                
                painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_name)

        # --- Draw Task Links ---
        painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine))
        for task in self.tasks_to_display:
            if task.linked_tasks:
                for linked_task_id in task.linked_tasks:
                    # Find the linked task in the list of all tasks
                    linked_task = next((t for t in self.tasks if t.metadata.get('vibe_id') == linked_task_id), None)
                    if linked_task:
                        # Find the rectangles for the two tasks
                        task_rect = next((rect for t, rect in self.task_rects if t == task), None)

                        # The linked task might not be in the visible area, so we need to calculate its rect
                        task_start_date = linked_task.metadata.get('date_start')
                        task_end_date = linked_task.metadata.get('date_end')
                        if not (isinstance(task_start_date, date) and isinstance(task_end_date, date)):
                            continue

                        days_from_view_start = (task_start_date - self.start_date).days
                        task_duration_days = (task_end_date - task_start_date).days + 1
                        pixels_per_day = self.get_pixels_per_day()
                        x_start_on_canvas = self.name_column_width + int(days_from_view_start * pixels_per_day)
                        width_on_canvas = int(task_duration_days * pixels_per_day)

                        linked_task_index = -1
                        try:
                            linked_task_index = self.tasks_to_display.index(linked_task)
                        except ValueError:
                            # The linked task is not in the displayed tasks
                            pass

                        if linked_task_index != -1:
                            y_on_canvas = self.header_height + linked_task_index * (self.task_height + self.task_spacing)
                            linked_task_rect = QRectF(x_start_on_canvas, y_on_canvas, width_on_canvas, self.task_height)
                        else:
                            linked_task_rect = None


                        if task_rect and linked_task_rect:
                            # Draw a line from the end of the current task to the start of the linked task
                            start_point = QPointF(task_rect.right(), task_rect.center().y())
                            end_point = QPointF(linked_task_rect.left(), linked_task_rect.center().y())
                            painter.drawLine(start_point, end_point)