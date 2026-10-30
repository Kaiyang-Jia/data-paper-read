"""Merge a Crossref JSONL export into the authentic catalog without erasing enrichment."""
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from research.catalog import catalog, normalize

ROOT = Path(__file__).resolve().parent.parent


def refresh(path):
    snapshot = ROOT / 'site/public/data/articles.json'
    before = json.loads(snapshot.read_text(encoding='utf-8'))
    records = {normalize(p)['id']: p for p in before['articles']}
    existing = set(records)
    fetched = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    for paper in fetched:
        key = normalize(paper)['id']
        if not key or not paper.get('title'):
            continue
        if key in records:
            # Preserve original/curated non-empty fields, fill only actual gaps.
            for field, value in paper.items():
                if value and not records[key].get(field):
                    records[key][field] = value
        else:
            records[key] = paper
    result = catalog(records.values(), source='snapshot')
    result['summary'].update({'generatedAt': datetime.now(timezone.utc).isoformat(), 'crossrefFetched':len(fetched), 'newCount':len(set(records)-existing), 'updateInput':path.name, 'interpretationCount':sum(bool(p.get('interpretationCn')) for p in result['articles'])})
    backup = ROOT / 'backups' / f"snapshot_before_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    backup.parent.mkdir(exist_ok=True)
    shutil.copy2(snapshot, backup)
    temp = snapshot.with_suffix('.json.tmp')
    temp.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    temp.replace(snapshot)
    print(json.dumps(result['summary'],ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('jsonl',type=Path)
    args = parser.parse_args()
    refresh(args.jsonl)
