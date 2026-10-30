"""Synthetic fixtures test decisions; they are not real dataset attributes."""
import unittest
from unittest.mock import patch
import app as server
from research.requirements import FRAMEWORK, FIELDS, validate_requirements, assess_requirements


def requirement(field='medicine.participants', value=100, priority='required', domains=None):
    return validate_requirements({'domains': domains or ['medicine'], 'conditions': [{'field': field, 'value': value, 'priority': priority}]})


def fact(value, **changes):
    return {'value': value, 'unit': '人', 'status': 'reviewed', 'checkedAt': '2026-10-02',
            'source': {'url': 'https://example.org/dataset', 'quote': 'Synthetic test evidence.'}, **changes}


def assess(req, attributes):
    return assess_requirements(req, {'attributes': attributes})


class RequirementsTest(unittest.TestCase):
    def test_defaults_do_not_select_geography(self):
        self.assertEqual(validate_requirements(None)['domains'], [])
        self.assertEqual(assess_requirements(validate_requirements(None))['status'], 'not-assessed')
        self.assertEqual(len(FRAMEWORK['common']), 7)
        self.assertEqual(len(FRAMEWORK['domains']), 6)

    def test_each_domain_accepts_its_typed_conditions(self):
        values = {'set': ['test'], 'number': 100, 'range': [2010, 2022]}
        for domain in FRAMEWORK['domains']:
            conditions = [{'field': f['id'], 'value': values[f['type']]} for f in domain['fields']]
            req = validate_requirements({'domains': [domain['id']], 'conditions': conditions})
            self.assertEqual(len(req['conditions']), len(conditions))
            attrs = {c['field']: fact(c['value'], unit=FIELDS[c['field']].get('unit', ''), coverage='continuous') for c in req['conditions']}
            self.assertEqual(assess(req, attrs)['status'], 'match')

    def test_wrong_template_invalid_numbers_and_duplicate_fields_rejected(self):
        invalid = [{'domains': [], 'conditions': [{'field': 'medicine.participants', 'value': 100}]},
                   {'domains': ['medicine'], 'conditions': [{'field': 'medicine.participants', 'value': True}]},
                   {'domains': ['medicine'], 'conditions': [{'field': 'medicine.participants', 'value': -1}]},
                   {'conditions': [{'field': 'format', 'value': ['CSV']}] * 2},
                   {'version': '9.0'}, {'domains': [{}]}]
        for payload in invalid:
            with self.assertRaises(ValueError): validate_requirements(payload)

    def test_numeric_threshold_and_units(self):
        req = requirement()
        self.assertEqual(assess(req, {'medicine.participants': fact(100)})['status'], 'match')
        self.assertEqual(assess(req, {'medicine.participants': fact(99)})['status'], 'mismatch')
        self.assertEqual(assess(req, {'medicine.participants': fact(100, unit='条记录')})['status'], 'unknown')
        req = requirement('geospatial.resolution_m', 30, domains=['geospatial'])
        self.assertEqual(assess(req, {'geospatial.resolution_m': fact(10, unit='米')})['status'], 'match')

    def test_missing_unreviewed_and_unsourced_facts_are_unknown(self):
        req = requirement()
        for attrs in ({}, {'medicine.participants': fact(200, status='source-backed')},
                      {'medicine.participants': fact(200, checkedAt='')},
                      {'medicine.participants': fact(200, source={'url': 'https://example.org', 'quote': ''})},
                      {'medicine.participants': fact(200, source={'url': 'http:missing-host', 'quote': 'test'})}):
            self.assertEqual(assess(req, attrs)['status'], 'unknown')

    def test_partial_set_cannot_prove_absence(self):
        req = requirement('variables', ['age', 'income'], domains=['social'])
        attrs = {'variables': fact(['AGE'], unit='')}
        self.assertEqual(assess(req, attrs)['status'], 'unknown')
        attrs['variables']['complete'] = True
        self.assertEqual(assess(req, attrs)['status'], 'mismatch')
        attrs['variables']['value'] = ['AGE', 'income']
        self.assertEqual(assess(req, attrs)['status'], 'match')

    def test_one_of_and_custom_conditions(self):
        req = requirement('format', ['CSV', 'parquet'])
        self.assertEqual(assess(req, {'format': fact(['Parquet'], unit='')})['status'], 'match')
        req = requirement('custom:标注复核', ['双人复核'])
        self.assertEqual(assess(req, {'custom:标注复核': fact(['双人复核'], unit='')})['status'], 'match')

    def test_year_endpoints_do_not_prove_continuity(self):
        req = requirement('social.coverage_years', [2010, 2022], domains=['social'])
        attrs = {'social.coverage_years': fact([2000, 2023], unit='年')}
        self.assertEqual(assess(req, attrs)['status'], 'unknown')
        attrs['social.coverage_years']['coverage'] = 'continuous'
        self.assertEqual(assess(req, attrs)['status'], 'match')
        attrs['social.coverage_years']['value'] = [2015, 2023]
        self.assertEqual(assess(req, attrs)['status'], 'mismatch')

    def test_preferences_do_not_reject_candidate(self):
        req = requirement(priority='preferred')
        result = assess(req, {'medicine.participants': fact(10)})
        self.assertEqual(result['status'], 'not-assessed')
        self.assertEqual(result['conditions'][0]['status'], 'mismatch')

    def test_api_validates_before_model_call(self):
        with patch.object(server, 'generate_ai_recommendation') as model:
            response = server.app.test_client().post('/api/research-assistant', json={'message': 'clinical data', 'requirements': {'domains': ['unknown']}})
        self.assertEqual(response.status_code, 400)
        model.assert_not_called()

    def test_ai_or_client_cannot_supply_verified_facts(self):
        paper = {'doi': '10.1234/test', 'title': 'Clinical patient data', 'abstract': 'Clinical patient observations.'}
        output = {'answer': 'test', 'recommendations': [{'id': paper['doi'], 'dataProfile': {'attributes': {'medicine.participants': fact(999)}}}]}
        with patch.object(server, 'articles_data', [paper]), patch.object(server.FAISS_STORE, 'search', return_value=[]), patch.object(server, 'generate_ai_recommendation', return_value=output):
            response = server.app.test_client().post('/api/research-assistant', json={'message': 'clinical patient', 'requirements': requirement(), 'dataProfile': output['recommendations'][0]['dataProfile']}).get_json()
        self.assertEqual(response['recommendations'][0]['requirementsAssessment']['status'], 'unknown')

    def test_framework_api_uses_shared_registry(self):
        self.assertEqual(server.app.test_client().get('/api/requirements/framework').get_json(), FRAMEWORK)
