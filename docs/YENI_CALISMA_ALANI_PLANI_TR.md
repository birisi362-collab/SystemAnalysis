# Tek ekranda mimari düzenleme — geliştirme planı

Plan tarihi: 3 Ekim 2026. Durum: planlandı; bu belge yeni uygulamanın tamamlandığı anlamına gelmez.

## Amaç

Mühendis belgeyi yükler, yapay zekânın oluşturduğu mimariyi kaynaklarıyla birlikte görür,
aynı çalışma alanında bileşen ve bağlantıları ekler, değiştirir veya kaldırır.
Yapay zekâ bulguları ilgili öğeler üzerinde açıklama olarak görünür. Uygulanabilir öneriler
önizlenir, mühendis tarafından düzenlenir ve istenirse gerçek mimariye uygulanır.

Başarı ölçütü: bir kaynak cümlesini okumak, ilgili bağlantıyı düzenlemek ve bir yapay zekâ
önerisini değerlendirmek için çalışma ekranından ayrılmak gerekmez.

## Kesinleşen ürün kararları

- Otomatik kontrol listeleri, hata rozetleri ve validatörden oluşturulan inceleme konuları kaldırılacak.
- `covered`, `partially_covered`, `unmapped` gibi kapsama durumları yeni çalışma akışından çıkarılacak.
- “Kaynak ilişkisini düzenle” ve doğrudan/bağlam eşleştirme formları kaldırılacak.
- Her belge cümlesinin bir şema öğesine bağlanması beklenmeyecek. Bağlantısı olmayan metin otomatik görev veya hata üretmeyecek.
- Belge ve dayanaklar erişilebilir kalacak. Bir kaynağın bağlı olması mühendislik doğruluğu onayı sayılmayacak.
- Ana şema ile inceleme şeması birleştirilecek. Ayrı küçük şema kaldırılacak.
- Günlük işlerde sayfa geçişleri ve üst üste düzenleme pencereleri kaldırılacak.
- Mühendis kaynak göstermeden kendi tasarım öğesini ekleyebilecek. Eklemeye belge dayanağı uydurulmayacak.
- Yapay zekâ mühendis düzenlemelerini doğrudan değiştirmeyecek; yeni değerlendirme sonucu öneriler sunacak.

## 1. Aşama — Zorunlu eşleştirme ve kontrol mantığını kaldırma

### Yapılacaklar

1. Kaynak ilişkisinin tek kaydı, öğeye bağlı kaynak ve alıntı olacak. Kaynak → öğe görünümü bu kayıttan türetilecek; ikinci bir kapsama kaydı düzenlenmeyecek.
2. Yeni model çıkarımında her kaynak için kapsama sınıflandırması istenmeyecek. Başlıklar, genel açıklamalar ve tek bir blokla temsil edilemeyen gereksinimler yalnız belgede bulunabilecek.
3. İnceleme konuları yalnız model bulgularından ve mühendisin eklediği notlardan oluşacak. Belgenin şemaya bağlanmamış satırlarından konu üretilmeyecek.
4. Protokol/kapsama yorumlarını otomatik hata listesine dönüştüren kurallar yeni akıştan çıkarılacak. Bu konularda anlamlı bir mühendislik gözlemi varsa yapay zekâ bulgusu olarak açıklanabilecek.
5. Kaydetmede yalnız biçim ve veri bütünlüğü koşulları kalacak: mevcut bağlantı uçları, benzersiz kimlikler, zorunlu alanlar ve seçilen belge alıntısının gerçek metinde bulunması. Sorun ilgili işlem alanında anlaşılır biçimde gösterilecek.
6. Kaynak alıntısı belge içinden seçilecek. “Kaynağı değiştir” ve “Bu kaynak ilgili değil” işlemleri yalnız seçili öğenin dayanağını düzenleyecek.
7. Başlık ve komşu metin kaynak cümlesinin yanında gösterilecek. Parçanın tek başına yanıltıcı olduğu durumlarda belge bağlamı açılabilecek. Kaynakla ilişkili olma kararı sırf alıntı metinde bulunduğu için otomatik verilmeyecek.

### Eski kayıtların korunması

