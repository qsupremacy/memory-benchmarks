import json, os
for f in sorted(os.listdir('results/locomo/predicted_volc-test')):
    if not f.endswith('.json'): continue
    d = json.load(open('results/locomo/predicted_volc-test/' + f))
    cr = d.get('cutoff_results', {})
    if not cr: continue
    a10 = cr.get('top_10', {}).get('generated_answer', '').strip()
    a200 = cr.get('top_200', {}).get('generated_answer', '').strip()
    if a10 and not a200:
          print(f"{d['question_id']} [{d['category_name']}] {d['question']}")
          print(f"  top_10: {a10[:60]}")
          print(f"  top_200: {empty}")
          print()
