# Mimari Atölyesi — System Architecture Analyzer

Gereksinim belgesinden mimari taslak oluşturur; mühendisin kaynak metni, şemayı ve yapay zekâ önerilerini aynı çalışma alanında incelemesini sağlar. Bileşenler ve bağlantılar düzenlenebilir, eklenebilir ve kaldırılabilir. Yapay zekâ bulguları öneri olarak sunulur; şema değişikliklerini mühendis önizleyerek uygular.

Arayüz **React + React Flow**, yerel servis **FastAPI**, kalıcı çalışma kaydı **SQLite** kullanır. Uygulama bilgisayarınızda `http://127.0.0.1:8766` adresinde çalışır. Canlı model değerlendirmesinde belge ve mimari içeriği seçtiğiniz model sağlayıcısına gönderilir.

## Kurulum ve çalıştırma

Windows için doğrulanmış çalışma ortamı **Python 3.12**'dir. İlk kurulum için Python 3.12 ve Git gerekir. Hazır arayüz `web/dist` içinde bulunduğundan normal kullanımda Node.js kurulumu gerekmez.

PowerShell'de:

```powershell
git clone https://github.com/birisi362-collab/SystemAnalysis.git
cd SystemAnalysis
py -3.12 -m venv .venv-workbench
.\.venv-workbench\Scripts\python.exe -m pip install -r requirements-workbench.txt
Copy-Item .env.example .env
```

`.env` dosyasında kullanacağınız sağlayıcının anahtarını doldurun. Örneğin OpenRouter profili `OPENROUTER_API_KEY` alanını kullanır. Anahtar **Belge aç / Yeni değerlendirme → Bağlantı ve gelişmiş seçenekler** alanından ilgili işlem için de girilebilir.

Ardından:

```powershell
.\run_app.bat
```

Sonraki açılışlarda **`run_app.bat` dosyasına çift tıklamak yeterlidir**. Tarayıcı otomatik açılır. Uygulamayı kapatmak için açılan terminalde **Ctrl+C** kullanın. `py` komutu bulunmuyorsa sanal ortamı kurulu Python 3.12'nin tam yoluyla oluşturun.

Başlatıcı `.venv-workbench` ortamını öncelikle seçer ve sunucuyu açmadan önce güvenli bağlantı ortamını kontrol eder. Aynı proje ve veri klasörüyle uygulama zaten çalışıyorsa mevcut uygulamayı açar.

Alternatif başlatma ve farklı port:

```powershell
.\.venv-workbench\Scripts\python.exe run_workbench.py
.\.venv-workbench\Scripts\python.exe run_workbench.py --port 8769
```

Başka bir servis varsayılan portu kullanıyorsa farklı port seçebilirsiniz. Veri klasörü isteğe bağlı `--data-dir` parametresiyle değiştirilebilir.

## Güncel çalışma akışı

1. **Belge aç** ile TXT, DOCX veya metin içeren PDF seçin. Aynı pencereden kaydedilmiş bir çalışma, önceki analiz çıktısı veya çalışma ZIP paketi de açılabilir.
2. Model profilini seçip **Analizi başlat** düğmesine basın. İlk aşama mimariyi çıkarır; ikinci aşama kaynak metinle birlikte değerlendirip mühendislik bulguları üretir. Anahtarsız denemek için **Bağlantı ve gelişmiş seçenekler → Örnek verilerle çevrimdışı dene** seçeneğini kullanın.
3. Solda kaynak belgeyi, ortada etkileşimli şemayı, sağda seçilen öğenin ayrıntılarını ve önerileri görün. Kaynak metne veya şema öğesine tıklayarak ilişkili bilgileri inceleyin.
4. Bileşen ve bağlantıları seçerek düzenleyin; araç çubuğundan yeni öğe ekleyin. Bağlantı yönü düzenlenebilir; çift yönlü ve aynı iki birim arasındaki birden fazla bağlantı desteklenir. Şemayı sürükleyerek yerleştirebilir veya otomatik yerleşim kullanabilirsiniz.
5. **Öneriler ve notlar** bölümündeki bulguyu açın, açıklamasını ve varsa değişiklik önerisini inceleyin. Öneriyi önizleyip **Uygula** ile tasarıma ekleyin. Kendi inceleme notlarınızı da ekleyebilirsiniz.
6. Konuları **Bekleyen**, **Bilgi bekleyen** ve **Tamamlanan** durumlarıyla takip edin. Mühendis kararlarını gerekçelendirebilir; **Geçmiş** üzerinden değişiklikleri karşılaştırabilir ve geri al/yinele kullanabilirsiniz.
7. Düzenlenmiş tasarımı tekrar inceletmek için **Yeni değerlendirme** başlatın. Yeni bulgular öneri listesine eklenir; mevcut şema kendiliğinden değiştirilmez.

