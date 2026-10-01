# V6 değerlendirme rehberi

## Üç farklı kanıt türü

1. **Otomatik kod testleri:** Hatalı alıntı, protokol, referans, API yanıtı, skor ve arayüz durumunu sınar.
2. **Fixture / replay:** Hazır veya daha önce kaydedilmiş yanıtla uygulamayı çalıştırır. Model kalitesi ölçmez.
3. **Live:** Gerçek endpoint’e yeni istek yapar. Model/prompt davranışını taslak referanslarla karşılaştırır.

Başka bir LLM’yi hakem yapmıyoruz. Referans JSON’lar başlangıç taslağıdır; mühendis incelemesinden
sonra sabitlenmelidir. Özellikle olumsuz, belirsiz ve çelişkili gereksinimlerde doğru mimari temsili
birden fazla olabilir. Böyle durumlarda referansı ve isim eşanlamlarını açıkça güncelle, sürüm değiştir.

## Kodun sağlamlığını sınama

```bat
python -m unittest discover -s tests -v
```

Testler gerçek NVIDIA/OpenRouter servisine istek göndermez. HTTP davranışları test çiftleriyle
sınanır; Streamlit test aracı ekranın yeniden çalıştırılması sırasında sonuçların korunduğunu kontrol eder.

## API’siz tüm örnekleri çalıştırma

```bat
python -m app.evaluation --mode fixture --split all --output reports/offline_check
```

20 örneğin işlenmesi gerekir. Bu modda referanslara uyan hazır mimariler kullanıldığı için
puanların yüksek olması beklenir; **DeepSeek’in veya başka bir modelin başarısı hakkında kanıt değildir**.
Fixture inceleme cevapları da tam bir semantik bulgu referansı değildir.

## Canlı değerlendirme planı

İlk adım: API rehberindeki iki örneklik smoke koşusu.
Sonra iki modeli aynı 12 geliştirme örneğinde çalıştır:

```bat
python -m app.evaluation --mode live --profile profiles/nvidia_deepseek.json --split dev --output reports/deepseek_dev
python -m app.evaluation --mode live --profile profiles/openrouter_nemotron.json --split dev --output reports/nemotron_dev
```

Her koşu taban 24, varsayılan tek tekrar denemesiyle en fazla 48 HTTP çağrısıdır.
Günlük kotana göre `--limit` kullan. Koşular ardışık çalışır. Tekrar sayısı `--repeats 3` yapılırsa
çağrı bütçesi de üç katına çıkar. Yalnızca son adaylarda tekrar yap.

Prompt/model ayarları sabitlendikten sonra 8 holdout örneğini çalıştır:

```bat
python -m app.evaluation --mode live --profile profiles/nvidia_deepseek.json --split holdout --repeats 3 --output reports/deepseek_holdout
```

Holdout'u tekrar tekrar prompt ayarlamak için kullanırsan bağımsız son kontrol niteliği zayıflar.
Bu küçük test seti ürün kabul standardı değildir; gerçek hedef ortama uygun ek örnekler gerektirir.

## Raporları okuma

| Alan | Yorum |
|---|---|
| `run_completion_rate` | Çıkarım ve ikinci turu tamamlanan koşular / tüm koşular. |
| `extraction_completed` | Mimari JSON’u şemaya uyan koşu sayısı. |
| `directed_connections.precision` | Üretilen bağlantıların ne kadarı doğru uç ve yöne sahip? |
| `directed_connections.recall` | Beklenen yönlü bağlantıların ne kadarı bulundu? |
| `connections_with_protocol` | Uçlar ve yönle birlikte protokol eşleşmesi. |
| `connections_with_type` | Uçlar ve yönle birlikte bağlantı türü eşleşmesi. |
| `components` | Bileşen isimlerinin referans isim/eşanlam listesiyle eşleşmesi. |
| `quote_containment` | Alıntı gerçekten verilen kaynak kaydında mı? Anlamsal desteği kanıtlamaz. |
| `validation_errors` | Deterministik doğrulama hataları. Sıfır olması doğruluk onayı değildir. |
| `findings_semantic_score` | Bilerek `null`; mühendis değerlendirmesi gerekir. |

