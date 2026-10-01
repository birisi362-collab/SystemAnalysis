# Validatör incelemesi

Bu dokümandaki 37 deney / 7 sınır sonuçları ilk incelemeye aittir. Sonraki uygulama geliştirmesinde iki protokol boşluğu kapatılmıştır; güncel rapor 38 deney, 33 karşılanan beklenti ve 5 anlam sınırı içerir. Güncel akış için `INCELEME_AKISI_TR.md` dosyasını okuyun. Rapor üreticisi kuralları ölçer; çalıştırılması üretim kurallarını değiştirmez. Model çağrısı,
çıktı dosyası düzenleme veya mühendis kararlarını değiştirme işlemi yapmaz.

## Raporu üretmek

Proje klasöründe PowerShell üzerinden:

```powershell
.\venv\Scripts\python.exe -m app.validator_audit
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

`venv` yoksa bağımlılıkların kurulu olduğu Python ile `python -m ...` kullanın.
Rapor `reports/validator_audit/inceleme.html` dosyasına, deney girdileri ve sonuçları
`reports/validator_audit/audit.json` dosyasına yazılır. HTML tarayıcıda açılabilir;
internet veya çalışan uygulama sunucusu gerektirmez. Her deneyin girdisi açılabilir.
Raporlar Git tarafından dışlanır; üretici kod ve bu doküman kaynak kodla paylaşılır.

## Ne bulundu?

37 sentetik deneyde 30 beklenti karşılandı, 7 sınır/kapsam farkı görünür oldu.
27 kontrol kodunun tamamı en az bir örnekte üretildi. Bu sayı bir doğruluk oranı
değildir: örnekler rastgele seçilmiş gerçek belge örneklemi değildir. Kural
deneyleri beklenen kodun varlığını, belirtilmiş yasak kodların yokluğunu denetler;
yalnız doğru başlangıç örneği hiçbir uyarı olmamasını zorunlu tutar. Tetiklenen
diğer uyarılar raporda ayrıca gösterilir.

| Deney | Ana validatör | Uygulama | Yorum |
| --- | --- | --- | --- |
| RS-422 kanıtına RS-422 / UDP beyanı | Uyarı yok | Desteksiz protokol uyarısı | Aynı amaç için iki farklı kontrol kapsamı |
| Teknoloji belirtmeyen kaynağa UDP eklemek | Uyarı yok | Desteksiz protokol uyarısı | Ana kontrol bilinen teknoloji için bu durumda sessiz |
| A → B yerine B → A | Uyarı yok | Uyarı yok | Yön anlamı denetlenmiyor |
| “RS-422 kullanılmayacaktır” için RS-422 seçmek | Uyarı yok | Uyarı yok | Olumsuzluk denetlenmiyor |
| Ölçüm aktarımını güç bağlantısı yapmak | Uyarı yok | Uyarı yok | Bağlantı türünün anlamı denetlenmiyor |
| Açık mimari gereksinimi not_architectural yapmak | Uyarı yok | Uyarı yok | Sınıflandırma doğruluğu denetlenmiyor |
| Kapak rengi cümlesini A → B bağlantısının kanıtı yapmak | Uyarı yok | Uyarı yok | Alıntının ilgisi denetlenmiyor |

İlk iki durum ana validatörün kontrol kapsamındaki boşluklardır; uygulamada ek
kontrol vardır. Son beş durum mevcut metin/kimlik kontrollerinin anlam sınırıdır.
Bunlar deterministik kodun kendi tanımını yanlış uyguladığını göstermiyor;
“kontrolden geçti, dolayısıyla mimari doğrudur” beklentisinin karşılanmadığını
gösteriyor. Yeni anlamsal kontroller yanlış alarm üretebileceğinden mühendis
tarafından onaylanmış örneklerle ayrıca değerlendirilmelidir.

## Coverage hatası neden kafa karıştırıyor?

`covered`, modelin “bu kaynağın şemada karşılığı var” beyanıdır. Validatör bu
beyanı bağımsız bir mühendislik incelemesiyle doğrulamaz.

`COVERAGE_EVIDENCE_MISMATCH` şu dar soruyu sorar: “Bu kaynakla ilişkilendirilen
nesnenin kanıt listesinde aynı kaynak kimliği var mı?” İkinci kaynak A ile
bağlamsal olarak ilişkili olduğunda, A'nın kanıtında yalnız ilk kaynak varsa
`error` çıkar. Deney bunu yeniden üretiyor. Uyarı izlenebilirlik listelerinin
uyuşmadığını gösterir; A bileşeninin yanlış olduğunu tek başına göstermez.

Kanıtın kaynak kimliği var, alıntısı uydurma ise kapsama eşleşmesi geçebilir;
ayrı `QUOTE_NOT_IN_SOURCE` kontrolü bunu yakalar. Dolayısıyla kapsama uyarısının
yokluğu alıntının doğrulandığını da ifade etmez.

## Test sonuçlarını nasıl okumalı?

İlk incelemede 7, güncel testlerde 5 beklenti `expectedFailure` olarak görünür. Bunlar bilinen,
henüz karşılanmayan beklentilerdir; başarı sayılmamalıdır. Böylece normal regresyon
testleri çalışırken ürün sınırları da görünür kalır. Bir kontrol geliştirildiğinde
ilgili testin bu işareti kaldırılmalı ve onaylanmış yeni davranış açıkça sınanmalıdır.
Raporun örnek amaçlı `DIRECTION_CONFLICT`, `NEGATED_PROTOCOL` gibi beklenti adları
mevcut kontrol kodları değildir.

Bu çalışma gerçek veride yanlış pozitif/negatif oranı ölçmez. Bunun için gerçek
gereksinim ve şema örneklerini mühendislerin önce etiketlediği, doğru ve yanlış
örnekler içeren bağımsız bir referans kümesi gerekir. Modelin kendi cevabı
referans doğru olarak kullanılmamalıdır.

## Önerilen geliştirme sırası

1. Ana validatör ile uygulamadaki kontrolü ortaklaştırın; aynı dosya için aynı
   kontrol sonucu üretilsin. Bu incelemedeki protokol çiftlerini regresyon olarak tutun.
2. Kesin kayıt sorunlarını (olmayan kimlik, kaynakta bulunmayan alıntı) mühendislik
   yorumlarından ayırın. Bağlamsal ilişki ile doğrudan kanıtı ayrı veri alanları yapın.
3. Arayüzde aynı çözüm gerektiren kayıtları gruplayın; kaynak cümlesini, ilgili
   nesneyi ve düzeltme eylemini birlikte gösterin. Covered durumunu “tam ve doğru
   tasarım onayı” gibi sunmayın.
4. Anlamsal kontrolleri mühendis onaylı örneklerle geliştirin; öneri ile kesin
   kayıt hatasını ayırın. Yön ve olumsuzluk deneyleri başlangıç örnekleridir.
5. Kabul gerekçesi / düzeltme / yeniden kontrol akışını bu ayrımla bağlayın.
   Mühendis uyarıyı gerekçeyle kabul edebilmeli; ilgili veri değişirse tekrar inceleme
   istenmelidir. Kararın kapatılması teknik kontrolün başarılı olduğu anlamına gelmez.

27 kuralın tam tablosu ve sınırları üretilen HTML/JSON raporunda yer alır;
tablonun kaynak tanımı `app/validator_audit.py` içindeki `RULES` listesidir.
