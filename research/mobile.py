"""Read-only mobile discovery over the shared Web catalog."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from flask import jsonify, request
from research.catalog import expand_terms


def mobile_date():
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


def register_mobile_api(app, load_catalog):
    @app.get('/api/miniprogram/feed')
    def mobile_feed():
        mode = request.args.get('mode', 'daily')
        if mode not in ('daily', 'search'):
            return jsonify(message='不支持的浏览方式。'), 400
        try:
            page = max(1, int(request.args.get('page', '1')))
        except ValueError:
            return jsonify(message='分页参数无效。'), 400
        query = request.args.get('q', '').strip()
        if len(query) > 100:
            return jsonify(message='搜索词请控制在100字以内。'), 400
        result = load_catalog()
        items = result['articles']
        day = mobile_date()
        if mode == 'daily':
            items = sorted(items[:120], key=lambda a: hashlib.sha256(
                (day + a['id']).encode('utf-8')).hexdigest())[:6]
        elif query:
            terms = expand_terms(query, [query.lower()])
            ranked = []
            for a in items:
                title = (a['title'] + ' ' + a['titleCn']).lower()
                body = ' '.join([a['abstract'], a['interpretationCn'], a['Subject'], a['journal'], ' '.join(a['tags'])]).lower()
                score = sum(6 if t.lower() in title else 1 if t.lower() in body else 0 for t in terms)
                if score:
                    ranked.append((score, a))
            items = [a for _, a in sorted(ranked, key=lambda pair: -pair[0])]
        start = (page - 1) * 12
        return jsonify(articles=items[start:start + 12], total=len(items),
                       hasMore=start + 12 < len(items), page=page, date=day, summary=result['summary'])

    @app.get('/api/miniprogram/article')
    def mobile_article():
        identity = request.args.get('id', '')
        if not identity or len(identity) > 1000:
            return jsonify(message='论文标识无效。'), 400
        for article in load_catalog()['articles']:
            if article['id'] == identity:
                return jsonify(article=article)
        return jsonify(message='这篇论文暂时不在当前目录中。'), 404

    @app.get('/api/miniprogram/updates')
    def mobile_updates():
        path = Path(__file__).with_name('project_updates.json')
        return jsonify(updates=json.loads(path.read_text(encoding='utf-8')))
