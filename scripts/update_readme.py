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

    # Find the dashboard block between markers
    pattern = r"(<!-- DASHBOARD_START -->\s*<pre>)(.*?)(</pre>\s*<!-- DASHBOARD_END -->)"
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print("Could not find the DASHBOARD markers in README.md to update.")
        return

    pre_prefix = match.group(1)
    inner_content = match.group(2)
    pre_suffix = match.group(3)

    lines = inner_content.splitlines()
    
    # Detect existing metrics position
    metrics_start_line = 1
    metrics_col = 52
    
    for idx, line in enumerate(lines):
        if "[ KAIZEN METRICS ]" in line:
            metrics_start_line = idx
            metrics_col = line.find("[ KAIZEN METRICS ]")
            break

    new_lines = []
    for i, line in enumerate(lines):
        if metrics_start_line <= i < metrics_start_line + len(dashboard_lines):
            # Update metrics portion
            m_idx = i - metrics_start_line
            # Preserve mountain part up to metrics_col
            mountain_part = line[:metrics_col].ljust(metrics_col)
            new_lines.append(mountain_part + dashboard_lines[m_idx])
        else:
            # Check if this is a line that might have leftover metrics from a previous bad run
            # (Only for lines immediately following the metrics block)
            if metrics_start_line + len(dashboard_lines) <= i < metrics_start_line + len(dashboard_lines) + 2:
                # Clear potential leftovers but keep the mountain
                new_lines.append(line[:metrics_col].rstrip())
            else:
                new_lines.append(line)

    new_inner_content = "\n".join(new_lines)
    # Ensure we don't lose the trailing newline if it was there
    if inner_content.endswith('\n') and not new_inner_content.endswith('\n'):
        new_inner_content += '\n'
        
    new_readme_content = content[:match.start()] + pre_prefix + new_inner_content + pre_suffix + content[match.end():]


    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(new_readme_content)
    
    print("README.md updated successfully.")

if __name__ == "__main__":
    update_readme()
