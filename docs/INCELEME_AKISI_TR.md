# Mühendis inceleme akışı — sürüm 1.2

`run_app.bat` ile uygulamayı başlatın. Önceki sunucu açıksa Ctrl+C ile kapatıp yeniden
başlatın; tarayıcıyı yenileyin. Adres `http://127.0.0.1:8766`.

## Konuyu anlayın ve müdahale edin

Şema, Kaynaklar, İnceleme, Varsayımlar ve Geçmiş bölümleri korunur.
İnceleme bölümünde artık tek konu listesi vardır. Aynı kaynak eşleştirmesini düzeltmek
gibi aynı işlem altında değerlendirilecek otomatik kayıtlar bir konuda toplanır.
Modelin bulguları değerlendirme soruları olarak sunulur; kesin hata sayılmaz.

Konu listesi kısa bir başlık, bir cümlelik yönlendirme, kaynak etiketi ve durum gösterir.
Üç liste vardır: **Bekleyenler**, **Açıklama bekleyenler**, **Tamamlananlar**.
Bir konu açıldığında üç soruyu izleyin:

1. **Neyi netleştirmeliyim?** Konunun amacı. Modelin uzun açıklaması “Bu konu neden önerildi?” altında açılır; kesin hata hükmü değildir.
2. **Belge ne söylüyor?** Kaynak cümleleri ve ilgili şema parçası. Kaynak ilişkisini veya bağlantıyı doğrudan düzenleyebilirsiniz. Düzenleyiciyi kaydetmek veya kapatmak aynı konuya geri getirir.
3. **Nasıl ilerleyebilirim?** Gerekçeyle kapatma veya eksik bilgiyi belirterek açıklama bekleme. Karar formu yalnız ilgili düğmeye basınca açılır.

Teknik kimlikler yerine okunabilir kaynak ve öğe adları gösterilir. Tam açıklama,
teknik kontroller ve diğer düzenlemeler gerektiğinde açılan ayrıntılardadır.
Küçük şema yalnız kayıtlı ilgili bağlantıları gösterir; önerilen eksik bağlantıyı
varmış gibi çizmez. Kaynak ve bileşen adına tıklayarak ana ekrandaki dayanağını açabilirsiniz.

## Kaynak ilişkileri

| İlişki | Ne demek? |
| --- | --- |
| Doğrudan dayanak | Kaynak cümlesi bu nesneye kanıt olarak bağlanır. Nesnenin kanıt listesinde aynı kaynak bulunmalıdır. |
| Bağlantı üzerinden bağlam | Kaynağı kanıt gösteren bağlantının uç bileşenleri. Bu tek başına bileşenin doğrudan dayanağı değildir. |
| Mühendisin belirttiği bağlam | Kaynakla ilgili, fakat doğrudan kanıt olarak gösterilmeyen öğe. Editörde “Yalnız bağlam” seçilir. |

Eski çıktılarda aynı kaynağı kanıt gösteren bağlantının uçları doğrudan listeye
eklenmişse, uygulama bu uçları bağlam olarak yorumlar. Orijinal JSON değiştirilmez.
İlgisiz nesneler otomatik bağlam sayılmaz; dayanak uyuşmazlığı görünür kalır.
Yalnız bağlam seçerek covered beyanını doğrulamak mümkün değildir.

Ana validatör ve uygulama aynı protokol kurallarını kullanır. Kesin kayıt hataları
(olmayan kimlik, kaynakta olmayan alıntı) ile protokol/kapsama yorumları ayrılır.
Protokol ve doğrudan ilişki uyuşmazlıkları mühendis incelemesi uyarısıdır.
Kapsama durumu hâlâ modelin/mühendisin sınıflandırmasıdır; teknik doğruluk onayı değildir.

## Değişiklikleri izleme

