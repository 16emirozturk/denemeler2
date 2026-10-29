# Güvenli Okul

Bozüyük Fen Lisesi okul logosunu kullanan, Streamlit ile hazırlanmış bağımsız bildirim ve takip prototipi. **Gerçek okul sistemine bağlı değildir ve gerçek öğrenci verileriyle kullanılmamalıdır.** Otomatik ifade eşleştirmesi bir karar, kanıt veya profesyonel değerlendirme değildir.

## Kurulum

Python 3.10 veya üstü önerilir.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python tools/parola_hash.py
```

`.streamlit/secrets.toml.example` dosyasını `.streamlit/secrets.toml` olarak kopyalayın; kullanıcı adını ve `tools/parola_hash.py` tarafından üretilen parola özetini ekleyin. `secrets.toml` dosyasını GitHub'a yüklemeyin.

```bash
streamlit run app.py
```

## Dosya yapısı

- `app.py`: sayfalar ve kullanıcı akışı
- `stil.py`: tema ve arayüz stilleri
- `db.py`: SQLite veri katmanı, kayıtlar, denetim ve CSV
- `guvenlik.py`: parola özeti, maskeleme ve CSV hücre temizliği
- `hakaret_tespiti.py`: kural tabanlı ifade sinyalleri
- `degerlendirme.py`: sentetik test örnekleri ve metrikler
- `sabitler.py`: durumlar, sınıflar, olay türleri ve seçenekler
- `bozuyuk_fen_lisesi_logo.png`: okul logosu
- `testler/test_core.py`: temel otomatik testler

## Test

```bash
python -m unittest discover -s testler -v
```

## Tasarım kararları

- Üst gezinme alanı, okul logosu, sade lacivert/mavi palet, açık zemin ve daha tutarlı boşluklar.
- Anonim kayıtta ad/soyad/sınıf veritabanına yazılmaz; açıklamadaki belirli e-posta, telefon, IBAN ve geçerli T.C. kimlik numarası biçimleri maskelenmeye çalışılır.
- Takip koduyla sorgu yalnızca durum ve zaman alanlarını döndürür.
- Yönetici işlemleri denetim kaydına eklenir; CSV dışa aktarımı kimlik alanlarını varsayılan olarak içermez ve formül enjeksiyonu için hücreleri temizler.
- Yeni veritabanı örnek kayıtlarla doldurulmaz; mevcut kayıtlar uygulama yeniden başlatıldığında otomatik silinmez.

## Sınırlılıklar ve güvenli kullanım

- Maskeleme tüm kişisel bilgileri yakalayamaz; isim, adres, okul numarası ve bağlamsal tanımlayıcılar kaçabilir.
- Oturum içi hız sınırı dağıtık veya çoklu oturum saldırılarına karşı yeterli değildir. Tek yönetici hesabı, rol yönetimi ve bu prototipin güvenlik önlemleri kurumsal kimlik doğrulama yerine geçmez.
- SQLite dosyasının bulut barındırmada kalıcı olacağı garanti edilmez. Yedekleme/geri yükleme ayrıca tasarlanmalıdır.
- Uygulama bildirimleri bir okula veya yetkili ekibe otomatik iletmez. Kullanıcıya inceleme garantisi vermez.
- Gerçek kullanım öncesinde okulun yetkili birimleri, veri koruma/hukuk uzmanı ve güvenlik uzmanlarıyla süreç, izin, erişim, saklama-imha, yedekleme ve acil durum planı doğrulanmalıdır.
- Acil tehlikede uygulamayı beklemek yerine 112 veya güvenilir bir yetişkine başvurulmalıdır.

## Bilimsel değerlendirme

`degerlendirme.py` yalnızca elle hazırlanmış sentetik kümede temel metrikleri verir. Küme küçük olduğu ve aynı geliştirme sürecinde oluşturulduğu için sonuçlar gerçek ortama genellenemez. Araştırma iddiası için bağımsız veri, uzman etiketlemesi, etik izin ve sınırlılık raporu gerekir.
