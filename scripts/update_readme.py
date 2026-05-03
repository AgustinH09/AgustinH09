import json
import os
import re

def generate_bar(percent, length=10):
    percent = min(max(percent, 0), 100)
    filled = int(length * percent / 100)
    return "█" * filled + "░" * (length - filled)

def update_readme():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    metrics_path = os.path.join(root_dir, 'metrics.json')
    readme_path = os.path.join(root_dir, 'README.md')
    
    # Default values for testing
    streak = 12
    total = 1200
    
    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, 'r') as f:
                data = json.load(f)
                streak = data.get('computed', {}).get('commits', {}).get('streak', {}).get('current', streak)
                total = data.get('computed', {}).get('commits', {}).get('total', total)
        except Exception as e:
            print(f"Error reading metrics.json: {e}")

    dashboard_lines = [
        "[ KAIZEN METRICS ]",
        "------------------",
        f"CONSISTENCY  [{generate_bar(80)}] {streak}d Streak",
        f"VOLUME       [{generate_bar(100)}] {total}+ Total",
        "INTENSITY    [██████░░░░] TS/Rails"
    ]

    if not os.path.exists(readme_path):
        print(f"README.md not found at {readme_path}")
        return

    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the Metrics pre block inside the table
    # We look for [ KAIZEN METRICS ] inside a <pre> tag
    pattern = r"(<td[^>]*>\s*<pre>\s*)\[ KAIZEN METRICS \].*?(\s*</pre>\s*</td>)"
    
    new_metrics_content = "\n".join(dashboard_lines)
    
    # Use re.DOTALL to match across newlines
    new_readme_content = re.sub(pattern, rf"\1{new_metrics_content}\2", content, flags=re.DOTALL)
    
    if new_readme_content == content:
        print("Could not find the Metrics block in README.md to update.")
        return

    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(new_readme_content)
    
    print("README.md updated successfully.")

if __name__ == "__main__":
    update_readme()
