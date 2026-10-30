"""Fill missing abstracts from DOI-verified publisher sections or Europe PMC records."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import threading
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from research.catalog import catalog

ROOT = Path(__file__).resolve().parent.parent
REVISION = 'abstract-source-v1'
EPMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search'


def doi_key(value):
    return re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', str(value or '').strip(), flags=re.I).lower().strip()


def is_notice(paper):
    return bool(re.match(r'^(?:(?:publisher|author)\s+)?(?:correction|corrigendum|erratum|retraction)\s*:', paper.get('title', ''), re.I))


def clean_abstract(text):
    text = re.sub(r'\s+', ' ', BeautifulSoup(text or '', 'html.parser').get_text(' ', strip=True)).strip()
    text = re.sub(r'^Abstract\s*[:.]?\s+', '', text, flags=re.I)
    if not 80 <= len(text) <= 30000:
        return ''
    if any(term in text.lower() for term in ('enable javascript', 'verify you are human', 'access denied', 'checking your browser')):
        return ''
    return text


def publisher_url(doi):
    match = re.fullmatch(r'10\.1038/(s41597-[a-z0-9-]+)', doi)
    if match:
        return f'https://www.nature.com/articles/{match[1]}'
    match = re.fullmatch(r'10\.5194/essd-(\d+)-(\d+)-(\d{4})', doi)
    if match:
        return f'https://essd.copernicus.org/articles/{match[1]}/{match[2]}/{match[3]}/'
    return None


def publisher_abstract(html, doi):
    soup = BeautifulSoup(html, 'html.parser')
    identifiers = []
    for meta in soup.find_all('meta'):
        name = str(meta.get('name') or meta.get('property') or '').lower()
        if name in ('citation_doi', 'dc.identifier', 'dc.identifier.doi', 'prism.doi'):
            identifiers.append(doi_key(meta.get('content')))
    if doi not in identifiers:
        return '', 'publisher-doi-not-confirmed'
    # Only explicit abstract sections; generic description/SEO text is not an abstract.
    for selector in ('div#Abs1-content', 'section[data-title="Abstract"]', 'div.abstract', 'div.abstract-content'):
        elements = soup.select(selector)
        if elements:
            paragraphs = elements[0].find_all('p')
            text = ' '.join(p.get_text(' ', strip=True) for p in paragraphs) if paragraphs else elements[0].get_text(' ', strip=True)
            abstract = clean_abstract(text)
            if abstract:
                return abstract, selector
    meta = soup.find('meta', attrs={'name': 'citation_abstract'})
    if meta:
        return clean_abstract(meta.get('content', '')), 'citation_abstract'
    return '', 'publisher-abstract-not-found'


def europepmc_abstract(payload, doi):
    for record in payload.get('resultList', {}).get('result', []):
        if doi_key(record.get('doi')) != doi:
            continue
        abstract = clean_abstract(record.get('abstractText', ''))
        if abstract:
            return abstract, str(record.get('id', '')), str(record.get('source', ''))
    return '', '', ''


class Sources:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_request = {}
        self.blocked = set()

    def get(self, url, **kwargs):
        # Retry a transient connection failure once, but never retry an access block.
        for attempt in range(2):
            try:
                return self._get_once(url, **kwargs)
            except (requests.ConnectionError, requests.Timeout):
                if attempt:
                    raise
                time.sleep(1)

    def _get_once(self, url, **kwargs):
        host = urlparse(url).netloc
        # At most two requests/second per host across the batch. No retries on blocks.
        with self.lock:
            if host in self.blocked:
                raise RuntimeError('source-paused-after-rate-limit-or-access-block')
            wait = 0.5 - (time.monotonic() - self.last_request.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            self.last_request[host] = time.monotonic()
        response = requests.get(url, timeout=(8, 22), headers={'User-Agent': 'DataPaper/1.0 (research abstract metadata)'}, **kwargs)
        if response.status_code in (403, 429):
            with self.lock:
                self.blocked.add(host)
        return response

    def fetch(self, paper):
        doi = doi_key(paper.get('doi'))
        attempts = []
        timestamp = datetime.now(timezone.utc).isoformat()
        if is_notice(paper):
            return {'doi': doi, 'status': 'not-applicable', 'reason': 'correction-or-retraction-notice', 'checkedAt': timestamp}
        if not re.fullmatch(r'10\.\d{4,9}/[^\s"<>]+', doi):
            return {'doi': doi, 'status': 'unresolved', 'reason': 'invalid-doi', 'checkedAt': timestamp}
        url = publisher_url(doi)
        if url:
            try:
                response = self.get(url)
                if response.status_code == 200 and urlparse(response.url).netloc == urlparse(url).netloc:
                    abstract, selector = publisher_abstract(response.text, doi)
                    if abstract:
                        return self.result(doi, abstract, 'publisher', response.url, selector, timestamp)
                    attempts.append(selector)
                else:
                    attempts.append(f'publisher-http-{response.status_code}')
            except (requests.RequestException, RuntimeError) as error:
                attempts.append('publisher-' + type(error).__name__)
        try:
            response = self.get(EPMC, params={'query': f'DOI:"{doi}"', 'format': 'json', 'resultType': 'core', 'pageSize': 3})
            if response.status_code == 200:
                abstract, record_id, record_source = europepmc_abstract(response.json(), doi)
                if abstract:
                    result = self.result(doi, abstract, 'europe-pmc', response.url, 'abstractText', timestamp)
                    result['abstractSource'].update({'recordId': record_id, 'recordSource': record_source})
                    return result
                attempts.append('europe-pmc-abstract-not-found-for-exact-doi')
            else:
                attempts.append(f'europe-pmc-http-{response.status_code}')
        except (requests.RequestException, ValueError, RuntimeError) as error:
            attempts.append('europe-pmc-' + type(error).__name__)
        return {'doi': doi, 'status': 'unresolved', 'attempts': attempts, 'checkedAt': timestamp}

    @staticmethod
    def result(doi, abstract, provider, url, selector, timestamp):
        return {'doi': doi, 'status': 'retrieved', 'abstract': abstract, 'checkedAt': timestamp,
                'abstractSource': {'provider': provider, 'url': url, 'doi': doi, 'retrievedAt': timestamp,
                                   'method': selector, 'sha256': hashlib.sha256(abstract.encode()).hexdigest(),
                                   'revision': REVISION, 'status': 'source-retrieved'}}


def backfill(snapshot, checkpoint, workers=3, limit=None, publish=True):
    raw = snapshot.read_bytes()
    original = json.loads(raw)
    papers = original['articles']
    cache = {}
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding='utf-8').splitlines():
            try:
                item = json.loads(line)
                # Only successful, exact-DOI, hash-checked records can be reused.
                source = item.get('abstractSource', {})
                abstract = item.get('abstract', '')
                if item.get('status') == 'retrieved' and clean_abstract(abstract) and source.get('revision') == REVISION and source.get('doi') == item.get('doi') and source.get('sha256') == hashlib.sha256(abstract.encode()).hexdigest():
                    cache[item['doi']] = item
            except (ValueError, KeyError, TypeError):
                continue
    missing = [p for p in papers if not str(p.get('abstract') or '').strip()]
    targets = missing if limit is None else missing[:limit]
    sources = Sources()
    outcomes = []
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    def fetch(paper):
        return cache.get(doi_key(paper.get('doi'))) or sources.fetch(paper)
    print(json.dumps({'missing': len(missing), 'targets': len(targets)}, ensure_ascii=False), flush=True)
    with checkpoint.open('a', encoding='utf-8') as out, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, paper): paper for paper in targets}
        for done, future in enumerate(as_completed(futures), 1):
            paper = futures[future]
            result = future.result()
            outcomes.append(result)
            out.write(json.dumps(result, ensure_ascii=False) + '\n')
            out.flush()
            paper['abstractRetrieval'] = {k: v for k, v in result.items() if k not in ('abstract', 'abstractSource')}
            if result['status'] == 'retrieved':
                paper['abstract'] = result['abstract']
                paper['abstractSource'] = result['abstractSource']
            if done % 25 == 0 or done == len(futures):
                print(json.dumps({'checked': done, 'total': len(targets), 'recovered': sum(r['status'] == 'retrieved' for r in outcomes)}, ensure_ascii=False), flush=True)
    report = {'missingBefore': len(missing), 'checked': len(targets), 'recovered': sum(r['status'] == 'retrieved' for r in outcomes),
              'notApplicable': sum(r['status'] == 'not-applicable' for r in outcomes), 'unresolved': [r for r in outcomes if r['status'] == 'unresolved'],
              'abstractCount': sum(bool(p.get('abstract')) for p in papers), 'totalCount': len(papers), 'completedAt': datetime.now(timezone.utc).isoformat()}
    checkpoint.with_suffix('.report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if publish and targets:
        if snapshot.read_bytes() != raw:
            raise RuntimeError('补摘要期间目录被修改；结果已存检查点，请重新合并')
        backup = ROOT / 'backups' / f"before_abstracts_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}.json"
        backup.parent.mkdir(exist_ok=True)
        shutil.copy2(snapshot, backup)
        result = catalog(papers, source='snapshot')
        result['summary'] = {**original.get('summary', {}), **result['summary'], 'abstractBackfilledAt': report['completedAt']}
        temporary = snapshot.with_suffix('.abstracts.tmp')
        temporary.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        temporary.replace(snapshot)
    print(json.dumps({**report, 'unresolved': len(report['unresolved'])}, ensure_ascii=False), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=ROOT / 'site/public/data/articles.json')
    parser.add_argument('--checkpoint', type=Path, default=ROOT / 'backups/abstract_backfill_v1.jsonl')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=3)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--no-publish', action='store_true')
    args = parser.parse_args()
    backfill(args.catalog, args.checkpoint, args.workers, args.limit, not args.no_publish)
