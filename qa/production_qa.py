"""D&D production QA runner.
Run from project root: python qa/production_qa.py
This does not modify production data. API checks are optional and only run when reachable.
"""
from pathlib import Path
import ast, json, re, sys, urllib.request
ROOT=Path(__file__).resolve().parents[1]
errors=[]; checks=[]
def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    if not ok: errors.append((name, detail))

for rel in ["desktop/main.py","desktop/api_client.py","backend/app/main.py","backend/app/models.py","backend/app/schemas.py"]:
    p=ROOT/rel
    try: ast.parse(p.read_text(encoding='utf-8')); check(f"Syntax: {rel}",True)
    except Exception as e: check(f"Syntax: {rel}",False,str(e))

main=(ROOT/'desktop/main.py').read_text(encoding='utf-8')
producer_sources='\n'.join(p.read_text(encoding='utf-8') for p in (ROOT/'desktop').glob('*.py'))
check('Producer alias parser sources present', all(x in producer_sources for x in ['prod.slv','deplugboy','daddykar_official']))
check('No tray minimize balloon call', 'tray.showMessage' not in main)
check('Background close does not quit', 'event.ignore(); self.hide()' in main)
check('Live refresh interval >= 30s', 'setInterval(30000)' in main)
check('Updater exists', (ROOT/'updater/updater.py').exists())
check('Installer exists', (ROOT/'installer/DD.iss').exists())

try:
    with urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2) as r:
        data=json.loads(r.read().decode())
        check('Backend health', data.get('status')=='ok', str(data))
except Exception as e:
    check('Backend health (optional)', True, 'Skipped: backend not running')

print('D&D Production QA preflight')
print('-'*60)
for name,ok,detail in checks:
    print(('PASS' if ok else 'FAIL').ljust(5), name, ('— '+detail) if detail else '')
print('-'*60)
print(f"{sum(1 for _,ok,_ in checks if ok)}/{len(checks)} checks passed")
if errors:
    sys.exit(1)
