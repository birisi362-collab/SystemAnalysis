import html
import json
from pathlib import Path

def _ids(architecture):
    return {c.id:f'n{i}' for i,c in enumerate(architecture.components)}

def _label(value):
    # Encode grammar-sensitive characters for quoted Mermaid labels.
    replacements={'&':'#38;','"':'#34;','<':'#60;','>':'#62;','|':'#124;','[':'#91;',']':'#93;','{':'#123;','}':'#125;','`':'#96;','\\':'#92;'}
    return ''.join(replacements.get(c,c) for c in value.replace('\n',' '))

def render_mermaid(final):
    a=final.architecture;ids=_ids(a);lines=['flowchart LR']
    for c in a.components: lines.append(f'    {ids[c.id]}["{_label(c.name)}"]')
    for e in a.connections:
        if e.source not in ids or e.target not in ids: continue
        label=' / '.join(x for x in [e.label,e.protocol] if x) or e.type
        arrow = '<-->' if e.direction == 'bidirectional' else '-->'
        lines.append(f'    {ids[e.source]} {arrow}|"{_label(label)}"| {ids[e.target]}')
    return '\n'.join(lines)

def render_dot(final):
    a=final.architecture;ids=_ids(a);lines=['digraph SystemArchitecture {','rankdir=LR;','node [shape=box,fontname="Arial"];']
    for c in a.components: lines.append(f'{ids[c.id]} [label={json.dumps(c.name,ensure_ascii=False)}];')
    for e in a.connections:
        if e.source not in ids or e.target not in ids: continue
        label=' / '.join(x for x in [e.label,e.protocol] if x) or e.type
        direction = ',dir=both' if e.direction == 'bidirectional' else ''
        lines.append(f'{ids[e.source]} -> {ids[e.target]} [label={json.dumps(label,ensure_ascii=False)}{direction}];')
    return '\n'.join(lines+['}'])

def write_outputs(final,output_dir):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    (out/'analysis_result.json').write_text(final.model_dump_json(indent=2),encoding='utf-8')
    (out/'system_model.json').write_text(final.architecture.model_dump_json(indent=2),encoding='utf-8')
    (out/'system_diagram.mmd').write_text(render_mermaid(final),encoding='utf-8')
    dot=render_dot(final);(out/'system_diagram.dot').write_text(dot,encoding='utf-8')
    try:
        from graphviz import Source
        Source(dot).render(filename=str(out/'system_diagram'),format='svg',cleanup=True)
    except Exception as exc:
        (out/'graphviz_error.txt').write_text('SVG export unavailable: '+str(exc),encoding='utf-8')
    badge='Mimari çalışma çıktısı — mühendis değerlendirmesi'
    rows=''.join(f'<article><h3>{html.escape(f.title)}</h3><p>{html.escape(f.description)}</p><p>{html.escape(f.recommended_action or "")}</p></article>' for f in final.analysis.findings)
    text=f'''<!doctype html><html lang="tr"><meta charset="utf-8"><title>Analiz raporu</title>
<style>body{{font:16px system-ui;max-width:1000px;margin:32px auto;padding:20px}}td,th{{border:1px solid #ccc;padding:8px}}table{{border-collapse:collapse}}pre{{white-space:pre-wrap}}</style>
<h1>{html.escape(final.architecture.system_name)}</h1><p>{badge}</p>
<p>İkinci tur: {final.review_status}. İnsan incelemesi gereklidir. Geçersiz uçlu bağlantılar şemada çizilmez; JSON içinde korunur.</p>
<h2>Mühendislik önerileri ve bulguları</h2>{rows}
<h2>Model ve kaynaklar</h2><pre>{html.escape(final.model_dump_json(indent=2))}</pre></html>'''
    (out/'report.html').write_text(text,encoding='utf-8')