İlk model çıktısı, geçmiş ve mevcut mühendis kararları korunacak. Eski kapsama/validasyon
alanları eski dosyaları okumak için uyumluluk katmanında desteklenecek; yeni kullanıcı
iş listesine dönüşmeyecek. Eski otomatik kontrol kararları tarihsel kayıtta kalacak.
Eski bulgu kararları ilgili bulgulara bağlanmaya devam edecek. Göçten önce veri tabanı yedeği alınacak;
göç tekrar çalıştırıldığında mevcut düzenlemeleri çoğaltmayacak veya sıfırlamayacak.

### Tamamlanma ölçütü

“Sistemin blok mimarisi aşağıdaki bağlantıları sağlamalıdır” gibi genel bir cümle
şemaya bağlanmadığında uygulama görev üretmez. Kaynaksız bir mühendis eklemesi kaydedilebilir.
Eski Nemotron çıktısı ve mevcut SQLite projesi kararlarını kaybetmeden açılır.

## 2. Aşama — Belge, gerçek şema ve düzenlemeyi birleştirme

### Ekran düzeni

| Alan | İçerik ve etkileşim |
| --- | --- |
| Üst çubuk | Belge yükle / çalışma aç, geri al-yinele, kaydetme durumu, dışa aktar, geçmiş |
| Sol panel | Belge metni, başlık/satır/sayfa bilgisi, arama, seçilen kaynak ve komşu metin |
| Orta alan | Tek gerçek mimari şeması; blok ve bağlantı düzenleme, ekleme ve kaldırma |
| Sağ panel | Öneri listesi ve seçilen öğe/önerinin ayrıntısı; yerinde düzenleme alanları ve işlemler |

Öneri listesi sağ panelin içinde daraltılabilir. Seçilen önerinin açıklaması ve öğe
düzenlemesi aynı panelde erişilir; belge ve şema yerinde kalır. Geçmiş yan çekmecede,
varsayımlar ilgili öğe veya konu içinde açılır. Paneller yeniden boyutlandırılabilir
ve daraltılabilir. Dar ekranda açılan panel kapatıldığında aynı seçim ve konum korunur.

### Şema ve kaynak etkileşimi

- Kaynak seçilince dayanak gösteren öğeler vurgulanır. İlgili bağlantının uçları görünür tutulur; aynı kaynağı doğrudan kanıt gösteriyormuş gibi etiketlenmez.
- Blok veya ok seçilince sağdaki düzenleme alanları ve soldaki kaynak gösterilir. Birden fazla dayanak varsa kaynaklar arasında aynı panelde gezilebilir.
- Öneri seçilince ilgili bölgeye yaklaşılır. Diğer öğeler hafifçe soluklaşır; yerleşim yeniden kurulmaz.
- Düzenlenen ad, yön ve arayüz şemada taslak olarak önizlenir. “Uygula” gerçek kaydı değiştirir; “Vazgeç” taslağı kaldırır.
- Bloktan bağlantı başlatılır; uçlar otomatik doldurulur. Ekleme ve kaldırma sağ panelde tamamlanır.
- Bileşen kaldırılırken etkilenecek bağlantılar gösterilir. İşlem tek geçmiş kaydı olarak geri alınabilir.
- Kayıt sonrasında yakınlaştırma, şema konumu, belge kaydırması ve seçili konu korunur.
- Basit ad/yerleşim düzenlemelerinde yazılı gerekçe zorunlu tutulmaz; işlem geçmişi otomatik açıklama üretir. Mühendislik kararları için kısa not istenir.

### Tamamlanma ölçütü

Bir kaynak cümlesini seçmek, bağlı bağlantının yönünü değiştirmek, sonucunu önizlemek,
kaydetmek ve geri almak başka bir sayfa veya düzenleme penceresi gerektirmez.
Düzenlemenin ardından aktif öneri ve belge konumu korunur.

## 3. Aşama — Bulguları ve uygulanabilir önerileri ayırma

### Bulgu / inceleme notu

