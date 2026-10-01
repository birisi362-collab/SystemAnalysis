"""Offline, reproducible validator audit; never edits model outputs or review data."""
import argparse
from copy import deepcopy
from dataclasses import asdict
from html import escape
import json
from pathlib import Path

from .models import FinalModel
from .requirement_catalog import RequirementEntry
from .review_store import enrich_issues
from .validator import validate_architecture


# The expected outcomes below are specified independently of the observed result.
RULES = [
    ('DUPLICATE_SOURCE_ID', 'Kaynak kimliği veya özgün numarası tekrarlanıyor mu?', 'Belge gerçekten aynı gereksinimi iki yerde tekrar ediyor olabilir.'),
    ('DUPLICATE_COMPONENT_ID', 'Bileşen kimlikleri benzersiz mi?', 'Farklı kimlikli iki bileşenin aslında aynı olması anlaşılmaz.'),
    ('DUPLICATE_CONNECTION_ID', 'Bağlantı kimlikleri benzersiz mi?', 'Farklı kimlikle aynı bağlantının tekrarı anlaşılmaz.'),
    ('DUPLICATE_COVERAGE', 'Bir kaynağın birden fazla kapsama kaydı var mı?', 'Tek kayıt içindeki anlamsal tutarlılık ölçülmez.'),
    ('DUPLICATE_FINDING_ID', 'Bulgu kimlikleri benzersiz mi?', 'Aynı sorunun farklı kimliklerle tekrarı anlaşılmaz.'),
    ('EMPTY_ARCHITECTURE', 'Bileşen listesi boş mu?', 'Belgenin mimari içerip içermediğine karar vermez.'),
    ('MISSING_EVIDENCE', 'Nesnenin veya bulgunun kanıt listesi boş mu?', 'Mühendisin yeni tasarım kararı da kanıtsız olabilir; otomatik olarak yanlış değildir.'),
    ('UNKNOWN_EVIDENCE_REF', 'Kanıtın kaynak kimliği katalogda var mı?', 'Doğru kaynağın seçildiğini kanıtlamaz.'),
    ('MISSING_QUOTE', 'Kaynak için alıntı boş mu?', 'Dolu alıntının açıklayıcı olması ayrı konudur.'),
    ('QUOTE_NOT_IN_SOURCE', 'Boşluk ve Unicode normalizasyonundan sonra alıntı kaynakta geçiyor mu?', 'Özet/parafraz reddedilir. Doğru alıntı, doğru çıkarım demek değildir.'),
    ('UNKNOWN_SOURCE', 'Bağlantının başlangıç bileşeni mevcut mu?', 'Başlangıç bileşeninin kaynak cümlesine uygunluğunu denetlemez.'),
    ('UNKNOWN_TARGET', 'Bağlantının hedef bileşeni mevcut mu?', 'Bağlantı yönünü veya hedefin anlamını denetlemez.'),
    ('UNKNOWN_COMPONENT_REF', 'Kapsama/bulgu mevcut bileşenleri mi gösteriyor?', 'İlişkinin anlamını denetlemez.'),
    ('UNKNOWN_CONNECTION_REF', 'Kapsama/bulgu mevcut bağlantıları mı gösteriyor?', 'İlişkinin anlamını denetlemez.'),
    ('EXPLICIT_PROTOCOL_NOT_CAPTURED', 'Geçerli alıntıda bilinen teknoloji var ama bağlantı protokolü boş mu?', 'Sözcük diğer bir bağlantıya ait veya olumsuz cümlede olabilir.'),
    ('PROTOCOL_MISMATCH', 'Alıntıdaki bilinen teknolojiler ile protokol alanının hiç ortak değeri yok mu?', 'Olumsuzluk, yön, aynı cümledeki farklı bağlantılar ve katmanlar anlaşılmaz.'),
    ('PROTOCOL_REVIEW_REQUIRED', 'Alıntıdaki bilinen teknolojilerden bazıları protokol alanında yok mu?', 'Ethernet ve TCP gibi farklı katmanlar meşru olabilir; inceleme uyarısıdır.'),
    ('PROTOCOL_SOURCE_REVIEW', 'Tam kaynakta teknoloji var ama seçilen alıntıda yok mu?', 'Tam kaynak başka bir bağlantıdan da bahsedebilir.'),
    ('PROTOCOL_UNVERIFIED', 'Bilinmeyen protokol değeri tam kaynakta metin olarak bulunamıyor mu?', 'Sözlük sınırlı; özel arayüz adı metinde geçse bile anlamı denetlenmez.'),
    ('UNKNOWN_COVERAGE_REQUIREMENT', 'Kapsama kaydı katalogda olmayan bir kaynağa mı işaret ediyor?', 'Katalog oluşturulurken atlanan kaynakları bulamaz.'),
    ('COVERAGE_WITHOUT_LINKS', 'Covered veya partially_covered denmiş ama nesne seçilmemiş mi?', 'Nesne seçmek gereksinimin gerçekleştiğini kanıtlamaz.'),
    ('COVERAGE_EVIDENCE_MISMATCH', 'Doğrudan ilişki seçilen nesnenin kanıtında aynı kaynak kimliği var mı?', 'Aynı kaynağı gösteren bağlantının uçları bağlamdır; doğrudan destek sayılmaz. Kimlik eşleşmesi alıntının geçerliliğini kanıtlamaz.'),
    ('COVERAGE_CONTEXT_ONLY', 'Covered denmiş ama yalnız bağlam ilişki mi var?', 'Bağlam ilişkisi doğrudan doküman desteği yerine geçmez.'),
    ('MISSING_COVERAGE', 'Her katalog kaynağına kapsama durumu verilmiş mi?', 'Durumun doğruluğu denetlenmez.'),
    ('UNMAPPED_REQUIREMENT', 'Durum unmapped olarak verilmiş mi?', 'Modelin verdiği durumu görünür kılar; bağımsız eksik gereksinim keşfi değildir.'),
    ('PARTIAL_COVERAGE', 'Durum partially_covered olarak verilmiş mi?', 'Eksik kısmın ne olduğunu kendi başına bulmaz.'),
    ('ORPHAN_COMPONENT', 'System dışında bağlantı ucu olmayan bileşen var mı?', 'Bağımsız bileşen her zaman hata değildir; çizilmiş yanlış bağlantı uyarıyı susturabilir.'),
    ('PROTOCOL_NOT_SUPPORTED', 'Beyan edilen bilinen teknolojiler geçerli alıntıda var mı?', 'Ana validatör ve uygulama aynı kuralı kullanır. Olumsuzluk ve teknik anlam anlaşılmaz.'),
]


