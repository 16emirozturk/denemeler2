"""Uygulama genelinde kullanılan sabit listeler (tek kaynak)."""

DURUMLAR = ["İnceleme bekliyor", "İnceleniyor", "Takip gerekiyor", "Sonuçlandırıldı"]

BIRIMLER = ["Henüz atanmadı", "Rehberlik birimi", "Okul yönetimi", "Öğrenci destek ekibi"]

OLAY_TURLERI = [
    "Hakaret veya alay", "Tehdit", "Dışlama", "Dijital zorbalık",
    "Fiziksel zorbalık şüphesi", "Diğer",
]

ORTAMLAR = ["Sınıfta", "Okul bahçesinde", "Koridorda", "Sosyal medyada", "Mesajlaşmada", "Diğer"]
ZAMANLAR = ["Bugün", "Dün", "Bu hafta", "Daha önce", "Emin değilim"]
TEKRARLAR = ["Bir kez", "Birkaç kez", "Birden fazla kez", "Emin değilim"]
SINIFLAR = ["9/A", "9/B", "10/A", "10/B", "11/A", "11/B", "12/A", "12/B"]

# Algılayıcının öncelik sinyali sırası (düşükten yükseğe).
ONCELIKLER = ("Sinyal yok", "Düşük", "Orta", "Yüksek", "Acil")
ONCELIK_SIRASI = {ad: i for i, ad in enumerate(ONCELIKLER)}

# Yayına almadan önce resmi kaynaklardan yeniden doğrulayın.
ACIL_HATLAR = (
    ("112", "Acil çağrı merkezi"),
)