Belirsizlik, çelişki veya değerlendirme sorusu ilgili şema öğelerinde küçük bir işaret
olarak gösterilir. Açıklama ve kaynak sağ/sol panellerde birlikte okunur. İşaretin görünürlüğü
değiştirilebilir; not gizlemek mimari öğeyi kaldırmaz. Mühendis şemadan kendi inceleme notunu da ekleyebilir.
Henüz belirli bir öğeye bağlanamayan belge bulgusu öneri listesinde bulunur; sahte blok oluşturulmaz.

### Uygulanabilir değişiklik

Yeni model yanıtına isteğe bağlı yapılandırılmış değişiklik önerileri eklenecek:

| Alan | Amaç |
| --- | --- |
| Bulgu/öneri kimliği ve açıklama | Önerinin hangi konuya ait olduğu ve neden sunulduğu |
| İşlem | Bileşen/bağlantı ekle, değiştir veya kaldır |
| Hedef öğeler ve alan değerleri | Tam olarak hangi mimari verinin değişeceği |
| Kaynaklar ve alıntılar | Önerinin dayandığı belge ifadeleri |
| Açık kalan bilgiler | Uygulamadan önce mühendisin tamamlaması gereken alanlar |
| İncelenen çalışma sürümü | Önerinin hangi mevcut tasarıma göre üretildiği |

Belirsiz bir bulguya zorla değişiklik eklenmeyecek. Eski, yalnız metinsel `recommended_action`
alanından işlem/yön/protokol tahmin edilerek otomatik uygulama yapılmayacak. Bu bulgular
mevcut öğe düzenleyicisiyle elle değerlendirilebilecek.

“Önizle”, “Düzenleyerek uygula” ve “Reddet” işlemleri sağ panelde sunulacak. Öneri önizlemesi
belirgin etiket ve çizimle gerçek şemadan ayrılacak; yalnız renge dayanmayacak. Uygulanınca
gerçek mimari değişecek ve önerinin durumu güncellenecek. Bir önerinin birden fazla değişikliği
tek işlem olarak kaydedilip geri alınacak; kısmi veya iki kez uygulama engellenecek.

Önerinin dayandığı öğe değişmiş veya kaldırılmışsa eski öneri sessizce uygulanmayacak.
İlgili farklılık gösterilecek ve öneriyi güncelleme/elle düzenleme yolu sunulacak.

### Tamamlanma ölçütü

ADC/LVDS belirsizliği kaynaklarıyla incelenebilir; uygulama kendi başına ADC'nin yerini
değiştirmez. Yeterince belirli bir bağlantı önerisi gerçek şemada önizlenir, düzenlenip
uygulanır ve tek geri alma işlemiyle kaldırılır. Öneriyi reddetmek mimariyi değiştirmez.

## 4. Aşama — Belge yükleme ve karar akışını tamamlama

1. Dosya yolu yazma zorunluluğu yerine TXT/DOCX/PDF dosya seçme ve sürükleyip bırakma eklenecek. Mevcut yerel dosya yolu gelişmiş seçenek olarak kalabilecek.
2. Dosya seçme, analiz başlatma, ilerleme ve hata/yeniden deneme tek açılış akışında gösterilecek. Okunamayan veya metinsiz belge anlaşılır mesajla bildirilecek.
3. Şema oluşunca üç panelli çalışma alanı açılacak. Yapay zekâ değerlendirmesi tamamlanmazsa mevcut şema kullanılabilir kalacak; öneriler için tekrar deneme sunulacak.
4. Öneriler “Bekleyen”, “Bilgi bekleyen” ve “Tamamlanan” olarak izlenecek. Tamamlananlarda uygulanan/reddedilen/incelenen sonuç ayrıntıda gösterilecek.
5. Önceki/sonraki öneriye çalışma alanından ayrılmadan geçilecek. İşaretlerin görünürlüğü inceleme durumundan bağımsız olacak.
6. “Yeni değerlendirme iste” yalnız mühendis tarafından başlatılacak; güncel çalışma kopyası değerlendirilecek. Eski öneriler/kararlar korunacak; yeni sonuçlar mevcut düzenlemelerin üzerine doğrudan yazılmayacak.
7. Yalnız anlamlı değişiklikler ilgili karar için yeniden inceleme gerektirecek. Yerleşim değişikliği veya bağımsız öğe düzenlemesi tamamlanan konuları topluca geri açmayacak.
8. Dışa aktarma güncel şemayı, kaynakları, mühendis eklemelerini, öneri/karar durumlarını ve geçmişi taşıyacak. Eski çıktı uyumluluğu için alanlar saklansa bile boş validasyon listesi otomatik doğruluk onayı olarak raporlanmayacak.

