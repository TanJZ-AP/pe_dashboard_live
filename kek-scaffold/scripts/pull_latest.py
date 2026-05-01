"""Scan Daily POS Reports folder for any new dates and merge them.

Usage:
    python3 pull_latest.py

Picks up any individual dailyReport file not yet in kek_parsed.json,
parses it, and refreshes kek_dashboard_data.json.

Does NOT update top20_by_view, top10_wib_by_view, or payment_by_view —
run build_per_view_items.py and build_payment_detail.py after this for
full refresh.
"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_kek import parse_daily, identify_outlet
from _dates import period_label

KEK_DIR = os.environ.get('KEK_DIR', "/sessions/youthful-peaceful-faraday/mnt/Daily POS Reports")
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
OUTLETS = ['KEK Alexandra', 'KEK Tampines', 'KEK Punggol', 'WOKIN Punggol']
SHORT = {'KEK Alexandra': 'BM', 'KEK Tampines': 'TP', 'KEK Punggol': 'PG', 'WOKIN Punggol': 'WIB'}

with open(f'{SCRIPTS}/kek_parsed.json') as f:
    parsed = json.load(f)
DAILY = parsed['daily']

new_count = 0
for f in sorted(os.listdir(KEK_DIR)):
    if 'dailyReport' not in f: continue
    outlet = identify_outlet(f)
    if not outlet: continue
    m = re.search(r'(\d{4}-\d{2}-\d{2})', f)
    if not m: continue
    date = m.group(1)
    if date in DAILY.get(outlet, {}): continue
    try:
        data = parse_daily(os.path.join(KEK_DIR, f))
        DAILY.setdefault(outlet, {})[date] = data
        print(f"+ {outlet} {date}: net=${data['net_sales']:,.2f}")
        new_count += 1
    except Exception as e:
        print(f"  ERROR {f}: {e}")

if new_count == 0:
    print("No new dailyReports to merge.")
    sys.exit(0)

parsed['daily'] = DAILY
with open(f'{SCRIPTS}/kek_parsed.json', 'w') as f:
    json.dump(parsed, f, default=str, indent=2, ensure_ascii=False)

# Update kek_dashboard_data.json daily structure
with open(f'{SCRIPTS}/kek_dashboard_data.json') as f:
    dash = json.load(f)
all_dates = sorted(set(d for o in DAILY for d in DAILY[o].keys()))
daily_by_date = {date: {SHORT[o]: DAILY.get(o, {}).get(date) for o in OUTLETS} for date in all_dates}
dash['all_dates'] = all_dates
dash['daily'] = daily_by_date
dash['period_label'] = period_label(all_dates[-1])
with open(f'{SCRIPTS}/kek_dashboard_data.json', 'w') as f:
    json.dump(dash, f, indent=2, ensure_ascii=False)

print(f"\nMerged {new_count} new dailyReports. Run build_per_view_items.py and build_payment_detail.py to refresh derived views.")