**Geçmiş → Değişiklikleri gör**, ilk model çıktısından bu yana düzenlenen öğeleri
listeler. Bir öğeyi açınca yalnız değişen alanlar **İlk hali / Şimdi** olarak görünür.
İnceleme ekranında “Model / çalışma kopyası” sekmesi yoktur.
Kararlar ve şema yerleşimi ayrıca işlem geçmişinde kayıtlıdır.

## Gerekçeli kapatma ve yeniden inceleme

- **Gerekçeyle kapat:** yaptığınız kontrolü/düzeltmeyi gerekçeyle kaydedin.
- **Bu durumu gerekçeyle kabul et:** bir uyarının neden bu tasarımda kabul edilebilir
  olduğunu açıklayın. Otomatik kontrol ayrıntılı kayıtta görünmeye devam eder.
- **Açıklama bekleniyor:** hangi bilginin eksik olduğunu yazın; konu ayrı bekleme listesinde saklanır.
- **İncelemeye geri al:** önceki kararı gerekçeyle yeniden açın.
- **Başka konuyla birleştir:** benzer model/mühendis konuları tek takip noktası altında
  yönetilebilir. Otomatik kayıt sorunları bulgularla birleştirilerek gizlenemez.

Gerekçe ve mühendis adı zorunludur. Tamamlanan konular **Tamamlananlar** görünümüne
geçer; karar, gerekçe, mühendis ve zaman saklanır. İlgili kaynak eşleştirmesi, nesne,
dayanak veya bulgu değişince **Bekleyenler** listesine “Yeniden inceleme” durumuyla döner. Eski gerekçe silinmez.
Birleştirme hedefinin değiştirilmesi de ilgili kapatma kararını tekrar açar.
İlgisiz bağımsız öğe veya yalnız şema yerleşimi değişikliği konuyu yeniden açmaz.

Bir kontrol düzeltmeyle kaybolduğunda, önceden verilmiş karar tamamlananlarda korunur.
Önceden kapatma kararı yoksa da yapılan düzeltmenin gerekçesi “Kayıt kontrolü
giderildi” olarak tamamlananlara alınır; mühendislik doğruluğu onayı verilmez.
Aynı konu farklı bir dayanakla tekrar oluşursa yeniden inceleme gerekir.
Geri al/yinele kararları ve değişiklikleri birlikte geri getirir. Yeniden açılan
konuda yeniden gerekçe kaydederek incelemeyi tamamlayabilirsiniz.

Eski öğe/bulgu kararları korunur. Yeni konu kararı, birleşik konu listesinde önceliklidir;
eski öğe bazlı onay ile yeni konu kapatma kararı farklı kayıt düzeyleridir.

## Doğrulama ve sınır

İlk Nemotron çıktısının 20 otomatik kaydından 15'i bağlantı uçlarının bağlam olarak
ayrılmasıyla gereksiz doğrudan kanıt hatası olmaktan çıkar. Kalan 4 doğrudan dayanak
uyuşmazlığı bir kaynak konusu altında, 1 nesnesiz eşleştirme ayrı konuda kalır.
Modelin 4 bulgusuyla başlangıçta 6 konu oluşur. Bu, model bulgularının doğru olduğu
veya kaynakların eksiksiz temsil edildiği anlamına gelmez.

Validatör yön anlamını, olumsuz cümleyi, yanlış bağlantı türünü, ilgisiz gerçek
alıntıyı ve mimari gereksinimin yanlış sınıflandırılmasını henüz anlamsal olarak
denetlemez. Bu beş sınır açık test beklentileri olarak tutulur; yeni bir model
çağrısı otomatik çalıştırılmaz. Gerçek dokümanlarla mühendis kullanıcı kabulü gerekir.

Yeni alanlar `contextual_component_ids` ve `contextual_connection_ids` isteğe bağlıdır;
eski çıktılar ve SQLite incelemeleri açılmaya devam eder. Orijinal çıktılar korunur.
ZIP paketinde güncel model, orijinal model ve karar/konu/geçmiş bilgileri bulunur.
GitHub'a gönderim otomatik yapılmaz; güncel sürüm kullanıcı isteğiyle commit edilip paylaşılır.