def baseline(text="A, ölçümleri RS-422 üzerinden B'ye aktarır.", protocol='RS-422'):
    ev = dict(requirement_id='G-01', quote=text)
    return dict(source_catalog=[asdict(RequirementEntry('G-01', text, locations=['line:1']))],
                architecture=dict(system_name='Deney', components=[
                    dict(id=x, name=x, evidence=[deepcopy(ev)]) for x in ('A', 'B')],
                    connections=[dict(id='E1', source='A', target='B', type='data',
                                      protocol=protocol, evidence=[deepcopy(ev)])],
                    requirement_coverage=[dict(requirement_id='G-01', status='covered',
                        related_component_ids=['A', 'B'], related_connection_ids=['E1'])]),
                analysis=dict(findings=[]))


def cases():
    result = []
    def add(name, explain, edit, expected=(), category='kural', base=None,
            app_expected=None, forbidden=()):
        data = deepcopy(base or baseline())
        edit(data)
        result.append(dict(name=name, explanation=explain, category=category,
            input=data, expected_core=list(expected),
            expected_app=list(expected if app_expected is None else app_expected),
            forbidden=list(forbidden)))
    def setpath(path, value):
        def edit(d):
            for key in path[:-1]:
                d = d[key]
            d[path[-1]] = value
        return edit
    cp = ['architecture', 'components', 0]
    edge = ['architecture', 'connections', 0]
    cov = ['architecture', 'requirement_coverage', 0]
    add('Doğru küçük mimari', 'A → B ve RS-422 açıkça kaynakta; uyarı beklenmez.', lambda d: None, forbidden=[r[0] for r in RULES])
    for code, name, path, value in [
        ('MISSING_EVIDENCE', 'Kanıt listesi boş', cp+['evidence'], []),
        ('UNKNOWN_EVIDENCE_REF', 'Var olmayan kanıt kaynağı', cp+['evidence',0,'requirement_id'], 'G-999'),
        ('MISSING_QUOTE', 'Boş alıntı', cp+['evidence',0,'quote'], '  '),
        ('QUOTE_NOT_IN_SOURCE', 'Uydurma alıntı', cp+['evidence',0,'quote'], 'Kaynakta olmayan cümle'),
        ('UNKNOWN_SOURCE', 'Başlangıç bileşeni yok', edge+['source'], 'Z'),
        ('UNKNOWN_TARGET', 'Hedef bileşeni yok', edge+['target'], 'Z'),
        ('UNKNOWN_COMPONENT_REF', 'Kapsamadaki bileşen yok', cov+['related_component_ids'], ['Z']),
        ('UNKNOWN_CONNECTION_REF', 'Kapsamadaki bağlantı yok', cov+['related_connection_ids'], ['Z']),
        ('EXPLICIT_PROTOCOL_NOT_CAPTURED', 'Protokol boş bırakılmış', edge+['protocol'], None),
        ('PROTOCOL_MISMATCH', 'RS-422 yerine UDP yazılmış', edge+['protocol'], 'UDP'),
        ('PROTOCOL_SOURCE_REVIEW', 'Alıntı protokolü dışarıda bırakıyor', edge+['evidence',0,'quote'], 'ölçümleri'),
        ('PROTOCOL_UNVERIFIED', 'Kaynakta olmayan özel protokol', edge+['protocol'], 'ÖzelHat'),
        ('UNKNOWN_COVERAGE_REQUIREMENT', 'Kapsamanın kaynağı yok', cov+['requirement_id'], 'G-999'),
        ('MISSING_COVERAGE', 'Kaynağın kapsama kaydı yok', ['architecture','requirement_coverage'], []),
        ('UNMAPPED_REQUIREMENT', 'Eşleştirilmemiş durumu', cov+['status'], 'unmapped'),
        ('PARTIAL_COVERAGE', 'Kısmen eşleştirilmiş durumu', cov+['status'], 'partially_covered'),
        ('EMPTY_ARCHITECTURE', 'Bileşensiz mimari', ['architecture','components'], []),
        ('ORPHAN_COMPONENT', 'Bağlantısız bileşenler', ['architecture','connections'], []),
    ]:
        add(name, 'Tek değişiklik: '+str(path)+' → '+str(value), setpath(path,value), [code])
    for code, path in [('DUPLICATE_SOURCE_ID',['source_catalog']),
                       ('DUPLICATE_COMPONENT_ID',['architecture','components']),
                       ('DUPLICATE_CONNECTION_ID',['architecture','connections']),
                       ('DUPLICATE_COVERAGE',['architecture','requirement_coverage'])]:
        def duplicate(d, path=path):
            for key in path:
                d = d[key]
            d.append(deepcopy(d[0]))
        add(code, 'Aynı kayıt iki kez eklenir; kimlik tekrarı bulunmalı.', duplicate, [code])
    finding = dict(id='F1', severity='low', type='other', title='Deney', description='Deney',
                   evidence=baseline()['architecture']['components'][0]['evidence'])
    add('Yinelenen bulgu', 'Aynı bulgu kimliği iki kez var.',
        setpath(['analysis','findings'], [finding,deepcopy(finding)]), ['DUPLICATE_FINDING_ID'])
    add('Kapsama nesnesiz', 'Covered kaydında iki nesne listesi de boş.',
        lambda d: d['architecture']['requirement_coverage'][0].update(related_component_ids=[],related_connection_ids=[]), ['COVERAGE_WITHOUT_LINKS'])
    def contextual(d):
        d['source_catalog'].append(asdict(RequirementEntry('G-02', 'A kutusu B ile birlikte yerleştirilir.')))
        d['architecture']['requirement_coverage'].append(dict(requirement_id='G-02', status='covered', related_component_ids=['A']))
    add('Bağlamsal ilişki doğrudan kanıt sayılıyor', 'A var; ikinci kaynak A ile ilişkili. Aynı kaynak A kanıtına eklenmediği için inceleme uyarısı çıkıyor. İlişki türü kararlaştırılmadan mimari yanlış denemez.', contextual, ['COVERAGE_EVIDENCE_MISMATCH'], category='kural yorumu')
    def context_only(d):
        contextual(d)
        d['architecture']['requirement_coverage'][-1].update(related_component_ids=[],contextual_component_ids=['A'])
    add('Yalnız bağlam ile covered beyanı', 'İlgili öğe seçmek doğrudan dayanak değildir; mühendislik incelemesi uyarısı beklenir.', context_only, ['COVERAGE_CONTEXT_ONLY'])
    add('Alıntıda iki teknoloji', 'RS-422 ve Ethernet aynı alıntıda; ek teknoloji inceleme uyarısı beklenir.', lambda d: None,
        ['PROTOCOL_REVIEW_REQUIRED'], base=baseline("A, RS-422 ve Ethernet üzerinden B'ye aktarır."))
    add('Fazladan protokol beyanı', 'Kaynak yalnız RS-422. Beyanda RS-422 ve UDP var: UDP desteği eksikliği iki kontrol yolunda da görünür olmalı.',
        setpath(edge+['protocol'], 'RS-422 / UDP'), ['PROTOCOL_NOT_SUPPORTED'], app_expected=['PROTOCOL_NOT_SUPPORTED'], category='kapsam farkı')
    add('Teknoloji belirtilmeyen kaynağa UDP eklemek', 'Kaynak yalnız veri aktarımı der; UDP için destek bulunmamalı.', lambda d: None,
        ['PROTOCOL_NOT_SUPPORTED'], base=baseline("A, ölçümleri B'ye aktarır.", 'UDP'), category='kapsam farkı')
    add('Ters bağlantı yönü', 'Kaynak A → B der. Model B → A yapıldı. Mühendislik açısından tutarsızlığın görünmesi gerekir.',
        lambda d: d['architecture']['connections'][0].update(source='B',target='A'), ['DIRECTION_CONFLICT'], category='anlam sınırı')
    add('Olumsuz cümlede protokol adı', 'Kaynak RS-422 kullanılmayacağını açıkça söyler. RS-422 seçilmesi tutarsızdır.', lambda d: None,
        ['NEGATED_PROTOCOL'], base=baseline("A ile B arasında RS-422 kullanılmayacaktır."), category='anlam sınırı')
    add('Bağlantı türü yanlış', 'Kaynak ölçüm aktarımı; model bunu güç bağlantısı yapar.', setpath(edge+['type'],'power'), ['CONNECTION_TYPE_CONFLICT'], category='anlam sınırı')
    add('Mimari gereksinimi bağlam diye dışlamak', 'A → B açıkça mimaridir. not_architectural seçimi inceleme gerektirir.',
        setpath(cov+['status'],'not_architectural'), ['COVERAGE_CLASSIFICATION_REVIEW'], category='anlam sınırı')
    add('Gerçek ama ilgisiz alıntı', 'Kaynakta geçen bir cümle doğru alıntıdır fakat A → B aktarımını desteklemez.',
        lambda d: None, ['EVIDENCE_RELEVANCE_REVIEW'], base=baseline('Bu raporun kapağı mavidir.',None), category='anlam sınırı')
    add('Boşluk normalizasyonu', 'Kaynak ve alıntı arasındaki fazla boşluk farkı kabul edilmeli.',
        setpath(cp+['evidence',0,'quote'], "A,  ölçümleri RS-422 üzerinden B'ye aktarır."), forbidden=['QUOTE_NOT_IN_SOURCE'])
    add('İngilizce can', 'can sözcüğü CAN veri yolu sayılmamalı.', lambda d: None,
        base=baseline('A can send measurements to B.', None), forbidden=['EXPLICIT_PROTOCOL_NOT_CAPTURED'])
    add('Geçersiz alıntı ve kapsama', 'Aynı kaynak kimliği kapsama kontrolünü geçirir; ancak ayrı alıntı kontrolü bunu yakalamalı.',
        setpath(cp+['evidence',0,'quote'], 'Uydurma'), ['QUOTE_NOT_IN_SOURCE'], forbidden=['COVERAGE_EVIDENCE_MISMATCH'])
    return result


