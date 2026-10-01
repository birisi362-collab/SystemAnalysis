# Mimari Atölyesi

Gereksinim dokümanından çıkarılan mimariyi, dayanağını kaybetmeden incelemek ve düzeltmek için yerel uygulama.
Yeni arayüzde düzenlemeler Python analiz motoruna bağlanır; SQLite'a kaydedilir ve sonraki açılışta korunur.

## Başlatma

Bu klasörde `run_app.bat` dosyasına çift tıklayın. `run_ui.bat` aynı uygulamayı açar.
Adres: **http://127.0.0.1:8766**. Başlatıcı pencere açık kalmalı; Ctrl+C uygulamayı durdurur.
Port kullanımdaysa açık uygulamayı kullanın veya `venv\Scripts\python.exe run_workbench.py --port 8768` çalıştırın.

Yeni bilgisayarda Python 3.10+ ile:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-workbench.txt
.\venv\Scripts\python.exe run_workbench.py
```

Hazır `web/dist` dağıtımını koruyun. Kullanım sırasında Node, npm, CDN veya Graphviz kurulumu gerekmez.
İsteğe bağlı SVG dışa aktarımı için Graphviz `dot` bulunmalıdır; bulunmasa da JSON, Mermaid ve DOT üretilir.
Uygulama yalnızca bu bilgisayarda dinler; bir kurum sunucusuna çok kullanıcılı dağıtım değildir.

## İlk inceleme

1. **Aç** ile mevcut analizi seçin. Nemotron çalışması: `outputs/20260930_182611_214350`.
2. Şemada bir blok veya ok seçin. Sağ panelde açıklama, arayüz/yön, kaynak alıntıları ve ilgili kontroller açılır.
3. Alıntının **Satır / Sayfa** düğmesi ilgili kaynak kaydına götürür. Belgeden çıkarılan kaynak metin korunur; orijinal PDF sayfasının görsel gösterimi bu sürümde yoktur.
4. **Düzenle** ile ad, sınıf, yön, protokol, açıklama ve dayanak değiştirin. Kaynak eklerken metin otomatik getirilir; yalnız ilgili bölümünü alıntılayabilirsiniz.
5. Her değişiklik için gerekçe girin. Mühendis adını üst çubuktan düzenleyin. Bu bir kayıt etiketi olup kimlik doğrulama veya elektronik imza değildir.

Blokları sürükleyerek yerleştirebilirsiniz. Alt tutamaçtan başka bloğun üst tutamacına bağlantı çizmek düzenleme formunu açar; kayıt ancak gerekçe ile kaydedildiğinde oluşur. **Bileşen** ve **Bağlantı** düğmeleri de aynı işlemleri yapar.
**Otomatik yerleştir**, **ekrana sığdır**, yakınlaştırma ve küçük harita büyük şemalarda gezinmeyi kolaylaştırır.

## Covered, kanıt ve karar

| Arayüzdeki kavram | Anlamı | Tek başına göstermediği |
|---|---|---|
| Karşılık seçilmiş (`covered`) | Model veya mühendis kaynak için nesneler seçmiş | Tasarımın doğru, eksiksiz veya onaylı olması |
| Alıntı metinde var | Seçilen alıntı belirtilen metinde bulunuyor | İddianın teknik anlamda doğru olması |
| Mühendis kararı | Belirli öğe hakkında gerekçeli değerlendirme | Sistemin tamamının onaylanması |

`COVERAGE_EVIDENCE_MISMATCH`: kaynak kapsama listesinde nesne seçilmiştir ama aynı kaynak nesnenin kanıt listesinde yoktur.
Örneğin 29. satırdaki LVDS bağlantısının kendi alıntısı doğru olabilir; uç bileşenleri doğrudan kanıt olmadan ayrıca seçmek yine bu hatayı doğurabilir.

**Kaynak → Eşleştirmeyi düzenle** ekranında gerçek doğrudan ilişkileri seçin. **Seçimleri mevcut kanıtlardan getir**, eldeki kanıt bağlantılarını forma taşır; kaydetmez, kapsam durumunu veya onay kararını kendisi vermez. Doğrudan dayanak gerçekten varsa bunun yerine nesneye doğru alıntıyı ekleyebilirsiniz. Uç bileşenler ayrıca bağlamsal ilişki olarak görünür.

İlk Nemotron incelemesinde 19 böyle uyuşmazlık ve 1 nesnesiz `covered` kaydı vardır. Bunlar uygulama tarafından gizlenmez. İlgili kayıt değişince kontroller yeniden hesaplanır.
Dokümanda olmayan alıntı kaydedilemez. Kanıtsız bir mühendislik eklemesi yapılabilir; dayanak eksikliği ve mühendis gerekçesi görünür kalır.

## Bulgular, öneriler ve müdahale

**İnceleme** bölümünde iki ayrı liste vardır:

- **Mühendislik konuları:** modelin bulgusu, ilgili kaynak ve nesneler, önerilen işlem. Mühendis bulgu ekleyebilir veya mevcut bulgunun metnini, önemini, dayanağını ve ilişkilerini düzenleyebilir; kabul, ret, çözüldü veya başka bulguyla birleştirildi kararı verebilir. İlk bulgu orijinal kayıtta korunur.
- **Otomatik kontroller:** yazılımın kayıt/alıntı/protokol kontrolleri. Her kayıt açıklama ve düzeltme önerisiyle ilişkilendirilir. Bir bulguya “çözüldü” demek bu kontrolleri gizlemez.

**Varsayımlar** bölümünde varsayım metinleri düzenlenebilir ve ayrı karar verilebilir. Modelin açık soruları ve eksik bilgi listesi de gösterilir.
Mimari veya dayanak değişince etkilenmiş kararlar **Yeniden incelenmeli** olur. Mimari değişikliği, ilişkisi eksik olabilecek model bulgularına verilmiş kararları da yeniden incelemeye düşürür. Otomatik anlamsal yeniden değerlendirme veya ikinci model çağrısı yapılmaz.

## Kayıt, geri alma ve dışa aktarma

- Orijinal çıktı dosyaları değişmez. Çalışma kopyası ve revizyonlar `workbench_data/reviews.sqlite3` içindedir.
- Her kaydetme, ad/gerekçe/zaman ile tam durum revizyonu oluşturur. Geri al/yinele sayfa yenilemesinden sonra da çalışır.
- Yeni işlem, geri alınmış dalın yineleme yolunu kapatır; eski kayıtlar olay geçmişinden silinmez.
- Aynı inceleme iki sekmede açılıp eski sürümle yazılmaya çalışılırsa değişiklik reddedilir ve güncel sürüm açılır.
- Bağlı bileşen silinirken bağlantılarıyla birlikte kaldırılması açıkça seçilmelidir. Geri al ile bütünü geri gelir.
- **Geçmiş**, nesne/kapsama farklarını ve tüm işlem gerekçelerini gösterir. Karar ve varsayım işlemleri olay listesinde yer alır.
- **Çıktı paketi**, güncel JSON/Mermaid/DOT/rapor dosyalarını, `original_analysis_result.json` ve karar/geçmiş/yerleşimi içeren `engineering_review.json` dosyasını ZIP olarak verir.

Yedeklemek için uygulamayı kapatıp `workbench_data` klasörünü kopyalayın. ZIP inceleme kayıtlarını okunabilir şekilde taşır; başka bilgisayarda kaldığı yerden sürdürmek için bu sürümde veritabanı yedeği kullanılır. Yalnız `analysis_result.json` içe aktarmak yeni bir inceleme başlatır; eski kararları otomatik geri yüklemez.

## Yeni analiz

**Yeni analiz** ekranında TXT/DOCX/PDF yolu ve profil seçilir. Bağlantı ayarlarında model, servis adresi, süre sınırı, çıktı token sınırı ve ikinci tur inceleme ayarlanabilir.
API anahtarı mevcut `.env` dosyasından veya o analiz için formdan alınır. Form anahtarı SQLite'a veya tarayıcı yerel depolamasına kaydedilmez.
**Modelle analizi başlat**, doküman içeriğini ekranda görünen servise gönderir. Kaydedilmiş çıktıyı açmak veya düzenlemek model çağrısı yapmaz.
İlerleme ekranda gösterilir; sonuç otomatik açılır. Aynı anda bir analiz çalışır. Kapatılmış bir uygulamadaki yarım iş yeniden başlatmada kesintiye uğramış sayılır; otomatik yeniden ücretli çağrı yapılmaz.

**API olmadan örnek dene**, `evaluation/cases/dev_01` örneğini hazır test yanıtıyla çalıştırır. Bu Nemotron başarısını ölçmez.

## Teknoloji kararı

| Seçenek | Değerlendirme |
|---|---|
| React + React Flow | Seçildi. Özelleştirilebilir bileşenler, tıklanabilir kenarlar, tutamaçla bağlama, sürükleme, yakınlaştırma ve yerleşim saklama ihtiyaçlarına uygun. |
| Cytoscape.js | Güçlü grafik analizi ve yerleşim seçenekleri var. Bu uygulamanın form ve mühendis kararlarıyla bütünleşen görsel düzenleme ihtiyacı için React Flow tercih edildi. |
| Streamlit | İlk analiz ekranı korunuyor; yeni etkileşimli çalışma alanı React ile ayrı geliştirildi. |

Karar resmi belgelerdeki yeteneklere dayanır: [React Flow özel düğümler](https://reactflow.dev/learn/customization/custom-nodes), [tutamaçlar](https://reactflow.dev/learn/customization/handles), [kaydet/geri yükle örneği](https://reactflow.dev/examples/interaction/save-and-restore), [MIT lisanslı kaynak kodu](https://github.com/xyflow/xyflow), [Cytoscape.js](https://js.cytoscape.org/).
Python motorunu korumak ve derlenmiş arayüzü aynı yerel adresten sunmak için [FastAPI](https://fastapi.tiangolo.com/tutorial/static-files/) kullanıldı.

## Kod ve geliştirme

| Dosya | Sorumluluk |
|---|---|
| `web/src/main.jsx`, `styles.css` | Türkçe arayüz, şema, editörler, inceleme, geçmiş |
| `app/workbench.py` | Yerel API, analiz işleri, ZIP, statik arayüz |
| `app/review_store.py` | SQLite revizyonları, tutarlılık ve karar geçerliliği |
| `run_workbench.py`, `run_app.bat` | Başlatma |
| `tests/test_workbench.py` | Değişiklik/kayıt/geri alma/API regresyonları |

Arayüzü yeniden derlemek için Node 22.12+ veya desteklenen daha yeni sürüm gerekir:

```powershell
cd web
npm ci
npm run build
```

Geliştirmede Python sunucusunu çalıştırın; `web` içinde `npm run dev` kullanın. Vite `/api` isteklerini 8766'ya yönlendirir.
Tüm eski ve yeni testler için `requirements.txt` kurulmalı ve `run_tests.bat` çalıştırılmalıdır; Streamlit yalnız eski arayüz regresyon testi içindir.

## Plandaki yerimiz ve kapsam

Doküman → model taslağı → doğrulama → etkileşimli mühendis incelemesi → gerekçeli düzeltme → revizyonlu kayıt → güncel çıktı zinciri bu sürümde çalışır.
Bu, yerelde kullanılabilir ilk mühendis çalışma uygulamasıdır. Modelin çıkarım kalitesini artıran yeni bir eğitim/prompt optimizasyonu değildir.
Sonraki aşamalar: gerçek dokümanlarla kullanıcı kabulü, mühendis tarafından doğrulanmış referanslarla model başarısı ölçümü, PDF sayfa görüntüsü üzerinde vurgulama, kurum içi çok kullanıcılı kimlik/rol yönetimi ve gözden geçirme süreçleri.
Kaynak metni bulunması anlamsal doğruluk ispatı değildir; mevcut kurallar eksik tüm arayüzleri saptayamaz. Canlı sağlayıcı erişimi ve kalitesi ayrıca değerlendirilir.
