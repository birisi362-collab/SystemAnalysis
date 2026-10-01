# VS Code — dosya yoluyla çalıştırma

1. Proje klasörünü VS Code'da aç. `Python: Select Interpreter` ile kullandığın Python ortamını seç.
2. O ortamın terminalinde gerekirse `python -m pip install -r requirements-core.txt` çalıştır.
   Arayüz kullanmayacağın için Streamlit gerekmez. Kurulu bağımlılıkların varsa yeniden kurman gerekmez.
3. `run_from_path.py` dosyasını aç ve üstteki ayarları düzenle:

```python
INPUT_FILE = r"C:\Users\Berkay\Documents\isterler.docx"
OUTPUT_ROOT = r"C:\Users\Berkay\Documents\analizler"
PROFILE_FILE = "profiles/internal_example.json"
BASE_URL = "https://kurum-sunucusu/v1"
MODEL = "kurumdaki-tam-model-kimligi"
```

`BASE_URL` ve `MODEL` örnektir; şirket servisinin gerçek değerlerini kullan.
Bunlar profil JSON'unda zaten doğruysa Python'daki `None` değerlerini koruyabilirsin.
Python dosyasında açıkça yazılan ayarlar profil/.env değerlerinden önceliklidir.
Anahtar gerekiyorsa `.env` dosyasına `INTERNAL_LLM_API_KEY=...` ekle.
Sertifika gerekiyorsa `CA_BUNDLE = r"C:\certs\company-ca-bundle.pem"` olarak belirt.
Tam endpoint adresin varsa `CHAT_COMPLETIONS_URL` alanını kullan; bu alan Base URL/yol birleşiminden önceliklidir.

4. Sağ üstten **Run Python File** ile çalıştır veya terminalde `python run_from_path.py` kullan.
5. Terminalde yazan çıktı klasöründeki `report.html` dosyasını aç.
   JSON, şema ve çalışma kayıtları aynı klasördedir. Her koşu ayrı tarih-saat klasörü açar.

Desteklenen girdiler: TXT (UTF-8), DOCX, metin içeren PDF. Çıktı kökünü boş bırakırsan proje içindeki
`outputs` kullanılır. Göreli yollar VS Code terminalinin bulunduğu klasöre değil proje klasörüne göredir.
Windows yollarında `r"..."` kullan; kapanış tırnağından önce tek ters eğik çizgi bırakma.

Bu giriş dosyası tarayıcıya dosya yüklemez. Canlı analiz sırasında doküman metni seçtiğin LLM endpoint'ine
gönderilir; şirket kullanımı için iç ağ profilini/endpoint'ini seç. Dış servise otomatik geçiş yoktur.
Eski `run_spyder*.py` dosyaları geriye uyumluluk için duruyor; VS Code için `run_from_path.py` kullan.
