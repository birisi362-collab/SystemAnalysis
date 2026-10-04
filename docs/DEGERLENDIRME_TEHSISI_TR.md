# Değerlendirme ve teşhis

Yeni değerlendirme, mühendis tasarımını ve kararlarını değiştirmez. Kullanılabilir bulgular öneri listesine eklenir; şema değişiklikleri ancak mühendis önizleyip uyguladığında gerçekleşir.

## Kullanım

1. **Yeni değerlendirme** ile başlatın. Arayüzde çıktı sınırı başlangıçta 32.768 token; sağlayıcının desteklediği sınır geçerlidir.
2. Sonuç mesajındaki **Değerlendirme ayrıntıları** düğmesini açın. Bölüm durumlarını, bulgu reddetme nedenlerini, her çağrının token kullanımını ve sağlayıcı açıklamasını burada görebilirsiniz.
3. Kısmi sonuçta **Eksik bölümleri yeniden dene** yalnızca tamamlanamayan veya kullanılamayan çıktı üreten bölümleri tekrar işler. Önceki geçerli bulgular korunur. Şema değişmişse bu seçenek eski incelemeyi sürdürmez; **Yeni değerlendirme** gerekir.
4. **Teşhis kaydını indir** ayrıntılı JSON kaydını verir. Eski kayıtların tutulmamış hata mesajları geriye dönük çıkarılamaz.
5. Çalışırken geçen süreyi, tamamlanan bölüm sayısını ve toplam süre sınırını izleyebilirsiniz. **Değerlendirmeyi durdur** devam eden yerel isteği keser; tamamlanan bölüm sonuçlarını ve kalan işleri saklar. Henüz bitmemiş model yanıtı sonuç sayılmaz. Sağlayıcı tarafında üretimin veya ücretlendirmenin durduğu garanti edilmez.
6. Bağlantı kesilirse arayüz bunu açıkça belirtir, ilerleme göstergesini durdurur ve aynı işin durumuna yeniden bağlanmayı dener. Yeni değerlendirmeyi kendiliğinden başlatmaz. `run_app.bat` ile servisi açtıktan sonra yarım kalan değerlendirmeye **Eksik bölümleri yeniden dene** ile devam edebilirsiniz.

## Davranış

- Küçük tasarım tek istekte, büyük belge bölümler halinde incelenir. Bütün mimari her bölümde bağlam olarak bulunur. Bölümler arası çelişki ve arayüz ilişkileri ayrıca incelenir.
- Olağan kaynak kayıtları bölünmez. Çok uzun tek kayıtta 400 karakter örtüşme kullanılır; kaynak kimliği korunur ve alıntı özgün tam metinde kontrol edilir.
- `TRUNCATED` / `length`, çıktı bütçesinde kesilmeyi belirtir. Bölüm en fazla iki düzey küçültülür. Her değerlendirmede en fazla 8 bölüm çağrısı yapılır; kalan işler saklanır. Taşıma katmanındaki sınırlı HTTP yeniden denemeleri de toplam süre sınırına tabidir.
- **Toplam süre sınırı**, bütün model çağrılarını ve yeniden denemeleri birlikte sınırlar. Yeni belge açarken mimari çıkarımı ve ikinci inceleme aynı bütçeyi paylaşır. `TIME_BUDGET` durumunda tamamlanan bulgular korunur. Dosya okuma ve sonuçları diske yazma küçük ek süre oluşturabilir.
- İstek metni gereksiz JSON boşluklarından arındırılır; aynı kaynak alıntısı her şema öğesinde tekrar gönderilmez. Kaynakların tam metni ve öğelerin kaynak kimlikleri korunur. Tek kaynak grubuna sığan uygun boyuttaki tasarım, aynı içerikle iki kez değerlendirilmez.
- Kota, kimlik doğrulama, bağlantı veya zaman aşımı hatalarında diğer çağrılar durdurulur. Zaman aşımında otomatik aynı istek tekrarlanmaz.
- Kaynakta bulunmayan alıntı, bilinmeyen kaynak/öğe kimliği ve biçimi bozuk bulgu diğer geçerli bulguları düşürmez. Sorunlu model çıktısı teşhis bölümünde ayrı tutulur. Bu, mühendisin çözmesi gereken bir kanıtlama görevi değildir.
- Desteklenen bulgunun değişiklik önerisi uygulanamıyorsa bulgu korunur, yürütülebilir öneri kaldırılır ve nedeni gösterilir. Alıntı veya kimlikler tahmin edilerek düzeltilmez.
- Eşdeğer kayıtlar yalnızca açıklama, önem, tür, kaynak/öğe ilişkileri ve önerileri eşleştiğinde birleştirilir. Farklı açıklamalar otomatik olarak aynı mühendislik konusu sayılmaz.
- Model yanıtı, HTTP sonucu, bitiş nedeni, kullanım ve hata konumu saklanır. API anahtarı ve gizli model düşünme metni teşhis kaydına yazılmaz.
- Uygulama kapanırsa o ana kadar tamamlanan bölüm sonuçları saklanır. Yeniden başlatınca kalan işler sürdürülebilir. Sonuç kaydetme sırasında tasarım değişmişse bulgular eski tasarıma otomatik eklenmez.

