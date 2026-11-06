"""Behavior checks for soft preferences and wording diversity; stdlib only."""
import argparse
import copy
import importlib.util
import json
import unittest
from pathlib import Path

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--skill-dir', type=Path, default=Path(__file__).resolve().parents[1])
options, test_arguments = parser.parse_known_args()
spec = importlib.util.spec_from_file_location('corpus', options.skill_dir/'scripts/corpus.py')
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)


def row(identifier, fleet, comment, tags=None, month='2026-05', flagship='加賀改二'):
    value = dict(id=identifier, fleet=fleet, comment=comment, month=month, flagship=flagship,
                 text_verified=bool(tags), review_status='待校对')
    if tags:
        value['curated'] = {'themes': tags}
    return value


def search(rows, **changes):
    arguments = dict(query='', theme='相处场景', expand_query='加賀 お茶 紅茶', prefer='',
                     flagship='', month=None, since=None, until=None, reviewed_only=False,
                     all=False, seed=42, limit=30, no_diversity=False)
    arguments.update(changes)
    return corpus.search(rows, argparse.Namespace(**arguments))


class RetrievalBehavior(unittest.TestCase):
    def test_preferences_change_ranking_without_changing_membership(self):
        rows = [row('a','第一','雪風とお茶'), row('b','第二','加賀とお茶'),
                row('c','第三','赤城と旅行')]
        normal = search(rows)
        focused = search(rows, prefer='加賀')
        self.assertEqual({r['id'] for r in normal['records']}, {r['id'] for r in focused['records']})
        self.assertEqual(focused['records'][0]['id'], 'b')
        self.assertNotIn('c', {r['id'] for r in focused['records']})

    def test_preference_cannot_add_an_unmatched_record(self):
        result = search([row('a','第一','加賀とお茶'), row('b','第二','赤城と旅行')], prefer='赤城')
        self.assertEqual([r['id'] for r in result['records']], ['a'])
        self.assertEqual(result['records'][0]['retrieval']['preference_matches'], [])

    def test_subject_and_scene_outrank_incidental_subject(self):
        result = search([row('a','加賀演習隊','任務終了'), row('b','第一','加賀と紅茶')], prefer='加賀 紅茶')
        self.assertEqual(result['records'][0]['id'], 'b')

    def test_nested_terms_do_not_multiply_evidence(self):
        rows = [row('a','第一','お茶を淹れよう')]
        short = search(rows, expand_query='お茶')['records'][0]['retrieval']['relevance_score']
        nested = search(rows, expand_query='茶 お茶 お茶')['records'][0]['retrieval']['relevance_score']
        self.assertEqual(short, nested)

    def test_width_normalization_applies_to_preferences(self):
        result = search([row('a','第一','ｶﾚｰを食べよう')], expand_query='カレー', prefer='カレー')
        self.assertEqual(result['records'][0]['retrieval']['preference_matches'], ['カレー'])

    def test_diversity_reduces_identical_wording_across_fleets(self):
        rows = [row('a','第一','加賀と紅茶でひと休み'), row('b','第二','加賀と紅茶でひと休み'),
                row('c','第三','紅茶を淹れたい加賀と')]
        checked = False
        for seed in range(20):
            plain = search(rows, limit=2, seed=seed, no_diversity=True)
            if plain['records'][0]['comment'] == plain['records'][1]['comment']:
                diverse = search(rows, limit=2, seed=seed)
                self.assertNotEqual(diverse['records'][0]['comment'], diverse['records'][1]['comment'])
                checked = True
                break
        self.assertTrue(checked, 'Fixture must exercise duplicate wording in the relevance-only result')

    def test_verified_pair_is_preserved_during_deduplication(self):
        rows = [row('raw','第一','加賀と紅茶。'), row('checked','第一','加賀と紅茶',['相处场景'])]
        result = search(rows, prefer='加賀')
        self.assertEqual(result['returned'], 1)
        self.assertEqual(result['records'][0]['id'], 'checked')

    def test_ranking_does_not_create_annotations_or_verification(self):
        result = search([row('raw','第一','加賀と紅茶')], prefer='加賀')
        self.assertNotIn('curated', result['records'][0])
        self.assertFalse(result['records'][0]['text_verified'])

    def test_filters_apply_before_preference_ranking(self):
        rows = [row('a','第一','加賀と紅茶',['相处场景']),
                row('b','第二','加賀とお茶', month='2026-04'),
                row('c','第三','加賀とお茶', flagship='赤城改二')]
        result = search(rows, prefer='加賀', month={5}, flagship='加賀', reviewed_only=True)
        self.assertEqual([r['id'] for r in result['records']], ['a'])
        self.assertEqual(result['scope']['eligible_records'], 1)

    def test_seeded_search_is_reproducible_and_leaves_source_unchanged(self):
        rows = [row(str(i),'第一'+str(i),'加賀と紅茶') for i in range(5)]
        snapshot = copy.deepcopy(rows)
        self.assertEqual(search(rows, prefer='加賀'), search(rows, prefer='加賀'))
        self.assertEqual(rows, snapshot)

    def test_plain_queries_keep_the_existing_sort_mode(self):
        result = search([row('a','第一','加賀と紅茶')], theme='', expand_query='', query='紅茶')
        self.assertEqual(result['scope']['selection'], 'keyword_hits_then_verification')

    def test_evaluation_judgments_cover_both_saved_top_eight_sets(self):
        directory = Path(__file__).resolve().parent
        initial = json.loads((directory/'relevance.json').read_text(encoding='utf-8'))['cases']
        extra = json.loads((directory/'supplemental-relevance.json').read_text(encoding='utf-8'))['cases']
        for name in ('baseline', 'v1.6.0', 'without-diversity'):
            report = json.loads((directory/'reports'/(name+'.json')).read_text(encoding='utf-8'))
            for case in report['results']:
                ids = {r['record_id'] for r in initial[case['id']] + extra[case['id']]}
                self.assertTrue({r['id'] for r in case['records']} <= ids)


if __name__ == '__main__':
    unittest.main(argv=[__file__]+test_arguments)