### Tamamlanma ölçütü

Mühendis dosya seçerek analiz başlatır, sonucu düzenler, kendi öğesini ekler,
öneriyi uygular veya reddeder ve çalışmayı yeniden açtığında bunları korunmuş görür.
Yeni değerlendirme mevcut düzenlemeleri silmez. Dışa aktarılan çalışma tekrar açılabilir.

## Kod üzerindeki çalışma sınırları

| Mevcut alan | Planlanan sorumluluk |
| --- | --- |
| `app/models.py`, `app/prompts.py`, `app/pipeline.py` | Yeni çıktı sürümü; zorunlu kapsama beyanından çıkış; isteğe bağlı yapılandırılmış öneriler |
| `app/review_store.py`, `app/review_topics.py` | Otomatik konu üretimini kaldırma; karar göçü; atomik öneri uygulama/geri alma |
| `app/source_relations.py` | Yeni akışta öğe dayanaklarından türetilen tek kaynak görünümü; eski kayıtlar için uyumluluk |
| `app/validator.py` | Kapsama/protokol yorumlarından üretilen iş listesini kaldırma; gerekli veri bütünlüğü kontrollerini işlem seviyesine ayırma |
| `app/workbench.py` | Belge yükleme, güncel tasarımı yeniden değerlendirme ve dışa aktarma |
| `web/src/main.jsx` | Tek çalışma alanının birleştirilmesi; mevcut şema ve editörlerin ayrı bileşenlere çıkarılması |
| `web/src/review-ui.jsx`, `web/src/topic-dialog.jsx` | Ayrı inceleme sayfası ve küçük şema yerine çalışma alanındaki öneri/ayrıntı panelleri |
| `web/src/history-changes.jsx` | Geçmiş çekmecesinde değişen alanları gösterme |

React ve mevcut React Flow altyapısı kullanılacak. Bu ürün değişikliği için yeni bir
arayüz çatısına veya ikinci bir şema altyapısına geçmek gerekmiyor.

## Teslim ve doğrulama

Her aşama çalışan uygulama üzerinde tamamlanacak; yalnız statik tasarım teslim edilmeyecek.
Öncelik ilk iki aşama: zorunlu eşleştirmeyi kaldırmak ve günlük işi tek şemada birleştirmek.
Üçüncü aşama önerileri uygulanabilir hâle getirir; dördüncü aşama uçtan uca akışı tamamlar.

- Eski çıktılar ve mevcut kararlar için göç/geri açma kontrolleri.
- Kaynaksız mühendis eklemesi, kaynak değiştirme/kaldırma ve genel cümlelerin görev üretmemesi.
- Belge/şema arasında iki yönlü seçim ve çalışma bağlamının korunması için tarayıcı kontrolleri.
- Öneri önizlemesinin gerçek kaydı değiştirmemesi; uygulama, reddetme, tekrar uygulama ve geri alma kontrolleri.
- İlgili veri değişmişken eski önerinin uygulanmaması; ilgisiz değişikliklerin kararları geri açmaması.
- Dosya yükleme, yeniden açma, yeniden değerlendirme ve dışa aktarma senaryoları.
- Yeni davranışa göre eski validatör testleri yeniden kapsamlandırılacak. Kaldırılmış ürün davranışı sırf eski test onu bekliyor diye korunmayacak.
- Frontend üretim derlemesi ve kullanım belgeleri güncellenecek. Son kabul Nemotron örneği ve farklı bir belgeyle yapılacak.

Başka bir altyapıya geçiş, OCR geliştirmesi, çok kullanıcılı çalışma ve yeni hosting kurulumu
bu değişikliğin ilk kapsamına eklenmeyecek. Metin okunamayan belgede okunabilir dosya gerektiği
belirtilecek. Çalışmanın odağı kaynakları anlaşılır biçimde gösteren, kolay düzenlenen tek ekran olacak.
