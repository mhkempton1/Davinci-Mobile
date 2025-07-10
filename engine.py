import frontmatter
import uuid
from pathlib import Path
from tkinter import filedialog, Tk
from datetime import datetime

class VibeTask:
    """Represents a single task parsed from a Markdown file."""
    def __init__(self, file_path, metadata, content):
        self.file_path = file_path
        self.metadata = metadata
        self.content = content
        self.is_dirty = False # Flag to track unsaved changes

    def __repr__(self):
        task_name = self.metadata.get('task_name', 'Unnamed Task')
        return f"VibeTask(name='{task_name}', path='{self.file_path.name}')"

def validate_task_data(task_metadata):
    """Checks for presence of essential fields AND logical consistency."""
    required_fields = ['task_name', 'date_start', 'date_end']

    missing_fields = [field for field in required_fields if field not in task_metadata or task_metadata[field] is None]
    if missing_fields:
        return missing_fields

    try:
        start_date = task_metadata['date_start']
        end_date = task_metadata['date_end']
        # Ensure they are date objects if they are not already
        if not isinstance(start_date, datetime.date):
            start_date = datetime.strptime(str(start_date), '%Y-%m-%d').date()
        if not isinstance(end_date, datetime.date):
            end_date = datetime.strptime(str(end_date), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return ["invalid_date_format"]

    if start_date > end_date:
        return ["impossible_timeline"]

    return None

def ingest_project_data():
    """Scans, parses, and now VALIDATES project files."""
    print("Initializing Vibe Engine... Please select your root project folder.")
    root = Tk()
    root.withdraw()
    root_path_str = filedialog.askdirectory(title="Select Root Project Folder")
    root.destroy()

    if not root_path_str:
        print("No folder selected. Aborting.")
        return [], []

    root_path = Path(root_path_str)
    print(f"Scanning directory: {root_path}")

    task_files = list(root_path.glob('**/Task Sheets/**/*.md'))
    print(f"Found {len(task_files)} task files to process.")

    all_tasks = []
    ingestion_errors = []

# In engine.py, inside the ingest_project_data function

    for file in task_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                task_post = frontmatter.load(f)

            # --- THE CHANGE IS HERE ---
            validation_issues = validate_task_data(task_post.metadata)
            if validation_issues:
                # We still report the error...
                error_message = f"File: {file.name} | Validation Error: Missing or invalid fields -> {validation_issues}"
                ingestion_errors.append(error_message)
                # ...but we REMOVE the 'continue' statement that was here.
                # This ensures the task is loaded regardless of validation status.

            if 'vibe_id' not in task_post.metadata:
                new_id = str(uuid.uuid4())
                task_post.metadata['vibe_id'] = new_id
                task_obj = VibeTask(file, task_post.metadata, task_post.content)
                task_obj.is_dirty = True
            else:
                task_obj = VibeTask(file, task_post.metadata, task_post.content)

            # Now, all tasks (even those with errors) will be added to the list.
            all_tasks.append(task_obj)

        except Exception as e:
            error_message = f"File: {file.name} | Parsing Error: {e}"
            ingestion_errors.append(error_message)

    print("-" * 30)
    print(f"Ingestion Complete. Successfully loaded {len(all_tasks)} tasks.")

    if ingestion_errors:
        print(f"\nEncountered {len(ingestion_errors)} issues during ingestion:")
        for error in ingestion_errors:
            print(f"- {error}")
    else:
        print("All files processed and validated without issues.")

    print("-" * 30)
    return all_tasks, ingestion_errors