"""End-to-end dashboard refresh:
1. Pull latest dailyReports
2. Rebuild per-view item rankings
3. Rebuild per-view payment breakdown
4. Swap inline DATA into KEK Dashboard.html
5. Verify JS runs clean

Usage: python3 refresh_dashboard.py
"""
import subprocess, sys, os, re, json

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.environ.get(
    'KEK_HTML',
    "/sessions/youthful-peaceful-faraday/mnt/Keng Eng Kee Seafood/KEK Dashboard.html",
)

print("Step 1: pull latest dailyReports...")
subprocess.run([sys.executable, f"{SCRIPTS}/pull_latest.py"], check=True)

print("\nStep 2: rebuild per-view item rankings...")
subprocess.run([sys.executable, f"{SCRIPTS}/build_per_view_items.py"], check=True)

print("\nStep 3: rebuild per-view payment breakdown...")
subprocess.run([sys.executable, f"{SCRIPTS}/build_payment_detail.py"], check=True)

print("\nStep 4: swap inline DATA into HTML...")
with open(HTML_PATH) as f: html = f.read()
with open(f'{SCRIPTS}/kek_dashboard_data.json') as f: new_data = f.read()
m = re.search(r'const DATA = \{', html)
start = m.start(); i = m.end() - 1; depth = 0
while i < len(html):
    if html[i] == '{': depth += 1
    elif html[i] == '}':
        depth -= 1
        if depth == 0: end = i + 1; break
    i += 1
if html[end] == ';': end += 1
html = html[:start] + f'const DATA = {new_data};' + html[end:]
with open(HTML_PATH, 'w') as f: f.write(html)
print(f"  HTML saved: {len(html):,} chars")

print("\nStep 5: verify JS...")
m2 = re.search(r'<script>\s*\n(const DATA.*?)</script>', html, re.DOTALL)
with open('/tmp/kek_test.js', 'w') as f:
    f.write('''
global.document = { getElementById: () => ({ textContent: '', innerHTML: '', classList: { toggle: () => {} } }), querySelector: () => ({ innerHTML: '', textContent: '' }) };
global.Chart = function() { this.destroy = () => {}; };
''')
    f.write(m2.group(1))
r = subprocess.run(['node', '/tmp/kek_test.js'], capture_output=True, text=True, timeout=10)
if r.stderr:
    print(f"  JS ERROR: {r.stderr[:500]}")
    sys.exit(1)
else:
    print("  JS OK")

print("\nAll done.")