Ana çalışma alanı otomatik validasyon uyarılarını çözme veya kaynak ilişkilerini tek tek kanıtlama üzerine kurulmaz. Model yanıtındaki biçim, kaynak alıntısı ve öğe kimliği sorunları uygulama içinde denetlenir; kullanılamayan sonuçlar **Değerlendirme ayrıntıları** içinde açıklanır.

## TİD, varsayımlar ve proje asistanı

Üstteki **Şema · TİD · Varsayımlar** ana sekmeleri çalışma alanlarını ayırır. Orijinal belge korunur; yeni değerlendirmeler güncel TİD çalışma sürümünü, mimariyi ve mühendis kararlarını birlikte kullanır.

- **TİD:** Bölüm başlıkları ve aramayla geniş belge alanında çalışın. Bir maddeyi seçip **Düzenle** ile değiştirin; çalışma sürümünü veya orijinal belgeden alınan metni Word/TXT olarak indirin. **Şemaya göre güncelleme öner** asistan konuşmasına bir istek hazırlar. Her şema değişikliği ister değişikliği gerektirmez.
- **Varsayımlar:** Başlıklar varsayım metnidir; sistem kimlikleri arayüzde gösterilmez. **İnceleme bekleyen / Kabul edilen / Reddedilen / Tümü** filtreleri ve adetleri vardır. Yeniden inceleme gereken eski kararlar hem ilgili karar filtresinde hem inceleme bekleyenlerde görünür. **Kabul et / Reddet** ile gerekçenizi ve varsa doğru bilgiyi girin; kararı önizleyip uygulayın. Karar sonrası ilgili filtre açılarak kaydedilen durum gösterilir.
- **Karar ve etkileri:** Kararı kaydetmek şemayı veya TİD’i kendiliğinden değiştirmez. Kaydedilen kararın **Şema ve TİD etkilerini öner** düğmesi gerekli düzenlemeleri hazırlamak için asistana istek aktarır. Öneri ayrıca önizlenir ve onayla uygulanır. Doğru alternatif bilinmiyorsa asistan bunu uydurmamalıdır.
- **Yeniden inceleme:** Kararlar yalnızca ilgili teknik dayanaklarla takip edilir. İlgili öğeler belirtilmemişse varsayım tüm projeye bağlı sayılmaz. Yerleşim, bileşenin görüntüleme adı, bölüm adı, liste sırası ve boşluk düzenlemeleri kararları yeniden açmaz. İlgili teknik içerik değiştiğinde eski karar ve gerekçe korunarak **Yeniden inceleme gerekli** uyarısı çıkar.
- **Önizleme:** Geniş, ortalanmış pencerede gerekçe, etkilenen öğeler ve önce/sonra karşılaştırması bulunur. Şema/TİD değişikliğinde her kararlı varsayım için **Yeniden değerlendir / Yeniden değerlendirmeye gerek yok** seçilebilir; **Diğer varsayımları da göster** ile otomatik olarak etkilenmeyenler de incelemeye açılabilir. Seçim değişince **Düzenlemeleri yeniden önizle**, ardından **Değişiklikleri uygula** kullanılır. “Gerek yok” yalnızca o değişikliği kapsar; sonraki ilgili teknik değişiklik yeniden inceleme gerektirebilir. Seçimler kaydedilir, dışa aktarılır ve geri alma/yineleme ile birlikte korunur.
- **Asistan:** Sağ alttaki düğme kompakt sohbet penceresini açar. Pencere daraltılıp büyütülebilir; sekmeler arasında konuşma ve mesaj taslağı korunur. Şemada öğe seçmek veya TİD’den metin seçmek kaldırılabilir bir bağlam etiketi ekler. Soru ve düzenleme isteği aynı mesaj alanından gönderilir; çalışma modu seçimi yoktur. Model önerileri kendiliğinden uygulanmaz.
- **Model Ayarları:** Model profili, sunucu, API anahtarı, süre ve çıktı sınırı tek genel alanda yönetilir; analiz, yeniden değerlendirme ve sohbet bu ayarları paylaşır. Sohbette yalnızca model seçimi bulunur. Buraya girilen anahtar sayfa oturumunun belleğinde kalır, tarayıcı depolamasına veya çalışma paketine yazılmaz. Kalıcı anahtar için mevcut yerel profil/ortam ayarları kullanılabilir; diğer tercihler tarayıcıda korunur.

