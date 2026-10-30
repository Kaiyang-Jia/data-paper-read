"""Cross-disciplinary conditions. Only reviewed, sourced attributes are compared."""
import json
import math
from pathlib import Path
from urllib.parse import urlparse

FRAMEWORK_PATH = Path(__file__).resolve().parent.parent / 'site/public/data/requirements-framework.json'
FRAMEWORK = json.loads(FRAMEWORK_PATH.read_text(encoding='utf-8'))
FIELDS = {f['id']: f for f in FRAMEWORK['common']}
DOMAIN_FIELDS = {}
for domain in FRAMEWORK['domains']:
    DOMAIN_FIELDS[domain['id']] = {f['id'] for f in domain['fields']}
    FIELDS.update({f['id']: f for f in domain['fields']})


def definition(field):
    if field in FIELDS:
        return FIELDS[field]
    if isinstance(field, str) and field.startswith('custom:') and 0 < len(field[7:]) <= 60:
        return {'id': field, 'label': field[7:], 'type': 'set', 'operator': 'includes_all'}
    raise ValueError('条件包含未支持的属性')


def valid_value(value, kind):
    if kind == 'set':
        return (isinstance(value, list) and 0 < len(value) <= 12
                and all(isinstance(v, str) and 0 < len(v.strip()) <= 120 for v in value))
    if kind == 'number':
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
    if kind == 'range':
        return (isinstance(value, list) and len(value) == 2
                and all(isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 9999 for v in value)
                and value[0] <= value[1])
    return False


def validate_requirements(payload):
    if payload is None:
        payload = {}
    if not isinstance(payload, dict) or payload.get('version', '1.0') != FRAMEWORK['version']:
        raise ValueError('需求框架版本或格式不正确')
    domains = payload.get('domains', [])
    conditions = payload.get('conditions', [])
    if not isinstance(domains, list) or len(domains) > len(DOMAIN_FIELDS) or any(not isinstance(d, str) or d not in DOMAIN_FIELDS for d in domains):
        raise ValueError('请选择支持的学科模板')
    if not isinstance(conditions, list) or len(conditions) > 32:
        raise ValueError('最多提交32项条件')
    allowed = {f['id'] for f in FRAMEWORK['common']}
    for domain in domains:
        allowed.update(DOMAIN_FIELDS[domain])
    normalized, seen = [], set()
    for condition in conditions:
        if not isinstance(condition, dict) or not isinstance(condition.get('field'), str):
            raise ValueError('条件格式不正确')
        field = condition['field']
        spec = definition(field)
        if field not in allowed and not field.startswith('custom:'):
            raise ValueError('条件不属于已选学科模板')
        if field in seen:
            raise ValueError('属性条件不能重复')
        seen.add(field)
        priority = condition.get('priority', 'required')
        value = condition.get('value')
        if priority not in ('required', 'preferred') or not valid_value(value, spec['type']):
            raise ValueError(f"{spec['label']}的条件值或优先级不正确")
        if spec['type'] == 'set':
            value = list(dict.fromkeys(v.strip() for v in value))
        normalized.append({'field': field, 'priority': priority, 'value': value})
    return {'version': FRAMEWORK['version'], 'domains': list(dict.fromkeys(domains)), 'conditions': normalized}


def compare_condition(condition, fact):
    spec = definition(condition['field'])
    result = {**condition, 'label': spec['label'], 'unit': spec.get('unit', ''),
              'status': 'unknown', 'reason': '尚无可用于判断的核验属性'}
    if not isinstance(fact, dict):
        return result
    source = fact.get('source')
    source_url = urlparse(str(source.get('url', ''))) if isinstance(source, dict) else None
    if not isinstance(source, dict) or source_url.scheme not in ('https', 'http') or not source_url.netloc or not isinstance(source.get('quote'), str) or not source['quote'].strip():
        result['reason'] = '属性缺少可追溯的来源与原文证据'
        return result
    if fact.get('status') not in ('reviewed', 'file-checked') or not isinstance(fact.get('checkedAt'), str) or not fact['checkedAt'].strip():
        result['reason'] = '已有属性线索，尚未经复核'
        return result
    result['source'] = {'url': source['url'], 'quote': source['quote'], 'checkedAt': fact['checkedAt'], 'status': fact['status']}
    value = fact.get('value')
    if not valid_value(value, spec['type']):
        result['reason'] = '属性值缺失或类型不符合框架'
        return result
    if spec.get('unit') and fact.get('unit') != spec['unit']:
        result['reason'] = '单位不一致，尚未核对转换关系'
        return result
    result['actual'] = value
    expected = condition['value']
    operator = spec['operator']
    if spec['type'] == 'set':
        wanted = {v.strip().casefold() for v in expected}
        actual = {v.strip().casefold() for v in value}
        passed = wanted <= actual if operator == 'includes_all' else bool(wanted & actual)
        if not passed and fact.get('complete') is not True:
            result['reason'] = '已记录属性未命中条件，但取值是否完整尚不明确'
            return result
    elif spec['type'] == 'number':
        passed = value >= expected if operator == 'at_least' else value <= expected
    else:
        passed = value[0] <= expected[0] and value[1] >= expected[1]
        if passed and fact.get('coverage') != 'continuous':
            result['reason'] = '年份端点覆盖需求，但区间内是否连续完整尚未核验'
            return result
    result['status'] = 'match' if passed else 'mismatch'
    result['reason'] = '已核验属性满足此项条件' if passed else '已核验属性不满足此项条件'
    return result


def assess_requirements(requirements, profile=None):
    attributes = profile.get('attributes', {}) if isinstance(profile, dict) else {}
    if not isinstance(attributes, dict):
        attributes = {}
    results = [compare_condition(c, attributes.get(c['field'])) for c in requirements['conditions']]
    required = [r for r in results if r['priority'] == 'required']
    status = ('not-assessed' if not required else 'mismatch' if any(r['status'] == 'mismatch' for r in required)
              else 'unknown' if any(r['status'] == 'unknown' for r in required) else 'match')
    return {'version': FRAMEWORK['version'], 'status': status, 'conditions': results,
            'note': '只判断已填写条件；不代表全部数据质量、可下载性或研究适用性已验证。'}


def describe_requirements(requirements):
    return '\n'.join(f"{definition(c['field'])['label']}（{'必须' if c['priority'] == 'required' else '偏好'}）：{c['value']}" for c in requirements['conditions'])
