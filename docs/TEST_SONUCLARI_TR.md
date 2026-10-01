# Teslim öncesi doğrulama — V6

Tarih: 30 Eylül 2026.

## Çalıştırılan kontroller

- 42 otomatik test: kaynak ayırma, DOCX sırası, boş PDF sayfası, kanıt/protokol/kapsama/bulgu
  doğrulaması, API hata davranışı, token kesilmesi, replay, skor hesapları ve UI oturum durumu.
- 20/20 sentetik senaryo çevrimdışı fixture modunda tamamlandı.
- Komut satırından kayıtlı yanıt replay ve iki raporu karşılaştırma akışı çalıştırıldı.
- Streamlit AppTest ile örnek çalıştırma ve profil değişimi sonrasında sonuçların korunması kontrol edildi.
- Çevrimdışı 20 senaryoda doğrulama seviyesinde error kaydı yok; belirsiz/bağlantısız örneklerde
  inceleme uyarıları bulunabilir.

Fixture girdileri beklenen mimariye göre hazırlanmıştır. Bu sonuçlar bir modelin %100 doğru
olduğunu göstermez; uygulamanın test verisini işlemesi ve raporlaması sınanmıştır.

## Ortam ve sınırlar

Python 3.12 / Linux üzerinde test edildi. Windows/Anaconda için .bat girişleri ve Python 3.10+
uyumlu sözdizimi hazırlandı; Windows üzerinde bu teslim sırasında çalıştırılmadı.
Bağımlılık sürümleri `requirements-tested.txt` içindedir. Normal kurulum `requirements.txt` ile yapılır.
Sistem Graphviz `dot` bulunmadığından SVG dışa aktarımının başarılı yolu çalıştırılmadı;
DOT/Mermaid üretimi, arayüz şeması için veri üretimi ve SVG yokken diğer çıktıların korunması sınandı.
Tarayıcıda piksel düzeyinde görsel inceleme yapılmadı; Streamlit davranışı test aracıyla doğrulandı.

Canlı NVIDIA/DeepSeek veya OpenRouter/Nemotron çağrısı yapılmadı; kullanıcı API anahtarı gerekli.
Bu nedenle gerçek model kalitesi, sağlayıcı uyumluluğu ve hesaba özel ücretsiz erişim henüz ölçülmedi.
İlk canlı adım: API rehberindeki bağlantı testi ve iki örneklik karşılaştırma.

## VS Code dosya-yolu güncellemesi

Ek iki test geçti: farklı terminal klasöründen göreli girdi yolu ve ayrı çıktı klasörleri;
geçersiz/boş girdi yolunda LLM istemcisi oluşturulmadan durma. Yeni giriş sözdizimi derlendi.
Bu ek doğrulama çevrimdışı Linux ortamında yapıldı; şirket endpoint'ine bağlanılmadı.