TİD maddesi değiştiğinde o maddeye bağlı eski alıntılar korunur ve yeniden incelenmesi gereken dayanak olarak işaretlenir. İlgili şema öğesini düzenleyerek güncel kaynağı seçebilirsiniz. Kabul edilmiş varsayım, orijinal TİD’de yazan bir ister olarak gösterilmez.

Eski analizleri veya çalışma ZIP paketlerini **Belge aç** üzerinden modelden yeniden çıktı beklemeden kullanabilirsiniz. Eski yerel kararların dayanakları aktif revizyon geçmişinden okunur; dayanağı bulunamayan eski paketlerde kararın yeniden doğrulanması istenir.

Model işlemleri iptal edilebilir; aynı anda bir model işi çalışır. Sohbet bağlamı en fazla 120.000 karakterdir; sınır aşılırsa açıklama gösterilir. Son sekiz sohbet turu model bağlamına alınır; bütün sohbet geçmişi yerel kayıtta ve çalışma ZIP paketinde korunur. Taşınan eski öneriler tarihçe olarak gösterilir; uygulanmak için güncel projede yeniden istenmelidir.

## Değerlendirme süresi ve hata durumları

**Bağlantı ve gelişmiş seçenekler** içinde iki ayrı sınır bulunur:

| Ayar | Anlamı |
| --- | --- |
| Çıktı token sınırı | Her model çağrısının çıktı bütçesi. Arayüz başlangıcı 32.768'dir; seçilen sağlayıcının sınırları geçerlidir. |
| Toplam süre sınırı | İşlemdeki bütün model çağrılarını ve sınırlı yeniden denemeleri kapsar. Arayüz başlangıcı 600 saniyedir. Yeni belgede mimari çıkarımı ve ikinci inceleme bu bütçeyi paylaşır. |

Küçük tasarımlar tek çağrıda, büyük değerlendirmeler bölüm bölüm incelenir. Büyük belgelerde bölümler arası ilişkiler ayrıca değerlendirilir. Çıktı kesildiğinde bölüm küçültülebilir; her değerlendirmede en fazla 8 bölüm çağrısı yapılır. Tamamlanamayan işler saklanır. İlk mimari çıkarımının belge boyutu sınırı ayrı uygulanır.

- **İlerleme alanı:** geçen süreyi, bölüm durumunu ve toplam süre sınırını gösterir.
- **Değerlendirmeyi durdur:** devam eden yerel isteği keser; tamamlanan bölüm sonuçları korunur. Sağlayıcı tarafındaki üretimin veya ücretlendirmenin durduğu garanti edilmez.
- **Değerlendirme ayrıntıları:** hata nedenlerini, kullanılamayan bulguları, sağlayıcı açıklamasını ve bildirilen token kullanımını gösterir. Teşhis kaydı indirilebilir.
- **Eksik bölümleri yeniden dene:** başarılı sonuçları koruyarak eksik işleri sürdürür. Şema değişmişse güncel tasarım için yeni değerlendirme başlatın.
- **Bağlantı kesintisi:** arayüz durumu açıkça belirtir ve aynı işin durumuna yeniden bağlanmayı dener. Servis kapandıysa `run_app.bat` ile yeniden açın. Yarım kalan değerlendirmeler açılışta kesintiye uğramış olarak işaretlenir.

Model bağlantıları ayrı işlemlerde çalışır; bağlantı ortamındaki yerel çökme uygulamanın tamamını kapatmaz. Windows sisteminin güvenilir sertifika deposu kullanılır; özel CA dosyası ayarı da desteklenir.

Ayrıntılı açıklama: **[Değerlendirme ve teşhis](docs/DEGERLENDIRME_TEHSISI_TR.md)**.

## Kayıt, dışa aktarma ve başka bilgisayarda devam etme

