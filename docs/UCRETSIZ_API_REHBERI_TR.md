# Ücretsiz geliştirici API’si: adım adım kurulum

System Architecture Analyzer V6 • Kontrol tarihi: 30 Eylül 2026

## Hangi seçeneği kullanacağız?

Başlangıç: **NVIDIA Build üzerinden DeepSeek V4.1 Flash**.
Karşılaştırma: **OpenRouter üzerinden Nemotron 3 Ultra (free)**.

Önemli ayrım: NVIDIA’nın eski `deepseek-v4-flash` sayfasında ücretsiz endpoint
“Deprecated” olarak gösteriliyor. Bu nedenle paketteki hazır profil V4.1 Flash içindir.
Bu iki sürüm aynı değildir. İç ağdaki V4 Flash başarısı ayrıca ölçülmelidir.

Ücretsiz olan, sağlayıcının sunucusundaki modele geliştirme amacıyla API isteği göndermektir.
Bilgisayarına modeli indirmen, GPU satın alman veya Docker kurman gerekmez.
Tarayıcıda ücretsiz sohbet etmek ile Python’dan API kullanmak ayrı erişim yollarıdır.
Burada API anahtarı oluşturup Python uygulamasına tanıtacağız.

Ücretsiz erişim sınırsız kullanım veya kesintisiz hizmet garantisi değildir. Kota, hesap erişimi
ve modelin ücretsiz sunulma durumu değişebilir. Bu rehberde sabit günlük kota sözü verilmez.

## 1. NVIDIA hesabını ve anahtarını oluştur

1. [DeepSeek V4.1 Flash model sayfasını aç](https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash).
2. **Login / Sign in** ile NVIDIA hesabına giriş yap; hesabın yoksa e-posta ile oluştur.
3. İstenirse geliştirici programı üyeliğini, e-posta/hesap doğrulamasını tamamla.
4. Model sayfasındaki **Get API Key / Generate API Key** düğmesini kullan. Arayüzdeki isim değişebilir.
5. Hesap kurulumu tamamlandığında oluşturulan anahtarı kopyala. Anahtarı bana göndermene gerek yok.
6. Sayfada ücretsiz API yerine yalnızca partner veya kendi sunucuna kurulum seçenekleri varsa
   bu modelin ücretsiz erişimi değişmiş olabilir. Ücretli dağıtım açmadan aşağıdaki OpenRouter yolunu kullan.

