# In main_gui.py
# Add these imports at the top
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import QRectF
from datetime import date, timedelta

# ... (rest of your imports) ...

# NEW WIDGET: The Gantt Chart Canvas
class GanttChartWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.tasks_to_display = []
        self.start_date = date.today()
        self.end_date = date.today() + timedelta(days=60)
        self.setMinimumHeight(400)

    def set_tasks(self, tasks):
        """Receives the list of tasks to be drawn."""
        self.tasks_to_display = tasks
        if not tasks:
            self.update() # Redraw the widget
            return
            
        # Determine the date range of the tasks to display
        dates = [t.metadata['date_start'] for t in tasks] + [t.metadata['date_end'] for t in tasks]
        self.start_date = min(dates) - timedelta(days=7) # Add some padding
        self.end_date = max(dates) + timedelta(days=7)   # Add some padding
        
        self.update() # Trigger a redraw

    def paintEvent(self, event):
        """This is where all the drawing happens."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Define chart dimensions
        width = self.width()
        height = self.height()
        header_height = 30
        row_height = 25
        left_margin = 150 # Space for task names

        if not self.tasks_to_display:
            painter.drawText(QRectF(0, 0, width, height), Qt.AlignmentFlag.AlignCenter, "No tasks to display. Apply filters to begin.")
            return

        # Draw header (for now, just a line)
        painter.setPen(QColor("#555"))
        painter.drawLine(0, header_height, width, header_height)
        
        # --- Timeline Calculation ---
        total_days = (self.end_date - self.start_date).days
        if total_days == 0: return # Avoid division by zero
        pixels_per_day = (width - left_margin) / total_days

        # --- Draw Tasks ---
        for i, task in enumerate(self.tasks_to_display):
            y_pos = header_height + (i * row_height)

            # Draw task name
            painter.setPen(QColor("#ccc")) # Text color
            task_name = task.metadata.get('task_name', 'Unnamed Task')
            painter.drawText(QRectF(5, y_pos, left_margin - 10, row_height), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, task_name)
            
            # Draw task bar
            task_start = task.metadata['date_start']
            task_end = task.metadata['date_end']
            
            x_start_offset = (task_start - self.start_date).days * pixels_per_day
            bar_width = (task_end - task_start).days * pixels_per_day
            
            bar_rect = QRectF(left_margin + x_start_offset, y_pos + 5, bar_width, row_height - 10)
            
            # TODO: Add logic for project colors and "fluorescent" flagging here
            painter.setBrush(QColor("#0078d4")) # Default blue color for now
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_rect, 5, 5)

# In the VibeGanttApp class...
class VibeGanttApp(QMainWindow):
    # ... (__init__ is the same)
    
    def _setup_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ... (filter panel setup is the same)
        self.filter_panel = QWidget()
        self.filter_layout = QVBoxLayout(self.filter_panel)
        # ... (all filter widgets setup)
        
        splitter.addWidget(self.filter_panel)

        # --- Replace QLabel with our new GanttChartWidget ---
        self.gantt_chart = GanttChartWidget()
        splitter.addWidget(self.gantt_chart)
        
        # ... (rest of setup is the same)
        
    def apply_filters(self):
        # ... (code to get filter values is the same)
        
        # --- This is where the magic happens! ---
        # Filter the self.tasks list based on the selections
        filtered_tasks = []
        # TODO: Add filtering logic here
        
        # For now, we'll just pass all tasks to show it works
        filtered_tasks = self.tasks 
        
        self.gantt_chart.set_tasks(filtered_tasks) # Send data to the widget
        self.statusBar().showMessage(f"Rendering {len(filtered_tasks)} tasks.", 3000)

    # ... (the rest of the VibeGanttApp class, including the fixed _populate_filter_options)