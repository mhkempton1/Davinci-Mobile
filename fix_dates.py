

import os
import re

def fix_date_format_in_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Regex to find date_start and date_end fields with YYYY-MM-DD format
    # and replace with MM/DD/YYYY format
    content = re.sub(r"(date_start:\s*)(\d{4})-(\d{2})-(\d{2})", r"\1\3/\4/\2", content)
    content = re.sub(r"(date_end:\s*)(\d{4})-(\d{2})-(\d{2})", r"\1\3/\4/\2", content)

    with open(file_path, 'w') as f:
        f.write(content)

def process_directory(directory_path):
    for filename in os.listdir(directory_path):
        if filename.endswith(".md"):
            file_path = os.path.join(directory_path, filename)
            fix_date_format_in_file(file_path)
            print(f"Processed {filename}")

if __name__ == "__main__":
    target_directory = "C:\\Users\\mkempton\\Documents\\CODEX\\40-PROJECTS"
    for root, dirs, files in os.walk(target_directory):
        if "Task Sheets" in dirs:
            task_sheets_path = os.path.join(root, "Task Sheets")
            process_directory(task_sheets_path)
