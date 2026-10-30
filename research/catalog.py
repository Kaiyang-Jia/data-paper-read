"""Normalize metadata and make the limits of paper-based evidence explicit."""
import re
from collections import Counter
from urllib.parse import urlparse


def normalize(article):
    item = dict(article)
    for field in ('title', 'titleCn', 'abstract', 'interpretationCn', 'doi', 'url',
                  'Subject', 'journal', 'authors', 'publishDate'):
        item[field] = str(item.get(field) or '').strip()
    item['doi'] = re.sub(r'^https?://(?:dx\.)?doi.org/', '', item['doi'], flags=re.I).lower()
    tags = item.get('tags') or []
    item['tags'] = [str(t).strip() for t in (tags if isinstance(tags, list) else re.split('[,，]', str(tags))) if str(t).strip()]
    item['id'] = item['doi'] or item['url'] or item['title'].lower()
    if urlparse(item['url']).scheme not in ('http', 'https'):
        item['url'] = ''
    item['evidenceStatus'] = 'abstract' if item['abstract'] else 'metadata-only'
    item['missingChecks'] = ['数据下载地址与可访问性', '数据使用许可', '研究对象与变量或内容', '样本、采集方式与学科条件']
    return item


def catalog(articles, source='memory'):
    unique = {}
    for article in articles:
        item = normalize(article)
        if item['id'] and item['id'] not in unique:
            unique[item['id']] = item
    items = sorted(unique.values(), key=lambda a: a['publishDate'], reverse=True)
    return {'articles': items, 'summary': {
        'totalCount': len(items), 'source': source,
        'latestPublishDate': max((a['publishDate'] for a in items), default=''),
        'subjects': sorted({a['Subject'] for a in items if a['Subject']}),
        'journals': sorted({a['journal'] for a in items if a['journal']}),
        'abstractCount': sum(bool(a['abstract']) for a in items),
        'translationCount': sum(bool(a['titleCn']) for a in items),
        'interpretationCount': sum(bool(a['interpretationCn']) for a in items),
        'chineseProcessedAt': max((a.get('chineseProcessing', {}).get('generatedAt', '') for a in items if isinstance(a.get('chineseProcessing'), dict)), default=''),
        'doiCount': sum(bool(a['doi']) for a in items),
        'subjectCounts': dict(Counter(a['Subject'] for a in items if a['Subject'])),
    }}


# Transparent query expansion for common research domains; not model inference.
CONCEPTS = {
    '城市': ['urban', 'city', 'cities'], '热岛': ['heat island', 'temperature'],
    '气候': ['climate', 'climatic'], '遥感': ['remote sensing', 'satellite'],
    '土地': ['land use', 'land cover'], '碳排放': ['carbon', 'emission'],
    '人口': ['population'], '水文': ['hydrolog', 'streamflow', 'river'],
    '河流': ['river', 'streamflow'], '中国': ['china', 'chinese'],
    '生态': ['ecolog', 'ecosystem'], '生物多样性': ['biodiversity', 'species'],
    '农业': ['agricultur', 'crop'], '蛋白质': ['protein'], '基因': ['gene', 'genom'],
    '海洋': ['ocean', 'marine'], '污染': ['pollution', 'pollutant'],
    '降水': ['precipitation', 'rainfall'], '土壤': ['soil'], '机器学习': ['machine learning'],
}


def expand_terms(query, base_terms):
    terms = list(base_terms)
    for word, english in CONCEPTS.items():
        if word in query:
            terms.extend(english)
    return list(dict.fromkeys(terms))


def evidence(article, terms):
    """Only return verbatim source snippets; never infer dataset suitability."""
    for field in ('abstract', 'title'):
        value = str(article.get(field) or '')
        for sentence in re.split(r'(?<=[.!?。])\s+', value):
            if any(term.lower() in sentence.lower() for term in terms):
                return {'field': field, 'text': sentence[:650]}
    return {'field': 'title', 'text': str(article.get('title') or '')[:650]}
