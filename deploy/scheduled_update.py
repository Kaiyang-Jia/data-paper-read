"""Stage and publish the catalog and matching incremental vector index."""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
root = Path('/opt/datapaper')
state = Path('/var/lib/datapaper/update')
live = root / 'site/public/data/articles.json'
state.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='run-', dir=state) as temp:
    stage = Path(temp)
    for part in ('research', 'get_data'):
        shutil.copytree(root / part, stage / part, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (stage / 'site/public/data').mkdir(parents=True)
    shutil.copy2(live, stage / 'site/public/data/articles.json')
    (stage / 'backups').symlink_to(state / 'checkpoints', target_is_directory=True)
    (state / 'checkpoints').mkdir(exist_ok=True)
    (stage / '.env').symlink_to(root / '.env')
    before = json.loads(live.read_text(encoding='utf-8'))
    dates = [p.get('publishDate', '')[:10] for p in before['articles']]
    valid = []
    for value in dates:
        try: valid.append(date.fromisoformat(value))
        except (ValueError, TypeError): pass
    start = (max(valid) if valid else date.today() - timedelta(days=14)) - timedelta(days=7)
    end = date.today()
    os.environ['CROSSREF_MAX_PAGES'] = '100'
    program = '''
from pathlib import Path
from get_data.crossref_crawler import CrossrefCrawler
from research.refresh_snapshot import refresh
from research.abstract_backfill import backfill
from research.enrich_catalog import enrich
import sys
root=Path.cwd()
out=root/'backups'/('crossref_'+sys.argv[1]+'_'+sys.argv[2]+'.jsonl')
CrossrefCrawler().export_jsonl(out,sys.argv[1],sys.argv[2])
refresh(out)
snapshot=root/'site/public/data/articles.json'
backfill(snapshot,root/'backups/abstract_backfill_v1.jsonl',workers=3)
report=enrich(snapshot,root/'backups/chinese_cards_v1.jsonl',workers=3)
if report['failed']: raise RuntimeError('Chinese processing incomplete')
'''
    print(f'Updating Crossref {start} to {end}', flush=True)
    subprocess.run([sys.executable, '-c', program, str(start), str(end)], cwd=stage, check=True, env=os.environ.copy())
    updated = json.loads((stage / 'site/public/data/articles.json').read_text(encoding='utf-8'))
    if len(updated.get('articles', [])) < len(before['articles']):
        raise RuntimeError('Refusing to publish a smaller catalog')
    vector_root = Path('/var/lib/datapaper/vector')
    current = vector_root / 'current'
    old_index = os.readlink(current)
    new_index = Path(tempfile.mkdtemp(prefix='index-', dir=vector_root))
    index_program = '''
import json, sys
from get_data.faiss_store import LocalFaissStore
papers=json.load(open('site/public/data/articles.json',encoding='utf-8'))['articles']
count, changed=LocalFaissStore(sys.argv[1]).build_incremental(papers,LocalFaissStore())
if count != len(papers): raise RuntimeError('Index/catalog count mismatch')
print(f'Validated vector index: {count} papers, {changed} new vectors',flush=True)
'''
    try:
        subprocess.run([sys.executable, '-c', index_program, str(new_index)], cwd=stage, check=True, env=os.environ.copy())
    except Exception:
        shutil.rmtree(new_index)
        raise
    backup = state / ('published-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
    shutil.copy2(live, backup)
    pending = live.with_suffix('.publish.tmp')
    shutil.copy2(stage / 'site/public/data/articles.json', pending)
    new_link = vector_root / 'current.next'
    new_link.unlink(missing_ok=True)
    new_link.symlink_to(new_index, target_is_directory=True)
    os.replace(pending, live)
    try:
        os.replace(new_link, current)
        subprocess.run(['systemctl','restart','datapaper-api'], check=True)
        health = None
        for _ in range(30):
            try:
                with urllib.request.urlopen('http://127.0.0.1:5000/api/catalog/page?size=1', timeout=2) as response:
                    health = json.load(response)
                break
            except (OSError, ValueError):
                time.sleep(1)
        if not health or health['summary']['totalCount'] != len(updated['articles']):
            raise RuntimeError('Published catalog health check failed')
    except Exception:
        shutil.copy2(backup, pending)
        os.replace(pending, live)
        new_link.unlink(missing_ok=True)
        new_link.symlink_to(old_index, target_is_directory=True)
        os.replace(new_link, current)
        subprocess.run(['systemctl','restart','datapaper-api'], check=False)
        raise
    print(f'Published: {len(before["articles"])} -> {len(updated["articles"])} papers', flush=True)