def evaluate(case):
    final = FinalModel.model_validate(case['input'])
    entries = [RequirementEntry(**s) for s in final.source_catalog]
    core = [i.model_dump() for i in validate_architecture(final.architecture, entries, final.analysis)]
    app = enrich_issues(final)
    result = {k:v for k,v in case.items() if k != 'input'}
    for label, issues in [('core',core),('app',app)]:
        codes = {i['code'] for i in issues}
        result[label+'_issues'] = issues
        result[label+'_missing'] = sorted(set(case['expected_'+label])-codes)
        result[label+'_unexpected'] = sorted(set(case['forbidden']) & codes)
    result['expectation_met'] = not any(result[k] for k in ('core_missing','app_missing','core_unexpected','app_unexpected'))
    return result


def audit():
    scenarios = cases()
    results = [evaluate(c) for c in scenarios]
    seen = {i['code'] for r in results for layer in ('core','app') for i in r[layer+'_issues']}
    return dict(rules=[dict(code=c, check=check, limitation=limit, exercised=c in seen) for c,check,limit in RULES],
                scenarios=scenarios, results=results,
                summary=dict(total=len(results), expectation_met=sum(r['expectation_met'] for r in results),
                    differences=sum(not r['expectation_met'] for r in results), rules_exercised=len(seen)))


