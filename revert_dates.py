import os
import re

def revert_date_format_in_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Regex to find date_start and date_end fields with MM/DD/YYYY format
    # and replace with YYYY-MM-DD format
    content = re.sub(r"(date_start:\s*)(\d{2})/(\d{2})/(\d{4})", r"\1\4-\2-\3", content)
    content = re.sub(r"(date_end:\s*)(\d{2})/(\d{2})/(\d{4})", r"\1\4-\2-\3", content)

    with open(file_path, 'w') as f:
        f.write(content)

def process_directory(directory_path):
    for filename in os.listdir(directory_path):
        if filename.endswith(".md"):
            file_path = os.path.join(directory_path, filename)
            revert_date_format_in_file(file_path)
            print(f"Processed {filename}")

if __name__ == "__main__":
    target_directory = r"C:\Users\mkempton\Documents\CODEX\40-PROJECTS"
    for root, dirs, files in os.walk(target_directory):
        if "Task Sheets" in dirs:
            task_sheets_path = os.path.join(root, "Task Sheets")
            process_directory(task_sheets_path)
