import frontmatter
import uuid
from pathlib import Path
from datetime import datetime, date, timedelta

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
    """Checks for presence of essential fields AND logical consistency, providing defaults for dates.
       Modifies task_metadata in place with validated/defaulted date objects."""
    issues = []

    if 'task_name' not in task_metadata or task_metadata['task_name'] is None:
        issues.append('missing_task_name')

    start_date = None
    end_date = None

    # Helper to parse date values, handling lists and various date types
    def parse_date_value(value, default_date=None):
        if value is None:
            return default_date
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date): # Already a date object
            return value
        if isinstance(value, list) and value: # Take first item if it's a list
            value = value[0]
        try:
            return datetime.strptime(str(value), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return default_date

    # Process date_start
    start_date = parse_date_value(task_metadata.get('date_start'), date.today())
    if 'date_start' not in task_metadata or task_metadata['date_start'] is None:
        issues.append("missing_date_start")
    elif not isinstance(task_metadata['date_start'], (date, datetime)) and "invalid_date_start_format" not in issues and start_date == date.today():
         issues.append("invalid_date_start_format")


    # Process date_end, with date_due as fallback
    end_date = parse_date_value(task_metadata.get('date_end'))
    if end_date is None: # If date_end is missing/invalid, try date_due
        end_date = parse_date_value(task_metadata.get('date_due'))
        if end_date is not None:
            issues.append("using_date_due_for_date_end")

    if end_date is None: # If still no end_date, default
        issues.append("missing_date_end")
        end_date = start_date + timedelta(days=1)

    # Ensure start_date is not after end_date
    if start_date > end_date:
        issues.append("impossible_timeline")
        end_date = start_date # Adjust end_date to be at least start_date

    # Update metadata with validated/defaulted dates
    task_metadata['date_start'] = start_date
    task_metadata['date_end'] = end_date

    return issues if issues else None

def ingest_project_data(root_path_str):
    """Scans, parses, and VALIDATES project files."""
    if not root_path_str:
        print("No folder selected. Aborting.")
        return [], []

    root_path = Path(root_path_str)
    print(f"Scanning directory: {root_path}")

    task_files = list(root_path.glob('**/Task Sheets/**/*.md'))
    print(f"Found {len(task_files)} task files to process.")

    all_tasks = []
    ingestion_errors = []

    for file in task_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                task_post = frontmatter.load(f)

            # Create a copy of metadata for validation, as validation function modifies it
            # The validation function will ensure 'date_start' and 'date_end' are proper date objects
            temp_metadata_for_validation = task_post.metadata.copy()
            validation_issues = validate_task_data(temp_metadata_for_validation)

            # Apply the (potentially corrected) metadata back to the task_post
            task_post.metadata.update(temp_metadata_for_validation)

            if validation_issues:
                error_message = f"File: {file.name} | Validation Error: {validation_issues}"
                ingestion_errors.append(error_message)

            if 'vibe_id' not in task_post.metadata:
                new_id = str(uuid.uuid4())
                task_post.metadata['vibe_id'] = new_id
                task_obj = VibeTask(file, task_post.metadata, task_post.content)
                task_obj.is_dirty = True
            else:
                task_obj = VibeTask(file, task_post.metadata, task_post.content)

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