Precision = TP / üretilen; recall = TP / beklenen. Tekrarlanan bağlantılar fazladan üretim olarak
cezalandırılır. Payda sıfırsa `null` gösterilir; boş yanıt %100 başarı sayılmaz.
Mimari çıkarılamayan koşular kalite hesabına girmez fakat tamamlanma oranında başarısızdır.
Bu yüzden kalite puanlarını tamamlanma oranıyla birlikte değerlendir.

İsim eşleşmesi bilinçli olarak muhafazakârdır: yalnızca referans adı ve `aliases` kullanılır;
bulanık benzerlik ile yanlış bileşen eşleştirilmez. `unmatched_component_names` listesindeki
geçerli alternatif isimleri insan kontrolüyle referansa ekleyebilirsin. Prompttaki ID’ler değişse de
bileşen isimleri eşleşiyorsa bağlantılar karşılaştırılabilir.

`human_review.csv` içinde üretilen bulgular ve beklenen inceleme maddeleri bulunur.
Her bulgu için doğru / yanlış / belirsiz kararını ve notunu doldur. Beklenen maddelerin
atlanıp atlanmadığını ayrıca kaydet. V6 bu dosyadan otomatik toplam semantik skor hesaplamaz.

## Çalışma kaydı ve replay

Her analizde:
- `source_catalog.json`: tam kaynak metni, kimlik ve konum.
- `architecture_pass1.json`: ikinci turdan bağımsız mimari.
- `analysis_result.json`: birleşik sonuç, inceleme durumu ve uyarılar.
- `run_record.json`: promptlar, son model yanıtları, kullanım bilgisi (sağlayıcı döndürürse),
  süre, endpoint/model ayarları, hata kodları ve içerik hash’leri.
- `report.html`, DOT ve Mermaid; Graphviz sistem aracı varsa SVG.

Başarısız bir koşuda bütün çıktıların oluşması beklenmez; çalışma kaydı teşhis için saklanır.
API anahtarı/Authorization başlığı kayıt altına alınmaz; gizli reasoning alanları da saklanmaz.
Kaynak metinleri ve final yanıtlar ise kaydedilir.

```bat
python -m app.main evaluation/cases/dev_01.txt --replay reports/deepseek_smoke/dev_01/run_1/run_record.json --output outputs/replay_01
```

Replay yeni API isteği yapmaz. Prompt hash’i eşleşmezse durur. Aynı kaydı bir prompt iyileştirmesinin
kanıtı olarak kullanamayız; prompt değişikliğini canlı koşuyla ölçmeliyiz.

## V6 sınırları

- Karakter bütçesi varsayılan 60000; bu bir token sayacı değildir. Aşılırsa metin kesilmez, durulur.
- Otomatik bölümleme/bölümler arası mimari birleştirme bu sürümde yoktur.
- OCR yoktur; metinsiz PDF sayfası varsa sessizce atlanmaz, analiz durur.
- Gereksinim ayırma sezgiseldir; kaynak sekmesini kontrol et. DOCX'te tablo/paragraf sırası korunur;
  başlık/altbilgi, metin kutuları ve karmaşık çizim içerikleri desteklenmez.
- Alıntının varlığı, alıntının bağlantıyı gerçekten desteklediği anlamına gelmez.
- Protokol kontrolü sınırlı bir teknoloji sözlüğü kullanır; çoklu arayüz içeren cümleler inceleme uyarısı doğurabilir.
- Yönün anlamsal doğruluğu test setinde ölçülür; genel amaçlı Python doğrulayıcı bunu kanıtlamaz.
- Şema düzenleme, kullanıcı onaylarının kalıcı saklanması, çok kullanıcılı proje yönetimi sonraki aşamadır.
- İç ağ modelinin kabul testi yapılmadan dış ağ sonuçları üretim doğruluğu sayılmaz.
