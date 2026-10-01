"""Integrity regressions and explicitly visible unmet semantic expectations."""
import unittest

from app.models import FinalModel
from app.requirement_catalog import RequirementEntry
from app.review_store import enrich_issues
from app.validator import validate_architecture
from app.validator_audit import RULES, audit, baseline, cases, evaluate


def checked(data, app=False):
    final = FinalModel.model_validate(data)
    if app:
        return {i['code'] for i in enrich_issues(final)}
    return {i.code for i in validate_architecture(final.architecture,
        [RequirementEntry(**s) for s in final.source_catalog], final.analysis)}


class ValidatorIntegrityAuditTests(unittest.TestCase):
    def test_complete_supported_model_has_no_issues_in_either_layer(self):
        for app in (False, True):
            self.assertEqual(checked(baseline(), app), set())

    def test_known_integrity_mutations_trigger_expected_rules(self):
        # Expected codes come from the independently specified audit scenarios.
        for case in cases():
            if case['category'] in ('kural', 'kural yorumu'):
                with self.subTest(case=case['name']):
                    result = evaluate(case)
                    self.assertTrue(result['expectation_met'], result)

    def test_every_documented_rule_is_exercised(self):
        results = audit()['results']
        observed = {i['code'] for r in results for layer in ('core','app')
                    for i in r[layer+'_issues']}
        self.assertEqual(observed, {r[0] for r in RULES})

    def test_app_warns_when_extra_protocol_lacks_support(self):
        data = baseline()
        data['architecture']['connections'][0]['protocol'] = 'RS-422 / UDP'
        self.assertIn('PROTOCOL_NOT_SUPPORTED', checked(data, app=True))

    def test_app_warns_for_protocol_added_to_technology_free_source(self):
        self.assertIn('PROTOCOL_NOT_SUPPORTED', checked(
            baseline("A, ölçümleri B'ye aktarır.", 'UDP'), app=True))

    def test_invalid_quote_is_rejected_despite_matching_coverage_id(self):
        data = baseline()
        data['architecture']['components'][0]['evidence'][0]['quote'] = 'Uydurma'
        self.assertIn('QUOTE_NOT_IN_SOURCE', checked(data))


class UnmetValidatorExpectations(unittest.TestCase):
    """These are unmet product expectations, not successful correctness checks.

    unittest reports them as 'expected failure'; a future implementation should
    remove the decorator and specify the actual, approved diagnostic contract.
    """
    def test_core_should_warn_about_extra_unsupported_protocol(self):
        data=baseline()
        data['architecture']['connections'][0]['protocol']='RS-422 / UDP'
        self.assertTrue(checked(data))

    def test_core_should_warn_about_unsupported_known_protocol(self):
        self.assertTrue(checked(baseline("A, ölçümleri B'ye aktarır.", 'UDP')))

    @unittest.expectedFailure
    def test_both_layers_should_flag_direction_opposite_to_explicit_source(self):
        data=baseline()
        data['architecture']['connections'][0].update(source='B', target='A')
        for app in (False,True):
            self.assertTrue(checked(data,app))

    @unittest.expectedFailure
    def test_both_layers_should_flag_explicitly_forbidden_protocol(self):
        for app in (False,True):
            self.assertTrue(checked(baseline('A ile B arasında RS-422 kullanılmayacaktır.'),app))

    @unittest.expectedFailure
    def test_both_layers_should_flag_power_type_for_measurement_transfer(self):
        data=baseline()
        data['architecture']['connections'][0]['type']='power'
        for app in (False,True):
            self.assertTrue(checked(data,app))

    @unittest.expectedFailure
    def test_both_layers_should_review_architectural_source_marked_as_context(self):
        data=baseline()
        data['architecture']['requirement_coverage'][0]['status']='not_architectural'
        for app in (False,True):
            self.assertTrue(checked(data,app))

    @unittest.expectedFailure
    def test_both_layers_should_review_irrelevant_but_verbatim_evidence(self):
        for app in (False,True):
            self.assertTrue(checked(baseline('Bu raporun kapağı mavidir.',None),app))


if __name__ == '__main__':
    unittest.main()