Bu akış NVIDIA’nın resmî [API Catalog Quickstart](https://docs.api.nvidia.com/nim/re/docs/api-quickstart)
yönergesine dayanır. Ücretsiz geliştirici erişiminin kapsamı için
[resmî FAQ](https://docs.api.nvidia.com/nim/docs/product) sayfasını kontrol et.
Bu rehber prototip/test API’si içindir; iç ağ üretim dağıtımının lisans ve altyapı seçimi ayrıdır.

## 2. Uygulamayı hazırla — Windows / Anaconda

ZIP’i çıkar. `README.md`, `ui_app.py` ve `requirements.txt` dosyalarının bulunduğu klasörü aç.
Anaconda Prompt içinde bu klasöre geç; örnek yolunu kendi klasörünle değiştir:

```bat
cd /d C:\Projects\system_architecture_analyzer_v6
python --version
python -m pip install -r requirements.txt
```

Python 3.10 veya üzeri kullan. Spyder farklı bir Python ortamını kullanıyorsa paketleri
Spyder’ın kullandığı ortama kurmalısın. Kurulum internet gerektirir; çevrimdışı testler
bağımlılıklar kurulduktan sonra API’ye bağlanmaz.

## 3. Anahtarı uygulamaya tanıt — en kolay yol

```bat
python -m streamlit run ui_app.py
```

Açılan ekranda:

| Alan | Değer |
|---|---|
| Bağlantı profili | `nvidia_deepseek` |
| Base URL | `https://integrate.api.nvidia.com/v1` |
| Model ID | `deepseek-ai/deepseek-v4.1-flash` |
| API anahtarı | Kendi NVIDIA anahtarın |
| Endpoint yolu | `/chat/completions` |
| Tam endpoint | Boş bırak |
| Sağlayıcının JSON modu | Başlangıçta kapalı |
| Çıktı token sınırı | Başlangıçta 8192 |
| Zaman aşımı | Başlangıçta 180 saniye |

**Bağlantıyı test et** düğmesine bas. Bu, modele küçük bir JSON isteği gönderir ve kota kullanır.
Başarı mesajını gördükten sonra `examples/sample_requirements.txt` dosyasını yükleyip
**Canlı analizi başlat** düğmesini kullan. Sonucu çalışma ZIP’i olarak indirebilirsin.

Bu oturumda anahtarı ekrana yazman yeterlidir. Sonraki açılışlarda ve komut satırındaki
karşılaştırmalarda tekrar girmemek için bir sonraki adımı uygula.

## 4. Anahtarı .env dosyasında tut — CLI ve Spyder için

Ana klasörde `.env.example` dosyasının bir kopyasını oluştur ve adını `.env` yap:

```bat
copy .env.example .env
```

`.env` dosyasını metin düzenleyicide aç ve ilgili satırı doldur:

```dotenv
NVIDIA_API_KEY=BURAYA_KENDI_ANAHTARIN
```

`BURAYA_KENDI_ANAHTARIN` metni gerçek anahtar değildir; tamamını kendi anahtarınla değiştir.
Dosyanın adının yanlışlıkla `.env.txt` olmamasına dikkat et.
API anahtarını Python dosyasına veya profil JSON’una yazmana gerek yok.

Ardından:

```bat
python -m app.main --profile profiles/nvidia_deepseek.json --probe
```

Bağlantı çalıştıysa:

```bat
python -m app.main examples/sample_requirements.txt --profile profiles/nvidia_deepseek.json
```

Spyder için `run_spyder.py` dosyasını açıp F5 kullanabilirsin.

## 5. İlk ücretsiz model değerlendirmesi

Önce yalnızca iki küçük örnekle başla:

```bat
python -m app.evaluation --mode live --profile profiles/nvidia_deepseek.json --split dev --limit 2 --output reports/deepseek_smoke
```

Bu komut normal durumda 4 LLM isteği yapar: her örnek için çıkarım + inceleme.
Varsayılan sınırlı tekrar denemeleriyle üst sınır 8 HTTP isteğidir. Öncesindeki bağlantı testi ayrıdır.
Çıktı klasörü yeni/boş olmalıdır; yeniden denemede farklı bir klasör adı kullan.

`reports/deepseek_smoke/evaluation.html` dosyasını tarayıcıda aç.
`status=failed` ise önce hata koduna bak; bu durum otomatik olarak kötü model puanı demek değildir.

## 6. İkinci model: OpenRouter Nemotron

1. [OpenRouter](https://openrouter.ai/) hesabına giriş yap.
2. [API Keys](https://openrouter.ai/settings/keys) sayfasında bir anahtar oluştur.
3. [Nemotron 3 Ultra free sayfasında](https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b:free)
   modelin ücretsiz sunulduğunu kontrol et. Ücretli varyanta otomatik geçiş uygulamada yoktur.
4. `.env` içine ekle:

```dotenv
OPENROUTER_API_KEY=BURAYA_KENDI_OPENROUTER_ANAHTARIN
```

Arayüzde `openrouter_nemotron` profilini seçebilir veya şu komutu kullanabilirsin:

```bat
python -m app.evaluation --mode live --profile profiles/openrouter_nemotron.json --split dev --limit 2 --output reports/nemotron_smoke
```

İki koşuyu karşılaştır:

```bat
python -m app.evaluation --compare reports/deepseek_smoke/evaluation.json reports/nemotron_smoke/evaluation.json --output reports/comparison_smoke
```

`comparison.json` içindeki `comparable_inputs` değeri aynı örneklerin ve prompt sürümünün
kullanılıp kullanılmadığını gösterir. Aynı koşullarda bile küçük örnek sayısı kesin model sıralaması vermez.

OpenRouter’da kota bilgisi hesabına bağlıdır; [resmî limitler](https://openrouter.ai/docs/api/reference/limits)
sayfasını esas al. Kota dolduğunda yeni hesap/anahtarla sınırı aşmaya çalışmak yerine bekle.

## Hata aldığında

| Hata | Anlamı / yapılacak işlem |
|---|---|
| `AUTHENTICATION` / 401 | Anahtarı, sağlayıcı profilini ve kopyalama hatalarını kontrol et. |
| `ACCESS_DENIED` / 403 | Hesabın endpoint erişimini ve istenen doğrulamaları kontrol et; sağlayıcı desteği gerekebilir. |
| `ENDPOINT_OR_MODEL` / 404 | Base URL, endpoint yolu ve model ID’sini resmî model sayfasıyla karşılaştır. |
| `RATE_LIMIT` / 429 | Kota/yoğunluk sorunu; sonra tekrar dene. |
| `SERVICE_UNAVAILABLE` | Sağlayıcı hizmet/kapasite sorunu. |
| `TIMEOUT` | İstek zamanında bitmedi; daha küçük dokümanla dene veya süreyi artır. |
| `TRUNCATED` | Çıktı token sınırına ulaşıldı; 16384 gibi daha yüksek sınırı sağlayıcı destekliyorsa dene. |
| `EMPTY_CONTENT` | Son cevap gelmedi; reasoning-only yanıt, token bütçesi veya model ayarlarını incele. |
| `INVALID_JSON` | Son yanıt JSON değil; çalışma kaydındaki final yanıtı incele. |
| `ValidationError` / `SCHEMA` | JSON var ama uygulamanın alanlarına uymuyor; kayıtlı yanıtla teşhis et. |
| `TLS` | Kurumsal CA sertifikasını tanıt; bu problemi model başarısıyla karıştırma. |

`.env` içindeki `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY` gibi genel ayarlar bütün profilleri
geçersiz kılabilir. İki sağlayıcıyı karşılaştırırken bunları boş bırak; sağlayıcıya özel anahtarları kullan.
Uygulama hata alınca başka modele otomatik geçmez; model karşılaştırması tutarlı kalır.

İnternet testlerinde paketteki sentetik belgeleri kullan. Kaydedilen çalışma dosyaları kaynak metni
ve modelin son yanıtlarını içerir; bunları paylaşmadan önce içeriklerini kontrol et.

## Doğrulanan resmî kaynaklar

- [V4 Flash: eski ücretsiz endpoint durumu](https://build.nvidia.com/deepseek-ai/deepseek-v4-flash)
- [V4.1 Flash: model ID, base URL ve ücretsiz API](https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash)
- [NVIDIA hesap / API anahtarı adımları](https://docs.api.nvidia.com/nim/re/docs/api-quickstart)
- [NVIDIA geliştirici erişimi](https://docs.api.nvidia.com/nim/docs/product)
- [Nemotron 3 Ultra ücretsiz model sayfası](https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b:free)
- [OpenRouter limitleri](https://openrouter.ai/docs/api/reference/limits)

Bu paket hazırlanırken kişisel API anahtarıyla canlı istek yapılmadı. Ücretsiz katalog durumu
resmî sayfalardan kontrol edildi; hesabına özel erişim ilk bağlantı testinde doğrulanacak.
