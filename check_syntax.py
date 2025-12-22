import ast
import os
import sys

def check_syntax(directory):
    print(f"Checking syntax in {directory}...")
    failed = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        source = f.read()
                    ast.parse(source)
                except SyntaxError as e:
                    print(f"❌ Syntax Error in {path}: {e}")
                    failed.append(path)
                except Exception as e:
                    print(f"❌ Error reading {path}: {e}")
                    failed.append(path)
    
    if not failed:
        print("✅ No syntax errors found.")
    else:
        print(f"❌ Found errors in {len(failed)} files.")

if __name__ == "__main__":
    check_syntax("cogs")