Çalışmalar ve mühendis değişiklikleri varsayılan olarak **`workbench_data/reviews.sqlite3`** içinde kalıcı tutulur. İlk model çıktısı başlangıç kaydı olarak korunur. Yeni analizlerin çıktı dosyaları `outputs` klasöründe oluşur.

Üst çubuktaki **Çalışmayı dışa aktar** düğmesi çalışma ZIP paketini indirir. Paket güncel şemayı, özgün model çıktısını, TİD çalışma sürümünü (DOCX/TXT), varsayımları, mühendis kararlarını, sohbeti, yerleşimi ve değişiklik geçmişini içerir. Başka bilgisayarda uygulamayı kurduktan sonra **Belge aç** ile bu ZIP paketini açabilirsiniz. Tüm yerel arşivi taşımak için uygulama kapalıyken `workbench_data` klasörünü yedekleyip kopyalayabilirsiniz.

GitHub kaynak kodunu ve hazır arayüzü taşır. `.env`, sanal ortamlar, `workbench_data`, `outputs` ve `reports` GitHub'a gönderilmez. Çalışma paketleri ve teşhis dosyaları kaynak belge içeriğini barındırabilir.

Mevcut kurulumun kodunu güncellemek için önce uygulama terminalini Ctrl+C ile kapatın, proje klasöründe çalıştırın:

```powershell
git pull --ff-only
.\.venv-workbench\Scripts\python.exe -m pip install -r requirements-workbench.txt
.\run_app.bat
```

## Geliştirme ve test

Backend testleri:

```powershell
.\.venv-workbench\Scripts\python.exe -m unittest discover -s tests -v
```

Windows'ta `run_tests.bat` da aynı test paketini çalıştırır.

Arayüz kaynaklarını değiştirirken Node.js ve npm gerekir:

```powershell
cd web
npm ci
node --test tests/*.test.js
npm run build
cd ..
```

`run_app.bat` hazır `web/dist` derlemesini sunar. Arayüz kaynakları değiştiğinde `npm run build` çalıştırın ve tarayıcıyı yenileyin. Backend değişikliklerinde uygulamayı yeniden başlatın.

Ek geliştirici araçları, çevrimdışı örnekler, kayıtlı yanıt replay ve model karşılaştırmaları için **[Değerlendirme rehberi](docs/DEGERLENDIRME_REHBERI_TR.md)** bulunur. Çevrimdışı örnek sonuçları canlı model başarısının ölçümü değildir.

## Sınırlar

- Model çıktısı mühendis incelemesi gerektirir; alıntı ve biçim kontrolleri mühendislik doğruluğunu garanti etmez.
- Taranmış/metinsiz PDF için OCR akışı bulunmaz. İlk mimari çıkarımına sığmayan belgeleri anlamlı bölümlere ayırmak gerekir.
- Çok büyük belgenin tamamında çapraz inceleme yapılamazsa bu eksiklik teşhis kaydında belirtilir.
- Model erişimi, kota, yanıt süresi ve token sınırları seçilen sağlayıcıya bağlıdır. Uygulama model profilini otomatik değiştirmez.
- Graphviz tabanlı SVG çıktısı için sistemde `dot` gerekir. Etkileşimli şema Graphviz kurulumu olmadan çalışır; SVG üretilemese de diğer çıktılar korunur.
- Yerel uygulama tek bilgisayarda kullanım içindir; çok kullanıcılı internet yayını veya ekip yetkilendirmesi içermez.

## Kaynak kodunun düzeni

| Konum | İçerik |
| --- | --- |
| `run_app.bat`, `run_workbench.py` | Uygulama başlatıcıları |
| `app/workbench.py` | Yerel API ve analiz işleri |
| `app/review_store.py` | Kalıcı projeler, mühendis değişiklikleri ve geçmiş |
| `app/engineering_workspace.py`, `app/workspace_assistant.py`, `app/tid_export.py` | TİD ve varsayım kayıtları, değişiklik etkileri, proje asistanı ve doküman çıktıları |
| `app/review_runner.py` | Bölümlü ve sürdürülebilir model değerlendirmesi |
| `app/llm_client.py`, `app/llm_worker.py` | Model bağlantısı, işlem yalıtımı ve süre/iptal yönetimi |
| `web/src` | Etkileşimli arayüz kaynakları |
| `web/dist` | Kullanıma hazır arayüz derlemesi |
| `profiles` | Model sağlayıcısı profilleri |
| `tests`, `web/tests` | Backend ve arayüz mantığı testleri |