def write_report(output):
    data = audit()
    output.mkdir(parents=True, exist_ok=True)
    (output/'audit.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    esc = lambda x: escape(str(x))
    rule_rows = ''.join(f'<tr><td><code>{esc(r["code"])}</code></td><td>{esc(r["check"])}</td><td>{esc(r["limitation"])}</td></tr>' for r in data['rules'])
    cards = ''
    for n,r in enumerate(data['results'],1):
        def codes(layer):
            return ', '.join(sorted({i['code'] for i in r[layer+'_issues']})) or 'Uyarı yok'
        status = 'Beklenti karşılandı' if r['expectation_met'] else 'Beklenti karşılanmadı — sınır / fark'
        detail = json.dumps(data['scenarios'][n-1]['input'],ensure_ascii=False,indent=2)
        cards += f'<article class="{"pass" if r["expectation_met"] else "gap"}"><h3>{n}. {esc(r["name"])}</h3><b>{status}</b> · {esc(r["category"])}<p>{esc(r["explanation"])}</p><p>Beklenen ana kontrol: {esc(r["expected_core"] or "İlgili yasak uyarılar çıkmamalı")}<br>Beklenen uygulama: {esc(r["expected_app"] or "İlgili yasak uyarılar çıkmamalı")}</p><p>Ana kontrol: {esc(codes("core"))}<br>Uygulama: {esc(codes("app"))}</p><details><summary>Deney girdisini göster</summary><pre>{esc(detail)}</pre></details></article>'
    s=data['summary']
    html=f'''<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Validatör incelemesi</title><style>body{{font:16px/1.6 system-ui;background:#eef2f6;color:#17243a;margin:0}}main{{max-width:1200px;margin:auto;padding:32px}}h1,h2{{line-height:1.2}}article,.intro{{background:white;padding:24px;margin:16px 0;border-radius:12px}}article{{border-left:6px solid #25845a}}.gap{{border-color:#b66b12}}table{{border-collapse:collapse;background:white;width:100%}}th,td{{text-align:left;padding:12px;border:1px solid #d8dfeb;vertical-align:top}}code{{font-size:12px;overflow-wrap:anywhere}}pre{{white-space:pre-wrap;font-size:13px}}nav a{{margin-right:20px}}.scroll{{overflow:auto}}</style><main><h1>Validatör neyi gerçekten kontrol ediyor?</h1><nav><a href="#conclusion">Bulgular</a><a href="#rules">Kural tablosu</a><a href="#cases">Deneyler</a></nav><section class="intro" id="conclusion"><h2>Sonuç</h2><p>{s['total']} küçük deney; {s['expectation_met']} beklenti karşılandı, {s['differences']} sınır veya kapsam farkı görünür oldu. {len(RULES)} kuralın tamamı en az bir deneyde tetiklendi.</p><p>Bu bir doğruluk yüzdesi değildir. Deneyler özellikle bilinen kusurları ve sınırları göstermek için seçildi. Kural deneyleri ilgili kodun varlığını/yokluğunu kontrol eder; diğer uyarılar da aşağıda görünür.</p><p><b>Validatör bir evrak kontrol memuru gibi çalışıyor:</b> adres var mı, alıntı gerçekten belgede mi, listeler birbiriyle uyumlu mu? Tasarımın teknik anlamını değerlendiren mühendis gibi çalışmıyor.</p><p><b>Ana validatör ile uygulama ortak:</b> fazladan veya desteksiz bilinen protokol beyanı iki yolda da ortak validatörle kontrol ediliyor. Yön, olumsuzluk, bağlantı türü ve alıntının ilgisi iki yolda da yakalanmıyor. Beklenen DIRECTION_CONFLICT gibi adlar mevcut kodlar değildir; eksik kontrol ihtiyacının deney etiketleridir.</p><p><b>Coverage uyuşmazlığı:</b> kapsamaya seçilen nesnenin kanıtında aynı kaynak kimliği aranır. Aynı kaynağı gösteren bağlantının uçları bağlam olarak ayrılır. Diğer desteksiz doğrudan ilişkiler inceleme uyarısı olarak kalır. Bu deney kuralın çalıştığını gösterir, mimarinin yanlış olduğunu kanıtlamaz.</p><p>Üretim validatörünün protokol ve kaynak ilişkisi kuralları güncellendi; orijinal model çıktıları korunuyor. Yeni model çağrısı yapılmadı. Bu rapor anlamsal kontroller için insan tarafından onaylanmış kapsamlı bir referans veri kümesinin yerine geçmez.</p></section><h2 id="rules">Her kuralın kapsamı ve sınırı</h2><div class="scroll"><table><tr><th>Kod</th><th>Ne kontrol ediyor?</th><th>Ne kanıtlamıyor / dikkat</th></tr>{rule_rows}</table></div><h2 id="cases">Beklenen cevap ile gerçek sonuç</h2>{cards}</main></html>'''
    (output/'inceleme.html').write_text(html,encoding='utf-8')
    return data['summary']


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('reports/validator_audit'))
    args=parser.parse_args()
    print(json.dumps(write_report(args.output),ensure_ascii=False))