## Sınırlar

Parçalı inceleme, modelin mühendislik doğruluğunu garanti etmez. Çok büyük belgenin tamamı çapraz inceleme isteğine sığmazsa bağlantılı bileşenlerin kaynakları birlikte incelenir ve bütün belge çapraz incelemesinin eksik olduğu açıkça belirtilir. Küçültülmüş bir bölüm de sürekli kesiliyorsa çıktı bütçesi/düşünme kullanımına veya farklı model profiline bakılmalıdır. İlk mimari çıkarımının girdi ve çıktı sınırları ayrı bir aşamadır.

İlk belge analizinin ikinci aşaması da aynı değerlendirme akışını kullanır. Çıktı klasöründe `review_diagnostics.json`, `run_record.json` ve başlangıç mimarisi korunur.

## Windows bağlantı ortamı ve “Failed to fetch”

4 Ekim 2026'daki olayda servis günlüğünde `OPENSSL_Uplink ... no OPENSSL_Applink` bulundu. Eski `venv` içindeki Python 3.14.3 ortamında sertifika bağlamı oluşturmak aynı yerel çökmeyi üretti. Sunucu kapandığı için tarayıcı `Failed to fetch` gösteriyordu; bu olay token sınırından kaynaklanmıyordu. Bu bulgu burada kullanılan Python dağıtımı/ortamı içindir, bütün Python 3.14 kurulumlarına genellenmez.

Bu bilgisayarda Python 3.12.10 ile `.venv-workbench` kuruldu. Windows sisteminin güvenilir sertifika deposu `truststore` üzerinden kullanılıyor; HTTPS doğrulaması kapatılmıyor. Özel `ca_bundle` tanımlanmışsa o ayar korunuyor. Model bağlantısı ayrı bir alt işlemde çalışıyor; yerel SSL çökmesi artık sunucuyu kapatmak yerine `TLS_RUNTIME` olarak raporlanıyor. Diğer beklenmedik alt işlem kapanmaları `WORKER_EXIT` olur. Başlatıcı sunucuyu açmadan önce ayrı işlemde TLS ortamını denetler.

Başka bilgisayarda Python 3.12 kurduktan sonra proje klasöründe:

```powershell
py -3.12 -m venv .venv-workbench
.\.venv-workbench\Scripts\python.exe -m pip install -r requirements-workbench.txt
.\run_app.bat
```

`py` yoksa kurulu Python 3.12'nin tam yolunu kullanın. `run_app.bat`, `run_workbench.py` ve `run_tests.bat` hazır olduğunda `.venv-workbench` ortamını seçer. Aynı veri klasörüyle uygulama zaten açıksa ikinci sunucu açılmaz; mevcut adres gösterilir. Kod güncellemesinin yüklenmesi için önce açık uygulama terminalini Ctrl+C ile kapatıp tekrar çalıştırın.

`Failed to fetch` tek başına her zaman SSL sorunu anlamına gelmez: servis kapanması, ağ veya tarayıcı bağlantı hatası da üretebilir. Yeni arayüz bu bağlantı hatasını modelin token, kota ve süre hatalarından ayırır.
