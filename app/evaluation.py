"""Conservative exact/alias matching; no LLM-as-judge. Findings require human review."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import html
import json
import csv
from pathlib import Path
from .llm_client import FixtureClient,from_environment
from .pipeline import run
from .validator import normalize,protocols


def norm(s):
    return normalize(s).casefold().replace('ı','i').replace('i\u0307','i')


def metric(expected,predicted):
    e,p=Counter(expected),Counter(predicted);tp=sum((e&p).values())
    return {'tp':tp,'expected':sum(e.values()),'predicted':sum(p.values()),
            'precision':tp/sum(p.values()) if p else None,
            'recall':tp/sum(e.values()) if e else None,
            'fp':sum(p.values())-tp,'fn':sum(e.values())-tp}


def protocol_key(value):
    known=protocols(value)
    return '|'.join(sorted(known)) if known else norm(value or '')


def score(final,gold):
    aliases={}
    for c in gold['components']:
        for alias in [c['id'],c['name'],*c.get('aliases',[])]:
            key=norm(alias)
            if key in aliases and aliases[key]!=c['id']:raise ValueError('Ambiguous reference alias: '+alias)
            aliases[key]=c['id']
    mapping={c.id:aliases.get(norm(c.name),'UNKNOWN:'+c.id) for c in final.architecture.components}
    g=gold['connections'];p=final.architecture.connections
    expected_pairs=[(c['source'],c['target']) for c in g]
    pred_pairs=[(mapping.get(c.source,'UNKNOWN:'+c.source),mapping.get(c.target,'UNKNOWN:'+c.target)) for c in p]
    expected_protocols=[(*pair,protocol_key(c.get('protocol'))) for pair,c in zip(expected_pairs,g)]
    pred_protocols=[(*pair,protocol_key(c.protocol)) for pair,c in zip(pred_pairs,p)]
    expected_typed=[(*pair,c['type']) for pair,c in zip(expected_pairs,g)]
    pred_typed=[(*pair,c.type) for pair,c in zip(pred_pairs,p)]
    source={e['requirement_id']:e['text'] for e in final.source_catalog}
    evidence=[ev for obj in [*final.architecture.components,*p,*final.analysis.findings] for ev in obj.evidence]
    valid=sum(bool(normalize(ev.quote) and ev.requirement_id in source and normalize(ev.quote) in normalize(source[ev.requirement_id])) for ev in evidence)
    return {'components':metric([c['id'] for c in gold['components']],list(mapping.values())),
            'directed_connections':metric(expected_pairs,pred_pairs),
            'connections_with_protocol':metric(expected_protocols,pred_protocols),
            'connections_with_type':metric(expected_typed,pred_typed),
            'quote_containment':{'valid':valid,'total':len(evidence),'rate':valid/len(evidence) if evidence else None},
            'unmatched_component_names':[c.name for c in final.architecture.components if mapping[c.id].startswith('UNKNOWN:')],
            'validation_errors':sum(i.severity=='error' for i in final.validation_issues),
            'findings_count':len(final.analysis.findings),
            'findings_semantic_score':None}


def aggregate(rows):
    completed=[r for r in rows if 'scores' in r]
    out={'cases_attempted':len(rows),'extraction_completed':len(completed),
         'review_completed':sum(r.get('review_status')=='completed' for r in rows),
         'run_completion_rate':sum(r.get('status')=='completed' for r in rows)/len(rows) if rows else None,
         'quality_denominator':'Only cases with a parsed architecture. Consult completion rate alongside quality.',
         'automatic_findings_scoring':False}
    for name in ['components','directed_connections','connections_with_protocol','connections_with_type']:
        vals=[r['scores'][name] for r in completed]
        tp=sum(v['tp'] for v in vals);e=sum(v['expected'] for v in vals);p=sum(v['predicted'] for v in vals)
        out[name]={'precision':tp/p if p else None,'recall':tp/e if e else None,'tp':tp,'expected':e,'predicted':p,'fp':p-tp,'fn':e-tp}
    return out


def write_report(payload,out):
    (out/'evaluation.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'scores.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['case','repeat','status','error_code','precision','recall','protocol_precision','validation_errors']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in payload['cases']:
            s=r.get('scores',{});d=s.get('directed_connections',{});p=s.get('connections_with_protocol',{})
            w.writerow(dict(case=r['case'],repeat=r['repeat'],status=r['status'],error_code=r.get('error_code',''),precision=d.get('precision'),recall=d.get('recall'),protocol_precision=p.get('precision'),validation_errors=s.get('validation_errors')))
    banner='OFFLINE FIXTURE — model başarısı ölçülmedi' if payload['mode']=='fixture' else 'CANLI MODEL — taslak referans seti; mühendis incelemesi gerekir'
    text=f'<!doctype html><html lang="tr"><meta charset="utf-8"><title>V6 değerlendirme</title><style>body{{font:16px system-ui;max-width:1100px;margin:40px auto}}pre{{white-space:pre-wrap;background:#f3f5f7;padding:20px}}</style><h1>{banner}</h1><p>Alıntı eşleşmesi anlamsal doğruluk değildir. Bulgular için human_review.csv dosyasını doldurun. Boş payda null; başarı sayılmaz.</p><pre>{html.escape(json.dumps(payload,ensure_ascii=False,indent=2))}</pre></html>'
    (out/'evaluation.html').write_text(text,encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description='V6 model benchmark (explicit live/fixture modes)')
    p.add_argument('--mode',choices=['fixture','live'],default='fixture');p.add_argument('--profile')
    p.add_argument('--split',choices=['dev','holdout','all'],default='dev');p.add_argument('--limit',type=int)
    p.add_argument('--repeats',type=int,choices=range(1,6),default=1);p.add_argument('--output')
    p.add_argument('--manifest',default=str(Path(__file__).resolve().parents[1]/'evaluation/manifest.json'))
    p.add_argument('--compare',nargs='+',help='Existing evaluation.json reports; no API calls')
    a=p.parse_args();out=Path(a.output or 'reports/'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    if out.exists() and any(out.iterdir()):p.error('Output directory must be empty.')
    out.mkdir(parents=True,exist_ok=True)
    if a.compare:
        reports=[json.loads(Path(f).read_text(encoding='utf-8')) for f in a.compare]
        comparability=len({(r.get('dataset_sha256'),r['split'],tuple(r['selected_cases']),r['repeats'],r.get('prompt_version')) for r in reports})==1
        result={'comparable_inputs':comparability,'note':'Fixture reports are not model benchmarks; compare identical case selections, repeats and prompt versions.',
                'runs':[{'file':f,'mode':r['mode'],'settings':r.get('settings'),'summary':r['summary']} for f,r in zip(a.compare,reports)]}
        (out/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(out);return
    manifest=Path(a.manifest);catalog=json.loads(manifest.read_text(encoding='utf-8'))
    cases=[c for c in catalog['cases'] if a.split=='all' or c['split']==a.split]
    if a.limit is not None:
        if a.limit<1:p.error('--limit must be positive')
        cases=cases[:a.limit]
    if not cases:p.error('No selected cases')
    settings=from_environment(a.profile).settings() if a.mode=='live' else {'model':'OFFLINE_FIXTURE'}
    digest=hashlib.sha256(manifest.read_bytes())
    for c in cases:
        for field in ('input','expected'):digest.update((manifest.parent/c[field]).read_bytes())
    from .pipeline import PROMPT_VERSION
    payload={'mode':a.mode,'split':a.split,'repeats':a.repeats,'prompt_version':PROMPT_VERSION,
             'selected_cases':[c['id'] for c in cases],'dataset_sha256':digest.hexdigest(),'settings':settings,'cases':[]}
    base_calls=len(cases)*a.repeats*2
    print(f'Mode={a.mode}; cases={len(cases)}; repeats={a.repeats}; base calls={base_calls if a.mode=="live" else 0}; live upper bound={base_calls*(settings.get("max_retries",0)+1) if a.mode=="live" else 0}')
    with (out/'human_review.csv').open('w',encoding='utf-8-sig',newline='') as review:
        w=csv.writer(review);w.writerow(['case','repeat','kind','finding_id','description_or_rubric','requirement_ids','decision_correct_incorrect_uncertain','reviewer_notes'])
        for c in cases:
            gold=json.loads((manifest.parent/c['expected']).read_text(encoding='utf-8'))
            for rep in range(1,a.repeats+1):
                row={'case':c['id'],'repeat':rep};client=FixtureClient(manifest.parent/c['fixture']) if a.mode=='fixture' else from_environment(a.profile)
                try:
                    final=run(str(manifest.parent/c['input']),str(out/c['id']/f'run_{rep}'),client)
                    row.update(status=final.run_metadata['run_status'],review_status=final.review_status,scores=score(final,gold))
                    if final.review_status=='failed':row['error_code']=final.run_metadata.get('review_error_code')
                    for f in final.analysis.findings:w.writerow([c['id'],rep,'predicted_finding',f.id,f.description,','.join(e.requirement_id for e in f.evidence),'',''])
                    for rubric in gold.get('finding_rubric',[]):w.writerow([c['id'],rep,'expected_rubric','',rubric,'','',''])
                except Exception as exc:
                    row.update(status='failed',error_code=getattr(exc,'code',type(exc).__name__))
                payload['cases'].append(row);payload['summary']=aggregate(payload['cases']);write_report(payload,out);review.flush()
                print(c['id'],rep,row['status'])
    print('Reports:',out)

if __name__=='__main__':main()
