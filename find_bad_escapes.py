# find_bad_escapes.py
# Place at repo root and run: python find_bad_escapes.py
# This script searches for likely problematic backslash escape sequences
# (like '\U') in common text/code files and prints filename + line numbers.

import os
import fnmatch
import sys

ROOT = os.path.abspath(os.path.dirname(__file__))

# File patterns to check
patterns = ["*.py", "*.txt", "*.md", "*.env", "Dockerfile", "*.yml", "*.yaml", "*.ini", "*.json"]

# suspicious substrings to search for (raw)
suspicious = [
    "\\U",  # unicode escape start
    "\\u",  # unicode escape
    "C:\\\\Users",  # literal C:\Users (escaped for Python)
    "C:\\Users",     # plain C:\Users
    "\\\\",          # any double backslash occurrences
    "\\n", "\\t",    # not always problematic but list them
]

# Also check string-like contexts with single/double quotes
def search_file(path):
    results = []
    try:
        with open(path, "r", errors="replace") as f:
            for i, line in enumerate(f, start=1):
                for token in suspicious:
                    if token in line:
                        results.append((i, line.rstrip("\n")))
                        break
    except Exception as e:
        # skip binary
        return []
    return results

matches = {}
for dirpath, dirnames, filenames in os.walk(ROOT):
    # skip virtual env folders and .git
    if any(part in (".git", ".venv", "venv", "__pycache__") for part in dirpath.split(os.sep)):
        continue
    for pat in patterns:
        for filename in fnmatch.filter(filenames, pat):
            path = os.path.join(dirpath, filename)
            res = search_file(path)
            if res:
                matches[path] = res
    # check Dockerfile explicitly
    if "Dockerfile" in filenames:
        path = os.path.join(dirpath, "Dockerfile")
        res = search_file(path)
        if res:
            matches[path] = res

if not matches:
    print("No suspicious backslash patterns found in scanned files.")
    sys.exit(0)

print("Found suspicious patterns in the following files (line: content):\n")
for path, hits in matches.items():
    print("----", path)
    for lineno, content in hits:
        # show with escaped backslashes visible
        print(f"{lineno}: {content}")
    print()
