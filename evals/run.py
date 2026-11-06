"""Run the frozen editorial retrieval benchmark; Python standard library only."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-dir', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--script', type=Path, help='Alternative corpus.py, e.g. the v1.5.0 baseline')
    parser.add_argument('--split', choices=['development', 'holdout', 'all'], default='all')
    parser.add_argument('--no-diversity', action='store_true', help='Evaluate the relevance ranking without wording reranking')
    parser.add_argument('--output', type=Path)
    options = parser.parse_args()
    directory = Path(__file__).resolve().parent
    requests_file = directory / 'requests.json'
    judgments_file = directory / 'relevance.json'
    dataset = json.loads(requests_file.read_text(encoding='utf-8'))
    judgments = json.loads(judgments_file.read_text(encoding='utf-8'))['cases']
    supplemental_file = directory / 'supplemental-relevance.json'
    if supplemental_file.exists():
        supplemental = json.loads(supplemental_file.read_text(encoding='utf-8'))['cases']
        for key, values in supplemental.items():
            assert not {r['record_id'] for r in judgments[key]} & {r['record_id'] for r in values}
            judgments[key].extend(values)
    assert hashlib.sha256((options.skill_dir / 'references/corpus.csv').read_bytes()).hexdigest() == dataset['corpus_sha256']
    curated = json.loads((options.skill_dir/'references/curated-examples.json').read_text(encoding='utf-8'))
    canonical_curated = json.dumps(curated, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    assert hashlib.sha256(canonical_curated).hexdigest() == dataset['curated_semantic_sha256']
    script = options.script or options.skill_dir / 'scripts/corpus.py'
    spec = importlib.util.spec_from_file_location('evaluated_corpus', script)
    corpus = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(corpus)
    corpus.REFERENCES = options.skill_dir / 'references'
    rows = corpus.load_data()
    results = []
    for case in dataset['requests']:
        if options.split != 'all' and case['split'] != options.split:
            continue
        search = dict(query='', theme='', expand_query='', prefer='', flagship='', month=None,
                      since=None, until=None, reviewed_only=False, all=False, seed=42, limit=8,
                      no_diversity=options.no_diversity)
        search.update(case['search'])
        report = corpus.search(rows, argparse.Namespace(**search))
        qrels = {r['record_id']: r for r in judgments[case['id']]}
        grades = [qrels[r['id']]['grade'] if r['id'] in qrels else None for r in report['records']]
        dcg = sum((2 ** (grade or 0) - 1) / math.log2(index + 2)
                  for index, grade in enumerate(grades))
        ideal = sorted((r['grade'] for r in qrels.values()), reverse=True)[:8]
        idcg = sum((2 ** grade - 1) / math.log2(index + 2) for index, grade in enumerate(ideal))
        ideas = {qrels[r['id']]['idea'] for r in report['records']
                 if r['id'] in qrels and qrels[r['id']]['grade'] > 0}
        results.append(dict(
            id=case['id'], split=case['split'], prompt=case['prompt'],
            metrics=dict(useful_at8=sum((g or 0) > 0 for g in grades) / 8,
                         direct_at8=sum(g == 2 for g in grades) / 8,
                         ndcg_at8_judged_pool=dcg / idcg if idcg else 0,
                         judged_coverage_at8=sum(g is not None for g in grades) / 8,
                         distinct_useful_ideas_at8=len(ideas)),
            records=[dict(id=r['id'], fleet=r['fleet'], comment=r['comment'],
                          grade=grade, text_verified=r['text_verified'])
                     for r, grade in zip(report['records'], grades)]))
    summaries = {}
    for split in ('development', 'holdout', 'all'):
        group = [r for r in results if split == 'all' or r['split'] == split]
        if group:
            summaries[split] = {metric: round(sum(r['metrics'][metric] for r in group) / len(group), 4)
                                for metric in group[0]['metrics']}
            summaries[split]['requests'] = len(group)
    output = dict(script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
                  requests_sha256=hashlib.sha256(requests_file.read_bytes()).hexdigest(),
                  judgments_sha256=hashlib.sha256(judgments_file.read_bytes()).hexdigest(),
                  supplemental_judgments_sha256=hashlib.sha256(supplemental_file.read_bytes()).hexdigest() if supplemental_file.exists() else None,
                  note='Single-maintainer editorial judgments; unjudged results count as zero, not proven irrelevant. '
                       'NDCG uses only the judged pool. This is a retrieval benchmark, not a generation-quality or award-probability score.',
                  summaries=summaries, results=results)
    if options.output:
        options.output.write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'summaries': summaries, 'output': str(options.output) if options.output else None}, ensure_ascii=False))


if __name__ == '__main__':
    main()
