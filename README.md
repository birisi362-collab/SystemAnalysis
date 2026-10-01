# System Architecture Analyzer — V6

Gereksinim dokümanından kaynakla ilişkilendirilmiş mimari taslağı çıkarır; doğrulama sorunlarını ve
LLM inceleme bulgularını gösterir. V6, model başarısıyla kodun sağlamlığını ayrı ölçmek için
çevrimdışı test, kayıtlı yanıt replay ve canlı karşılaştırma araçları içerir.

## Etkileşimli uygulama — Mimari Atölyesi

Yeni ana arayüz React + React Flow, yerel servis FastAPI, inceleme kaydı SQLite kullanır.
Şemadan kaynağa geçiş, bileşen/bağlantı düzenleme, gerekçeli karar, kapsama düzeltme,
geri al/yinele, değişiklik geçmişi ve çıktı paketi içerir. Streamlit bu arayüzün parçası değildir.

Bu bilgisayarda **`run_app.bat`** dosyasını açın; uygulama `http://127.0.0.1:8766` adresinde çalışır.
Hazır derleme `web/dist` içinde; kullanım için Node gerekmez.
Yeni kurulumda: `python -m pip install -r requirements-workbench.txt`.
Ardından: `python run_workbench.py`.

**[Kullanım, teknoloji seçimi ve geliştirme notları](docs/MIMARI_ATOLYESI_TR.md)**

Sürüm 1.2: sade konu listesi, üç adımlı konu ayrıntısı, anlaşılır kaynak etiketleri,
doğrudan/bağlam ilişkileri, Geçmiş bölümünde değişiklik karşılaştırması, gerekçeli
kapatma ve ilgili veri değişince yeniden inceleme. **[Yeni inceleme akışı](docs/INCELEME_AKISI_TR.md)**.

### GitHub'dan başka bilgisayarda devam etme

Depoyu GitHub'a gönderdikten sonra başka bilgisayarda:

```powershell
git clone https://github.com/<kullanici>/<depo>.git
cd <depo>
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-workbench.txt
.\run_app.bat
```

`web/dist` hazır arayüzü içerdiği için Node.js kurulumu gerekmez. Mühendis kararlarını ve yerleşimleri taşımak isterseniz `workbench_data` klasörünü ayrıca güvenli bir yoldan kopyalayın; bu klasör GitHub'a gönderilmez. API anahtarlarını GitHub'a koymayın; yeni bilgisayarda `.env.example` dosyasını `.env` olarak kopyalayıp anahtarı yerel olarak girin.

## Geliştirme ve test

Python 3.10+; Windows/Anaconda veya Linux:

```bat
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m unittest discover -s tests -v
```

Yeni uygulamada **Yeni analiz → API olmadan örnek dene**, hazır test yanıtıyla çalışır; gerçek model çağrısı yapmaz.
Windows'ta `run_tests.bat` geliştirici doğrulaması için kullanılabilir.

## Ücretsiz API kurulumu

Ayrı yönerge: **docs/UCRETSIZ_API_REHBERI_TR.md** (ayrıca HTML sürümü).
NVIDIA V4.1 Flash ve OpenRouter Nemotron 3 Ultra profilleri hazırdır.
V4 Flash’ın NVIDIA ücretsiz endpoint’i 30 Eylül 2026 kontrolünde kaldırılmıştı;
V4.1 profili bununla aynı model değildir. Profil JSON’undan model/endpoint değiştirilebilir.

Anahtarlar `.env` üzerinden veya arayüzden alınır. `.env.example` dosyasını `.env` olarak kopyala.
Anahtarsız canlı API çalışmaz. Eski arayüzdeki **Bağlantıyı test et** seçeneği veya mevcut
bağlantı test araçları ile hesabındaki erişimi doğrulayabilirsin. Yeni arayüzde dosya yolu,
profil ve bağlantı ayarları **Yeni analiz** penceresindedir.

## Değerlendirme

```bat
python -m app.evaluation --mode fixture --split all --output reports/offline_check
python -m app.evaluation --mode live --profile profiles/nvidia_deepseek.json --split dev --limit 2 --output reports/deepseek_smoke
```

Ayrıntılı kullanım ve skorların yorumu: **docs/DEGERLENDIRME_REHBERI_TR.md**.
20 sentetik taslak referans: 12 dev, 8 holdout. Referansların mühendis tarafından incelenmesi gerekir.
Fixture skorları bir model benchmark'ı değildir. Canlı benchmark sonuçları pakette yoktur.

## V6 değişiklikleri

- Çok satırlı açık kimlikli gereksinimler birleştirilir; kaynak konumları tutulur.
- DOCX tablo/paragraf sırası korunur. Metinsiz PDF sayfası sessizce atlanmaz.
- Gerçek alıntı eşleşmesi, protokol uyuşmazlığı, bozuk kapsama bağlantısı ve ikinci tur kanıtları denetlenir.
- İkinci tur başarısız olursa ilk turun mimarisi saklanır; “bulgu yok” diye sunulmaz.
- UI sonuçları oturumda korunur; kaynak kaydından ilişkili öğelere bakılır ve çalışma ZIP’i indirilir.
- CLI, UI ve Spyder aynı bağlantı ayarlarını kullanır; .env gerçekten yüklenir.
- API hata kodları, çıktı kesilmesi, süre ve son yanıt kaydı; sınırlı yeniden deneme.
- Model otomatik değiştirilmez. 401/403/404, bozuk JSON ve timeout körlemesine tekrarlanmaz.
- Kayda dayalı replay prompt hash'ini doğrular; başka promptun testi olarak kullanılamaz.
- HTML/CSV/JSON değerlendirme raporları ve insan inceleme CSV’si üretilir.

## Çıktılar ve sınırlamalar

Her koşu yeni/boş bir çıktı klasörü kullanır. `analysis_result.json`, kaynak kataloğu, çalışma kaydı,
HTML raporu ve şema dosyaları oluşur. SVG için ayrıca sistem Graphviz `dot` programı gerekir;
program yoksa diğer çıktılar üretilir, `graphviz_error.txt` açıklama içerir.

Arayüz sonuçları oturuma aittir; tarayıcı/sunucu yeniden açılması için kalıcı proje veritabanı yoktur.
Çalışma ZIP’ini indir. Kayıtlar kaynak metni içerir.

Bu sürüm: tek doküman, iki LLM aşaması + deterministik kontroller. Otomatik uzun doküman bölümleme,
OCR, şema düzenleme ve kalıcı mühendis onay akışı sonraki aşamalardır. Hiçbir otomatik kontrol,
model çıktısının mühendislik doğruluğunu tek başına garanti etmez.

`docs/TEST_SONUCLARI_TR.md` teslim öncesi doğrulamanın kapsamını açıklar.


Berkay---
git clone https://github.com/birisi362-collab/SystemAnalysis.git
cd SystemAnalysis

python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-workbench.txt

.\run_app.bat
