import os

def check_and_fix_admin_py(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    lines = content.splitlines()
    clean_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
    
    modified = False
    
    # Check for only "from django.contrib import admin"
    # This specifically looks for the case where only this import exists.
    if len(clean_lines) == 1 and clean_lines[0].strip() == "from django.contrib import admin":
        print(f"Fixing unused import in: {file_path}")
        # Replace with a comment or just clear it. 
        # The user mentioned they want to avoid the "only line" issue.
        # Let's use a standard comment.
        content = "# Admin registration for apps"
        modified = True
    
    # Check for extra newlines at end (W391)
    # W391: blank line at end of file.
    # We want exactly one newline at the end.
    if content.endswith("\n\n"):
        print(f"Fixing extra newlines (W391) in: {file_path}")
        content = content.rstrip() + "\n"
        modified = True
    elif content.strip() != "" and not content.endswith("\n"):
        # W292: no newline at end of file. Let's fix that too while we are at it.
        print(f"Fixing missing newline in: {file_path}")
        content = content.rstrip() + "\n"
        modified = True

    if modified:
        with open(file_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        return True
    return False

root = "services"
for dirpath, dirnames, filenames in os.walk(root):
    for filename in filenames:
        if filename == "admin.py":
            full_path = os.path.join(dirpath, filename)
            check_and_fix_admin_py(full_path)
