import frontmatter

# Path to a specific file that is known to be causing issues
file_path = r"C:\Users\mkempton\Documents\CODEX\40-PROJECTS\23-0510_Nine Tribes\Task Sheets\610 - PD Clean UP.md"

print(f"Attempting to load file: {file_path}")

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        task_post = frontmatter.load(f)

    print("\n--- File Loaded Successfully ---")
    print("\nMetadata:")
    print(task_post.metadata)

    print("\nContent:")
    print(task_post.content)

except Exception as e:
    print(f"\n--- An Error Occurred ---")
    print(f"Error: {e}")
