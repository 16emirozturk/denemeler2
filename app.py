"""Güvenli Okul — bildirim ve takip platformu (Streamlit, sürüm 2).

Mimari: app.py (arayüz) · db.py (veri) · guvenlik.py (kimlik/maskeleme) ·
hakaret_tespiti.py (kural tabanlı sinyal) · degerlendirme.py (ölçüm) · stil.py (CSS).
"""
from __future__ import annotations

import html
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

import db
import degerlendirme
import guvenlik
import hakaret_tespiti as ht
import stil
from sabitler import (ACIL_HATLAR, BIRIMLER, DURUMLAR, ONCELIK_SIRASI, ONCELIKLER, OLAY_TURLERI,
                      ORTAMLAR, SINIFLAR, TEKRARLAR, ZAMANLAR)

st.set_page_config(page_title="Güvenli Okul", page_icon="bozuyuk_fen_lisesi_logo.png", layout="wide", initial_sidebar_state="collapsed")
stil.uygula()

# ------------------------------------------------------------------ ayarlar
OTURUM_ZAMAN_ASIMI_SN = 30 * 60      # hareketsizlikte yönetici oturumu kapanır
OTURUM_HATALI_ESIK = 5               # bir tarayıcı oturumunda ardışık hatalı giriş sınırı
OTURUM_KILIT_SN = 5 * 60
GLOBAL_HATALI_ESIK = 20              # tüm oturumlarda 15 dakikadaki hatalı giriş sınırı
FORM_PENCERE_SN, FORM_PENCERE_MAKS = 600, 5   # bildirim spamına karşı oturum başına sınır
SORGU_PENCERE_SN, SORGU_MAKS = 300, 10        # takip kodu tahminine karşı sınır
ISTATISTIKLER_HERKESE_ACIK = False
SLA_SAAT = 24                        # ilk incelemeye alınmayan kayıt bu süreden sonra "gecikmiş" sayılır

ss = st.session_state


def _secret(bolum: str, anahtar: str, varsayilan: str = "") -> str:
    try:
        return str(st.secrets[bolum][anahtar])
    except Exception:  # secrets.toml yok / anahtar yok
        return varsayilan


ADMIN_KULLANICI = _secret("admin", "username")
ADMIN_PAROLA = _secret("admin", "password_hash")
# Bu dağıtım bağımsız prototiptir. Secrets ayarı, okul entegrasyonu veya gerçek üretim modu oluşturmaz.
DEMO_MODU = True


@st.cache_resource
def _veritabanini_hazirla() -> bool:
    db.hazirla()
    return True


_veritabanini_hazirla()

# ------------------------------------------------------------ oturum durumu
for _k, _v in {"yonetici_giris": False, "yonetici_adi": "", "son_etkinlik": 0.0, "hatali_giris": 0,
               "kilit_bitis": 0.0, "form_surumu": 0, "son_bildirim": None, "ana_menu": "Genel bakış"}.items():
    ss.setdefault(_k, _v)


def flash(tur: str, mesaj: str) -> None:
    """st.rerun() sonrasında da görünen bildirim (v1'de rerun mesajı yutuyordu)."""
    ss["_flash"] = (tur, mesaj)


def flash_goster() -> None:
    f = ss.pop("_flash", None)
    if f:
        getattr(st, f[0])(f[1])


def sayfaya_git(ad: str) -> None:
    # Düğme geri çağrısı (callback): widget anahtarı yalnızca burada güvenle değiştirilebilir.
    ss["ana_menu"] = ad


def oturumu_kapat(neden: str = "Oturum kapatıldı") -> None:
    if ss.yonetici_giris:
        db.denetim_ekle(ss.yonetici_adi, neden)
    ss.yonetici_giris = False
    ss.yonetici_adi = ""


def oturum_denetle() -> None:
    if ss.yonetici_giris:
        if time.time() - ss.son_etkinlik > OTURUM_ZAMAN_ASIMI_SN:
            oturumu_kapat("Oturum zaman aşımı")
            flash("warning", "Hareketsizlik nedeniyle yönetici oturumu kapatıldı.")
        else:
            ss.son_etkinlik = time.time()


def hiz_siniri(anahtar: str, pencere_sn: int, maks: int) -> tuple[bool, int]:
    simdi = time.time()
    liste = [t for t in ss.get(anahtar, []) if simdi - t < pencere_sn]
    if len(liste) >= maks:
        ss[anahtar] = liste
        return False, int(pencere_sn - (simdi - liste[0])) + 1
    liste.append(simdi)
    ss[anahtar] = liste
    return True, 0


def acil_hat_html() -> str:
    parca = " · ".join(f"<b>{html.escape(n)}</b> {html.escape(a)}" for n, a in ACIL_HATLAR)
    return f"<div class='emergency'>Acil bir tehlike varsa beklemeyin: {parca}</div>"


def yonetici_gerekli() -> None:
    if ss.yonetici_giris:
        return
    st.markdown(
        "<div class='access-panel'><strong>Yönetici erişimi gerekli</strong><br>"
        "<span style='color:#5b6b7e'>Bu bölümü görüntülemek için yönetici oturumu açın.</span></div>",
        unsafe_allow_html=True,
    )
    st.button("Yönetici girişine git", type="primary", on_click=sayfaya_git, args=("Yönetici girişi",))
    altbilgi()
    st.stop()


def altbilgi() -> None:
    st.divider()
    st.caption("Güvenli Okul · Bildirim ve takip platformu · Kural tabanlı sinyaller karar değildir.")


def pill(metin: str, sinif: str) -> str:
    return f"<span class='pill {sinif}'>{html.escape(metin)}</span>"


DURUM_SINIF = {"İnceleme bekliyor": "status-waiting", "İnceleniyor": "status-active",
               "Takip gerekiyor": "status-followup", "Sonuçlandırıldı": "status-done"}
ONCELIK_SINIF = {"Sinyal yok": "prio-none", "Düşük": "prio-low", "Orta": "prio-mid",
                 "Yüksek": "prio-high", "Acil": "prio-urgent"}


# ============================================================ 1. GENEL BAKIŞ
def sayfa_genel_bakis() -> None:
    st.markdown(
        """<div class="hero"><div class="eyebrow">BİLDİRİM VE TAKİP PLATFORMU</div>
        <h1>Güvenli bir okul ortamı için daha düzenli bildirim süreçleri.</h1>
        <p>Bildirimleri düzenli biçimde kaydetmek, inceleme adımlarını takip etmek ve güvenli okul kültürünü desteklemek için tasarlandı.</p></div>""",
        unsafe_allow_html=True,
    )
    if ss.yonetici_giris:
        kay = db.kayitlari_getir()
        acik = [k for k in kay if k["durum"] != "Sonuçlandırıldı"]
        st.subheader("Yönetici özeti")
        o = st.columns(4)
        o[0].metric("Açık kayıt", len(acik))
        o[1].metric("Yüksek/Acil sinyal (açık)", sum(k["oncelik"] in ("Acil", "Yüksek") for k in acik))
        o[2].metric(f"{SLA_SAAT} sa. aşan bekleyen",
                    sum(k["durum"] == "İnceleme bekliyor" and db.gecen_saat(k["olusturma_zamani"]) > SLA_SAAT for k in kay))
        o[3].metric("Toplam kayıt", len(kay))
        st.button("İnceleme kuyruğunu aç", type="primary", on_click=sayfaya_git, args=("Bildirim inceleme",), key="g_kuyruk")
    st.markdown(acil_hat_html(), unsafe_allow_html=True)
    st.subheader("Nasıl kullanılır?")
    a, b, c = st.columns(3, gap="medium")
    with a:
        st.markdown("<div class='soft-card'><h3>1 · Bildirim oluştur</h3><p>Formu doldur; anonim "
                    "olmayı seçebilirsin. Sana bir takip kodu verilir.</p></div>", unsafe_allow_html=True)
        st.button("Yeni bildirim", type="primary", on_click=sayfaya_git, args=("Yeni bildirim",), key="g_yeni")
    with b:
        st.markdown("<div class='soft-card'><h3>2 · Durumu sorgula</h3><p>Takip koduyla kaydın hangi "
                    "aşamada olduğunu gör (kişisel bilgi gösterilmez).</p></div>", unsafe_allow_html=True)
        st.button("Bildirim sorgula", on_click=sayfaya_git, args=("Bildirim sorgula",), key="g_sorgu")
    with c:
        st.markdown("<div class='soft-card'><h3>3 · İnsan incelemesi</h3><p>Yetkili kişiler kaydı inceler, "
                    "birim atar ve not ekler; her işlem kayda geçer.</p></div>", unsafe_allow_html=True)
        st.button("Yönetici girişi", on_click=sayfaya_git, args=("Yönetici girişi",), key="g_yon")

    st.subheader("Güvenlik ilkeleri")
    g1, g2, g3 = st.columns(3, gap="medium")
    g1.markdown("**Gizlilik**\n\nAnonim seçenekte kimlik alanları hiç kaydedilmez; açıklamadaki "
                "telefon, T.C. kimlik no, e-posta ve IBAN otomatik maskelenir.")
    g2.markdown("**İnsan değerlendirmesi**\n\nOtomatik ifade eşleşmeleri yalnızca öncelik sinyalidir; "
                "kesin karar veya kanıt değildir.")
    g3.markdown("**Hesap verebilirlik**\n\nYönetici işlemleri, kim tarafından yapıldığıyla birlikte "
                "denetim kaydında tutulur.")


# =========================================================== 2. YENİ BİLDİRİM
def sayfa_yeni_bildirim() -> None:
    st.title("Yeni bildirim")
    st.markdown(acil_hat_html(), unsafe_allow_html=True)

    son = ss.son_bildirim
    if son:
        with st.container(border=True):
            st.success("Bildirimin kaydedildi.")
            st.write("**Takip kodun** (kaydın durumunu bu kodla sorgulayabilirsin; kaybedersen yeniden üretilemez):")
            st.code(son["takip_no"])
            if son["maskelenen"]:
                st.info("Açıklamandaki şu bilgiler gizlilik için otomatik gizlendi: " + ", ".join(son["maskelenen"]) + ".")
            if son["oncelik"] in ("Acil", "Yüksek"):
                st.error("Yazdıkların için endişeleniyoruz. Şu an güvende değilsen ya da kendini veya başkasını "
                         "tehlikede hissediyorsan lütfen hemen güvendiğin bir yetişkine, okul rehber öğretmenine "
                         "ya da yukarıdaki acil hatlara ulaş.")
            st.info("Bu takip kodu yalnızca bu uygulamadaki kaydı tanımlar. Kayıt herhangi bir okula veya yetkili ekibe otomatik olarak iletilmez.")
            st.button("Yeni bildirim oluştur", on_click=lambda: ss.update(son_bildirim=None), key="son_kapat")
        return

    if DEMO_MODU:
        st.warning("Bu çalışma alanı gerçek ve gizli bildirimler için tasarlanmamıştır. Gerçek ad, okul numarası, "
                   "telefon, adres veya başka bir öğrenciyi tanımlayan bilgi girmeyin.")
    else:
        st.info("Açıklamada gerçek kişilerin adını, iletişim bilgilerini veya onları tanımlayabilecek ayrıntıları paylaşma.")

    # Anonim seçimi formun DIŞINDA: değişince ad/soyad/sınıf alanları anında açılıp kapanır.
    anonim = st.checkbox("Anonim bildirim oluştur", value=True, key="anonim_secimi",
                         help="Açıksa ad, soyad ve sınıf kayda alınmaz; kayıt zamanı saate yuvarlanır.")
    no = ss.form_surumu
    with st.form(f"bildirim_formu_{no}", clear_on_submit=False):
        ad = st.text_input("Ad (örnek bilgi)" if DEMO_MODU else "Ad", max_chars=40, disabled=anonim, key=f"ad_{no}")
        soyad = st.text_input("Soyad (örnek bilgi)" if DEMO_MODU else "Soyad", max_chars=40, disabled=anonim, key=f"soyad_{no}")
        sinif = st.selectbox("Sınıf / şube", ["Seçilmedi"] + SINIFLAR, disabled=anonim, key=f"sinif_{no}")
        olay_turu = st.selectbox("Olay türü", OLAY_TURLERI, key=f"tur_{no}")
        ortam = st.selectbox("Olayın gerçekleştiği ortam", ORTAMLAR, key=f"ortam_{no}")
        zaman_bilgisi = st.selectbox("Yaklaşık zaman", ZAMANLAR, key=f"zaman_{no}")
        tekrar = st.radio("Tekrarlanma durumu", TEKRARLAR, horizontal=True, key=f"tekrar_{no}")
        aciklama = st.text_area("Olay açıklaması", max_chars=3000, height=150, key=f"aciklama_{no}",
                                placeholder="Ne oldu, nerede ve ne zaman oldu? Telefon, adres gibi bilgileri yazma.")
        onay = st.checkbox(
            "Gerçek kişisel bilgi içermeyen örnek bir açıklama girdiğimi onaylıyorum.",
            key=f"onay_{no}")
        gonder = st.form_submit_button("Bildirimi oluştur", type="primary")

    if not gonder:
        return
    if not aciklama.strip():
        st.error("Lütfen olay açıklamasını yaz.")
    elif not onay:
        st.error("Lütfen onay kutusunu işaretle.")
    elif not anonim and (not ad.strip() or not soyad.strip()):
        st.error("Anonim olmayan kayıt için ad ve soyad gerekli.")
    elif not anonim and sinif == "Seçilmedi":
        st.error("Kimlik bilgisi belirtilen kayıt için sınıf seç.")
    else:
        izin, bekle = hiz_siniri("gonderim_zamanlari", FORM_PENCERE_SN, FORM_PENCERE_MAKS)
        if not izin:
            st.error(f"Kısa sürede çok fazla bildirim gönderildi. Lütfen yaklaşık {bekle} saniye sonra tekrar dene.")
            return
        try:
            sonuc = db.bildirim_ekle(
                olay_turu=olay_turu, ortam=ortam, zaman_bilgisi=zaman_bilgisi, tekrar_durumu=tekrar,
                aciklama=aciklama.strip(), anonim=anonim, ad=ad.strip(), soyad=soyad.strip(),
                sinif="" if sinif == "Seçilmedi" else sinif, demo=DEMO_MODU)
        except (sqlite3.Error, RuntimeError):
            st.error("Kayıt oluşturulamadı. Lütfen daha sonra tekrar dene.")
            return
        ss.son_bildirim = {"takip_no": sonuc["takip_no"], "maskelenen": sonuc["maskelenen"],
                           "oncelik": sonuc["analiz"].oncelik}
        ss.form_surumu += 1   # formu (yalnızca BAŞARIDA) temizler
        st.rerun()


# ========================================================= 3. BİLDİRİM SORGULA
def sayfa_sorgula() -> None:
    st.title("Bildirim sorgula")
    st.write("Bildirim oluştururken verilen takip kodunu gir. Yalnızca kaydın durumu gösterilir; "
             "açıklama, notlar ve kişi bilgileri paylaşılmaz.")
    with st.form("sorgu_formu"):
        kod = st.text_input("Takip kodu", placeholder="GO-XXXXXXXXXX", max_chars=20)
        ara = st.form_submit_button("Sorgula", type="primary")
    if not ara:
        return
    izin, bekle = hiz_siniri("sorgu_zamanlari", SORGU_PENCERE_SN, SORGU_MAKS)
    if not izin:
        st.error(f"Çok fazla sorgu yapıldı. Lütfen yaklaşık {bekle} saniye sonra tekrar dene.")
        return
    kayit = db.takip_durumu_getir(kod)
    if not kayit:
        st.error("Bu kodla eşleşen bir kayıt bulunamadı. Kodu kontrol edip tekrar dene.")
        return
    st.markdown(
        f"<div class='record-banner'><div><div class='record-kicker'>TAKİP KODU</div>"
        f"<div class='record-id'>{html.escape(kayit['takip_no'])}</div></div>"
        f"{pill(kayit['durum'], DURUM_SINIF.get(kayit['durum'], 'status-waiting'))}</div>",
        unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("Oluşturulma", kayit["olusturma_zamani"])
    c2.metric("Son güncelleme", kayit["son_guncelleme"] or "—")


# ======================================================== 4. YÖNETİCİ GİRİŞİ
def sayfa_yonetici_girisi() -> None:
    st.markdown("<div class='hero'><h1>Yönetici girişi</h1><p>Bildirim inceleme alanına yalnızca "
                "yetkili kullanıcılar erişebilir.</p></div>", unsafe_allow_html=True)
    if ss.yonetici_giris:
        st.success("Yönetici oturumu açık.")
        st.button("Bildirim incelemeye git", type="primary", on_click=sayfaya_git, args=("Bildirim inceleme",))
        return
    if (not ADMIN_KULLANICI or not ADMIN_PAROLA.startswith("pbkdf2_sha256$") or ADMIN_PAROLA.count("$") != 3):
        st.error("Yönetici hesabı yapılandırılmamış. .streamlit/secrets.toml içindeki [admin] bölümüne kullanıcı adını "
                 "ve tools/parola_hash.py ile üretilmiş PBKDF2 password_hash değerini ekleyin.")
        return
    kalan = int(ss.kilit_bitis - time.time())
    if kalan > 0:
        st.error(f"Çok fazla hatalı deneme. Lütfen {kalan} saniye sonra tekrar deneyin.")
        return
    if db.basarisiz_giris_sayisi(15) >= GLOBAL_HATALI_ESIK:
        st.error("Sistem genelinde çok fazla hatalı giriş denemesi var. Lütfen bir süre sonra tekrar deneyin.")
        return

    with st.form("yonetici_giris_formu"):
        kullanici = st.text_input("Kullanıcı adı")
        parola = st.text_input("Parola", type="password")
        giris = st.form_submit_button("Giriş yap", type="primary")
    if not giris:
        return
    if guvenlik.kimlik_dogrula(kullanici, parola, ADMIN_KULLANICI, ADMIN_PAROLA):
        db.giris_denemesi_kaydet(True)
        ss.update(yonetici_giris=True, yonetici_adi=ADMIN_KULLANICI, son_etkinlik=time.time(), hatali_giris=0)
        db.denetim_ekle(ADMIN_KULLANICI, "Yönetici girişi")
        flash("success", "Yönetici girişi başarılı.")
        st.rerun()
    else:
        db.giris_denemesi_kaydet(False)
        ss.hatali_giris += 1
        db.denetim_ekle("(bilinmiyor)", "Başarısız giriş denemesi")
        if ss.hatali_giris >= OTURUM_HATALI_ESIK:
            ss.kilit_bitis = time.time() + OTURUM_KILIT_SN
            ss.hatali_giris = 0
        st.error("Kullanıcı adı veya parola hatalı.")


# ===================================================== 5. BİLDİRİM İNCELEME
def _kayit_detayi(k: dict) -> None:
    st.markdown("#### Bildirim ayrıntıları")
    a, b = st.columns(2)
    a.markdown(f"**Olay türü**  \n{k['olay_turu']}\n\n**Ortam**  \n{k['ortam']}\n\n**Yaklaşık zaman**  \n{k['zaman_bilgisi']}")
    b.markdown(f"**Tekrarlanma**  \n{k['tekrar_durumu']}\n\n**Oluşturulma**  \n{k['olusturma_zamani']}\n\n"
               f"**Bildirim türü**  \n{'Anonim' if k['anonim'] else 'Kimlik bilgisi belirtilmiş'}")
    if not k["anonim"]:
        with st.expander("Bildirimde belirtilen kişi bilgileri"):
            st.write(f"Ad soyad: {(k['ad'] or 'Belirtilmedi')} {k['soyad'] or ''}")
            st.write(f"Sınıf: {k['sinif'] or 'Belirtilmedi'}")
    st.markdown("**Açıklama**")
    with st.container(border=True):
        st.write(k["aciklama"] or "Açıklama bulunmuyor.")
    with st.expander("Otomatik sinyal ve değerlendirme notu", expanded=k["oncelik"] in ("Acil", "Yüksek")):
        st.write(f"**Öncelik sinyali:** {k['oncelik']}")
        st.write(f"**Kategoriler:** {k['kategoriler'] or '—'}")
        st.write(f"**Eşleşen ifadeler:** {k['eslesmeler'] or 'Belirgin eşleşme yok'}")
        for u in filter(None, (k["baglam_uyarilari"] or "").split(" | ")):
            st.warning(u)
        if k["maskelenen"]:
            st.caption(f"Açıklamada otomatik maskelenen bilgi türleri: {k['maskelenen']}")
        st.caption(f"Algılayıcı sürümü: {k['analiz_surumu'] or 'v1 (eski kayıt)'}. Kural tabanlı eşleşme; kanıt veya "
                   "karar değildir, bağlamı anlayamaz. Eşleşme olmaması da sorun olmadığı anlamına gelmez.")


def _inceleme_formlari(k: dict) -> None:
    no = k["takip_no"]
    st.markdown("#### İnceleme ve yönlendirme")
    with st.form(f"inceleme_{no}"):
        c1, c2 = st.columns(2)
        durum = c1.selectbox("İnceleme durumu", DURUMLAR, key=f"durum_{no}",
                             index=DURUMLAR.index(k["durum"]) if k["durum"] in DURUMLAR else 0)
        birim = c2.selectbox("Sorumlu birim", BIRIMLER, key=f"birim_{no}",
                             index=BIRIMLER.index(k["birim"]) if k["birim"] in BIRIMLER else 0)
        kaydet = st.form_submit_button("Değişiklikleri kaydet", type="primary")
    if kaydet:
        try:
            degisen = db.durum_ve_birim_guncelle(no, durum, birim, ss.yonetici_adi)
        except (sqlite3.Error, ValueError, LookupError):
            st.error("Değişiklik kaydedilemedi. Lütfen yeniden deneyin.")
        else:
            flash("success" if degisen else "info",
                  "İnceleme bilgileri kaydedildi." if degisen else "Değişiklik yapılmadı; bilgiler zaten güncel.")
            st.rerun()

    notlar_k, gecmis_k = st.columns(2, gap="large")
    with notlar_k:
        st.markdown("#### İnceleme notları")
        with st.form(f"not_{no}"):
            metin = st.text_area("Yeni not", max_chars=db.MAKS_NOT_UZUNLUGU, key=f"not_metni_{no}",
                                 placeholder="İncelemeyle ilgili kısa not ekleyin.")
            gonder = st.form_submit_button("Notu kaydet")
        if gonder:
            try:
                db.not_ekle(no, metin, ss.yonetici_adi)
            except ValueError:
                st.error("Boş not eklenemez.")
            except (sqlite3.Error, LookupError):
                st.error("Not kaydedilemedi.")
            else:
                flash("success", "Not eklendi.")
                st.rerun()
        notlar = db.notlari_getir(no)
        if not notlar:
            st.caption("Henüz not eklenmemiş.")
        for n in notlar:
            with st.container(border=True):
                st.caption(f"{n['zaman']} · {n['yazar'] or '—'}")
                st.write(n["not_metni"])
    with gecmis_k:
        st.markdown("#### İşlem geçmişi")
        gecmis = db.gecmisi_getir(no)
        if not gecmis:
            st.caption("Henüz işlem kaydı bulunmuyor.")
        for g in gecmis:
            with st.container(border=True):
                st.markdown(f"**{g['islem']}**")
                st.caption(f"{g['zaman']} · {g['aktor'] or '—'}")
                if g["ayrinti"]:
                    st.write(g["ayrinti"])


def _kayitlar_sekmesi(kayitlar: list[dict]) -> None:
    sayac = {d: sum(k["durum"] == d for k in kayitlar) for d in DURUMLAR}
    acil = sum(k["oncelik"] in ("Acil", "Yüksek") and k["durum"] != "Sonuçlandırıldı" for k in kayitlar)
    gecikmis = sum(k["durum"] == "İnceleme bekliyor" and db.gecen_saat(k["olusturma_zamani"]) > SLA_SAAT for k in kayitlar)
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m6.metric(f"{SLA_SAAT} sa. aşan bekleyen", gecikmis)
    m1.metric("Toplam kayıt", len(kayitlar))
    m2.metric("İlk inceleme", sayac["İnceleme bekliyor"])
    m3.metric("Aktif takip", sayac["İnceleniyor"] + sayac["Takip gerekiyor"])
    m4.metric("Sonuçlandırıldı", sayac["Sonuçlandırıldı"])
    m5.metric("Yüksek/Acil sinyal (açık)", acil)
    if not kayitlar:
        st.info("Henüz kayıt bulunmuyor. Yeni bir bildirim oluşturulduğunda kayıt burada görünür.")
        return

    filtre_k, detay_k = st.columns([0.9, 1.7], gap="large")
    with filtre_k:
        st.markdown("#### Kayıt kuyruğu")
        arama = st.text_input("Kayıt ara", placeholder="Takip kodu, olay türü, ortam veya birim", key="inc_arama")
        durum_f = st.selectbox("İnceleme durumu", ["Tüm durumlar"] + DURUMLAR, key="inc_durum")
        oncelik_f = st.selectbox("Öncelik sinyali", ["Tümü"] + list(ONCELIKLER[::-1]), key="inc_oncelik")
        tur_f = st.selectbox("Bildirim türü", ["Tümü", "Anonim", "Kimlik bilgisi belirtilmiş"], key="inc_anonim")
        birim_f = st.selectbox("Sorumlu birim", ["Tüm birimler"] + BIRIMLER, key="inc_birim")
        sirala = st.selectbox("Sıralama", ["Öncelik (yüksekten)", "En yeni önce", "En eski önce"], key="inc_sira")

        gorunen = []
        a = arama.strip().casefold()
        for k in kayitlar:
            if durum_f != "Tüm durumlar" and k["durum"] != durum_f: continue
            if oncelik_f != "Tümü" and k["oncelik"] != oncelik_f: continue
            if tur_f == "Anonim" and not k["anonim"]: continue
            if tur_f == "Kimlik bilgisi belirtilmiş" and k["anonim"]: continue
            if birim_f != "Tüm birimler" and k["birim"] != birim_f: continue
            if a and a not in " ".join(str(k.get(x, "")) for x in ("takip_no", "olay_turu", "ortam", "birim")).casefold():
                continue
            gorunen.append(k)
        gorunen.sort(key=lambda x: x["olusturma_zamani"], reverse=(sirala != "En eski önce"))
        if sirala.startswith("Öncelik"):
            gorunen.sort(key=lambda x: ONCELIK_SIRASI.get(x["oncelik"], 0), reverse=True)  # kararlı sıralama

        st.caption(f"{len(gorunen)} kayıt")
        if not gorunen:
            st.info("Bu filtrelerle eşleşen kayıt yok.")
            return
        secenekler = [k["takip_no"] for k in gorunen]
        etiket = {k["takip_no"]: f"{k['takip_no']} · {k['olay_turu']} · {k['oncelik']} · {k['durum']}"
                  + (" · GECİKMİŞ" if k["durum"] == "İnceleme bekliyor" and db.gecen_saat(k["olusturma_zamani"]) > SLA_SAAT else "")
                  for k in gorunen}
        if ss.get("inceleme_secili") not in secenekler:
            ss["inceleme_secili"] = secenekler[0]   # widget oluşturulmadan ÖNCE atama güvenlidir
        secili_no = st.selectbox("Kayıt seç", secenekler, key="inceleme_secili", format_func=etiket.get)
        k = next(x for x in gorunen if x["takip_no"] == secili_no)
        st.markdown(
            f"<div class='record-banner'><div><div class='record-kicker'>SEÇİLİ KAYIT</div>"
            f"<div class='record-id'>{html.escape(k['takip_no'])}</div></div><div class='pills'>"
            f"{pill(k['durum'], DURUM_SINIF.get(k['durum'], 'status-waiting'))}"
            f"{pill('Sinyal: ' + k['oncelik'], ONCELIK_SINIF.get(k['oncelik'], 'prio-none'))}</div></div>",
            unsafe_allow_html=True)
    with detay_k:
        _kayit_detayi(k)
        _inceleme_formlari(k)


def sayfa_inceleme() -> None:
    st.markdown("<div class='page-heading'><div class='eyebrow-dark'>KAYIT YÖNETİMİ</div><h1>Bildirim inceleme</h1>"
                "<p>Kayıtları tek bir çalışma alanında görüntüleyin, yönlendirin ve işlem geçmişini takip edin.</p></div>",
                unsafe_allow_html=True)
    yonetici_gerekli()
    kayitlar = db.kayitlari_getir()
    sekme1, sekme2, sekme3 = st.tabs(["Kayıtlar", "Denetim kaydı", "Dışa aktarım ve saklama"])
    with sekme1:
        _kayitlar_sekmesi(kayitlar)
    with sekme2:
        st.caption("Girişler, başarısız denemeler, dışa aktarımlar ve silme işlemleri burada izlenir.")
        satirlar = db.denetim_getir()
        if satirlar:
            st.dataframe([{"Zaman": r["zaman"], "Kullanıcı": r["aktor"], "İşlem": r["islem"],
                           "Ayrıntı": r["ayrinti"]} for r in satirlar], hide_index=True)
        else:
            st.info("Henüz denetim kaydı yok.")
    with sekme3:
        st.subheader("Dışa aktarım")
        kimlik = st.checkbox("Kimlik bilgilerini (ad, soyad, sınıf) dahil et", value=False,
                             help="Varsayılan olarak kapalıdır (veri minimizasyonu).")
        st.download_button("CSV indir", data=db.csv_aktar(kayitlar, kimlik),
                           file_name=f"guvenli_okul_{datetime.now(db.TZ):%Y%m%d_%H%M}.csv", mime="text/csv",
                           on_click=db.denetim_ekle,
                           args=(ss.yonetici_adi, "CSV dışa aktarım", "kimlik dahil" if kimlik else "kimlik hariç"))
        st.subheader("Saklama süresi")
        st.caption("Süresi dolan, sonuçlandırılmış kayıtlar notları ve geçmişiyle birlikte kalıcı olarak silinir.")
        gun = st.number_input("Saklama süresi (gün)", min_value=30, value=180, step=30)
        onay = st.checkbox("Silmenin geri alınamayacağını anlıyorum", key="silme_onay")
        if st.button("Süresi dolan kayıtları sil", disabled=not onay):
            n = db.sonuclanmis_kayitlari_sil(int(gun), ss.yonetici_adi)
            flash("success", f"{n} kayıt silindi.")
            st.rerun()
    altbilgi()


# ========================================================== 6. İSTATİSTİKLER
def _saat_metni(o: dict) -> str:
    return "Veri yok" if not o["n"] else f"{o['medyan']:.1f} sa (n={o['n']})"


def sayfa_istatistikler() -> None:
    st.title("İstatistikler")
    if not ISTATISTIKLER_HERKESE_ACIK:
        yonetici_gerekli()
    s = db.istatistik_ozeti()
    st.caption("Grafikler yalnızca bu uygulamada kayıtlı bilgileri özetler; okul geneline ilişkin sonuç göstermez.")
    if not s["toplam"]:
        st.info("Henüz kayıt yok. Yeni kayıtlar eklendikçe istatistikler burada görüntülenir.")
        return
    if s["toplam"] < 10:
        st.warning("Kayıt sayısı çok az; yüzdeler ve karşılaştırmalar yanıltıcı olabilir, yorum yapmayın.")
    m = st.columns(4)
    m[0].metric("Toplam bildirim", s["toplam"])
    m[1].metric("Anonim oranı", f"%{100 * s['anonim'] / s['toplam']:.0f}")
    m[2].metric("İlk işlem süresi (medyan)", _saat_metni(s["ilk_inceleme_saat"]))
    m[3].metric("Sonuçlanma süresi (medyan)", _saat_metni(s["sonuclanma_saat"]))
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.subheader("Durum dağılımı")
        st.bar_chart(s["durum"], horizontal=True)
        st.subheader("Öncelik sinyali dağılımı")
        st.bar_chart(s["oncelik"], horizontal=True)
    with c2:
        st.subheader("Olay türü dağılımı")
        st.bar_chart(s["tur"], horizontal=True)
        st.subheader("Son 30 gün: günlük bildirim")
        if s["gunluk"]:
            st.bar_chart(dict(s["gunluk"]))
        else:
            st.caption("Bu dönemde kayıt yok.")
    st.caption("Süreler kayıt oluşturma ile ilk durum değişikliği / 'Sonuçlandırıldı' arasındaki farktır. "
               "Anonim kayıtların zamanı saate yuvarlandığından süreler ±1 saat sapabilir.")


# ================================================== 7. ARAŞTIRMA VE TEST
KONTROL_LISTESI = (
    ("T01", "Anonim bildirim", "Anonim seçenek açıkken ad/soyad/sınıf kaydedilmemeli."),
    ("T02", "Sınıf seçenekleri", "9/A … 12/B seçenekleri görünmeli."),
    ("T03", "Takip kodu", "Her kayıt benzersiz ve tahmin edilmesi zor bir kod üretmeli."),
    ("T04", "Yetkisiz erişim", "Girişsiz, inceleme/istatistik/denetim kayıtları görünmemeli."),
    ("T05", "Durum güncelleme", "Değişiklik kaydedilmeli, geçmişe işlemi yapanla birlikte eklenmeli."),
    ("T06", "Not geçmişi", "Not kaydedilmeli; yazar bilgisiyle ilgili kayıtta görünmeli."),
    ("T07", "Boş form", "Açıklama veya onay yoksa kayıt oluşturulmamalı; yazılan metin silinmemeli."),
    ("T08", "Temiz başlangıç", "Yeni kurulumda örnek kayıt olmamalı; yeniden başlatmada kayıt silinmemeli."),
    ("T09", "İstatistikler", "Grafik toplamları kayıt sayılarıyla uyumlu olmalı."),
    ("T10", "Güvenli metin", "Arayüz gerçek kişisel veri girilmemesi gerektiğini açıkça belirtmeli."),
    ("T11", "Hatalı giriş sınırı", "5 hatalı denemeden sonra giriş geçici olarak kilitlenmeli."),
    ("T12", "Oturum zaman aşımı", "30 dakika hareketsizlikte yönetici oturumu kapanmalı."),
    ("T13", "Kişisel veri maskeleme", "Açıklamaya yazılan telefon/T.C. no/e-posta/IBAN kayıtta maskeli olmalı."),
    ("T14", "Takip kodu sorgusu", "Sorgu yalnızca durum ve tarih göstermeli; açıklama/not göstermemeli."),
    ("T15", "CSV dışa aktarım", "Kimlik alanları varsayılan olarak dışarıda olmalı; işlem denetim kaydına yazılmalı."),
)


def _degerlendirme_sekmesi() -> None:
    st.write("Algılayıcının sentetik (elle yazılmış, gerçek veri içermeyen) örnek kümesindeki performansını ölçer. "
             "Aynı ölçüm komut satırından `python -m unittest discover -s testler` ile de çalışır.")
    st.caption(f"Algılayıcı sürümü: {ht.SURUM} · Sözlük: {sum(ht.sozluk_ozeti().values())} ifade, "
               + ", ".join(f"{k}: {v}" for k, v in ht.sozluk_ozeti().items()))
    if st.button("Değerlendirmeyi çalıştır", type="primary"):
        ss["degerlendirme_sonucu"] = degerlendirme.degerlendir()
    r = ss.get("degerlendirme_sonucu")
    if not r:
        return
    m = st.columns(5)
    m[0].metric("Örnek sayısı", r["toplam"])
    m[1].metric("Kesinlik (precision)", f"{r['precision']:.2f}")
    m[2].metric("Duyarlılık (recall)", f"{r['recall']:.2f}")
    m[3].metric("F1", f"{r['f1']:.2f}")
    m[4].metric("Doğruluk", f"{r['accuracy']:.2f}")
    st.markdown("**Karışıklık matrisi**")
    st.table({"": ["Gerçekte sinyal var", "Gerçekte sinyal yok"],
              "Sinyal verildi": [r["tp"], r["fp"]], "Sinyal verilmedi": [r["fn"], r["tn"]]})
    st.markdown("**Örnek türüne göre doğruluk**")
    st.dataframe([{"Tür": t, "Örnek": o["n"], "Doğru": o["dogru"], "Oran": round(o["dogru"] / o["n"], 2)}
                  for t, o in r["tur_ozeti"].items()], hide_index=True)
    st.markdown("**Kategoriye göre yakalama (duyarlılık)**")
    st.dataframe([{"Kategori": t, "Örnek": o["n"], "Yakalanan": o["bulunan"], "Oran": round(o["bulunan"] / o["n"], 2)}
                  for t, o in r["kategori_ozeti"].items()], hide_index=True)
    with st.expander(f"Yanlış alarmlar ({len(r['yanlis_pozitifler'])}) ve kaçırılanlar ({len(r['kacirilanlar'])})"):
        st.write("**Yanlış alarm:**", r["yanlis_pozitifler"] or "—")
        st.write("**Kaçırılan:**", r["kacirilanlar"] or "—")
    st.warning("Küme küçüktür, araştırmacılar tarafından yazılmıştır ve sözlük bu kümeye bakılarak iyileştirilmiştir; "
               "sonuçlar iyimserdir ve genellenemez. Bilimsel geçerlik için bağımsız, etik onaylı ve en az iki "
               "değerlendiricinin etiketlediği bir veri kümesi gerekir.")
    st.download_button("Sonucu JSON olarak indir", json.dumps(r, ensure_ascii=False, indent=2),
                       file_name="degerlendirme_sonucu.json", mime="application/json")


def sayfa_arastirma() -> None:
    st.title("Araştırma ve kalite kontrol")
    s1, s2, s3 = st.tabs(["Otomatik değerlendirme", "Elle kontrol listesi", "Yöntem ve sınırlılıklar"])
    with s1:
        _degerlendirme_sekmesi()
    with s2:
        for kod, baslik, aciklama in KONTROL_LISTESI:
            with st.expander(f"{kod} · {baslik}"):
                st.write(aciklama)
                st.checkbox("Bu senaryoyu test ettim", key=f"test_{kod}")
        bitti = sum(bool(ss.get(f"test_{kod}")) for kod, _, _ in KONTROL_LISTESI)
        st.progress(bitti / len(KONTROL_LISTESI), text=f"İşaretlenen test: {bitti}/{len(KONTROL_LISTESI)}")
        st.warning("İşaretler yalnızca bu oturumda tutulur; resmi test raporu veya bilimsel doğrulama yerine geçmez.")
    with s3:
        st.markdown("""
1. **Amaç:** Bildirim sürecinin anlaşılırlığını, temel işlevlerin doğruluğunu ve kural tabanlı sinyalin ölçülebilir
   başarımını raporlamak.
2. **Algılayıcı:** Makine öğrenmesi içermez; Türkçe'ye duyarlı normalleştirme (İ/ı, ASCII katlama), kelime başı sınırı,
   harf tekrarı/ayraç/rakamla yazım çözümü ve kategori+ağırlık tabanlı öncelik kuralı kullanır.
3. **Ölçüt:** Kesinlik, duyarlılık, F1 ve kategori bazlı yakalama; ayrıca "zor örnek" kümesiyle bilinen sınırlılıklar.
4. **Sınırlılıklar:** Bağlam, ironi, imâ ve ima yoluyla dışlama yakalanmaz; deyimsel abartı ("babam beni öldürecek")
   yanlış alarm üretir; yazım hataları ("apdal") kaçar; sözlük küçüktür.
5. **Yol haritası:** (a) etik kurul/okul izniyle, kimliksizleştirilmiş ve en az iki uzmanca etiketlenmiş veri kümesi,
   (b) değerlendiriciler arası uyum (Cohen kappa), (c) eğitim/doğrulama/test ayrımı, (d) kural tabanlı yöntemin bir
   dil modeli veya sınıflandırıcı ile karşılaştırılması, (e) kullanılabilirlik testi (SUS ölçeği).
6. **Etik:** Gerçek öğrenci verisi için önceden okul/veli onayı, gönüllülük, veri minimizasyonu ve güvenli saklama planı
   gerekir. Bu uygulamada gerçek öğrenci verisi kullanmayın.""")


# ======================================================= 8. GÜVENLİ KULLANIM
def sayfa_guvenli_kullanim() -> None:
    st.title("Güvenli kullanım")
    st.markdown(acil_hat_html(), unsafe_allow_html=True)
    st.subheader("Platformun işlevleri")
    st.markdown("""
- Bildirim kaydı oluşturur; anonim bildirim seçeneği sunar (kimlik alanları hiç yazılmaz, zaman saate yuvarlanır).
- Açıklamadaki telefon, T.C. kimlik no, e-posta ve IBAN'ı otomatik maskeler.
- Takip koduyla yalnızca durum sorgulamaya izin verir.
- Yönetici girişinden sonra kayıtları listeler; durum/birim günceller; not ve işlem geçmişi tutar.
- Girişleri ve yönetici işlemlerini denetim kaydında saklar; CSV dışa aktarım ve saklama süresi temizliği sunar.
- İfade eşleşmelerini yalnızca insan incelemesi için öncelik sinyali olarak gösterir.""")
    st.subheader("Sınırlar")
    st.markdown("""
- Gerçek bir okul veya rehberlik servisine bağlı değildir; resmi bildirim ya da acil yardım hizmeti değildir.
- Zorbalık hakkında otomatik kesin karar vermez; sinyaller yanlış alarm üretebilir ve olayları kaçırabilir.
- Tek yönetici hesabı kurumsal kimlik doğrulamanın (SSO/2FA) yerini tutmaz.
- Yerel SQLite dosyasının bulut ortamında kalıcı olacağı garanti edilmez; yedekleme planı gerekir.
- Hatalı giriş ve zaman aşımı korumaları vardır, ancak bu bir güvenlik denetiminden geçmemiştir.""")
    st.subheader("Gerçek kullanıma geçmeden önce (kontrol listesi)")
    st.markdown("""
- **KVKK (6698):** veri sorumlusunun belirlenmesi, aydınlatma metni, hukuki sebep/veli onayı, saklama-imha politikası,
  gerekiyorsa VERBİS ve veri işleyen sözleşmeleri. Çocuk verisi ve olası yurt dışı sunucu kullanımı (ör. bulut barındırma)
  ayrıca hukuki değerlendirme gerektirir.
- **Yasal bildirim yükümlülükleri:** çocuğa yönelik istismar/şiddet şüphesinde mevzuattaki bildirim yükümlülükleri bu
  uygulamanın kayıt akışından bağımsızdır; okul yönetimi ve hukuk danışmanıyla netleştirilmelidir.
- **Erişim:** kişi bazlı hesaplar, rol ayrımı, iki aşamalı doğrulama, parola özeti (`tools/parola_hash.py`).
- **Altyapı:** HTTPS, şifreli yedek, günlüklerin korunması, bağımsız güvenlik testi.
- **Okul süreci:** kayıtları kimin, ne kadar sürede inceleyeceği, acil durum protokolü ve rehberlik servisiyle iş akışı.""")
    altbilgi()


# ============================================================== YÖNLENDİRME
SAYFALAR = {
    "Genel bakış": sayfa_genel_bakis,
    "Yeni bildirim": sayfa_yeni_bildirim,
    "Bildirim sorgula": sayfa_sorgula,
    "Yönetici girişi": sayfa_yonetici_girisi,
    "Bildirim inceleme": sayfa_inceleme,
    "İstatistikler": sayfa_istatistikler,
    "Araştırma ve test": sayfa_arastirma,
    "Güvenli kullanım": sayfa_guvenli_kullanim,
}

oturum_denetle()

NAV = (
    ("Genel bakış", "Yeni bildirim", "Bildirim sorgula", "Yönetici girişi",
     "Bildirim inceleme", "İstatistikler", "Araştırma ve test", "Güvenli kullanım")
)
KORUMALI = {"Bildirim inceleme", "İstatistikler"}

if ss.get("ana_menu") not in SAYFALAR:
    ss["ana_menu"] = "Genel bakış"

# Üst marka alanı: okul logosu dosya sisteminden okunur; dosya eksikse uygulama çökmemeli.
logo_col, brand_col, account_col = st.columns([0.10, 0.62, 0.28])
with logo_col:
    logo_yolu = Path(__file__).with_name("bozuyuk_fen_lisesi_logo.png")
    if logo_yolu.exists():
        st.image(str(logo_yolu), width=66)
    else:
        st.markdown("<div class='brand-fallback'>BF</div>", unsafe_allow_html=True)
with brand_col:
    st.markdown(
        "<div class='brand-title'>Güvenli Okul</div>"
        "<div class='brand-subtitle'>Bildirim ve takip platformu</div>"
        "<div class='brand-school'>Bozüyük Fen Lisesi</div>",
        unsafe_allow_html=True,
    )
with account_col:
    if ss.yonetici_giris:
        st.markdown(f"<div class='account-label'>Yönetici oturumu</div><div class='account-name'>{html.escape(ss.yonetici_adi)}</div>", unsafe_allow_html=True)
        st.button("Oturumu kapat", on_click=oturumu_kapat, key="oturum_kapat_ust", type="secondary")
    else:
        st.markdown("<div class='account-label'>Erişim durumu</div><div class='account-name'>Ziyaretçi</div>", unsafe_allow_html=True)

st.markdown("<div class='header-rule'></div>", unsafe_allow_html=True)
secili_sayfa = st.radio(
    "Ana gezinme", NAV[0], horizontal=True, key="ana_menu", label_visibility="collapsed"
)

st.markdown(
    f"<div class='topbar'><div class='crumb'>Güvenli Okul <span>/</span> <b>{html.escape(secili_sayfa)}</b></div>"
    f"<div class='pills'>{pill('Yönetici' if ss.yonetici_giris else 'Ziyaretçi', 'status-active' if ss.yonetici_giris else 'prio-none')}</div></div>",
    unsafe_allow_html=True)
st.markdown(
    "<div class='notice-bar'><span class='notice-dot'></span><span>Bağımsız prototip; gerçek okul sistemine bağlı değildir. "
    "Gerçek öğrenci veya kişisel bilgileri girmeyin.</span></div>",
    unsafe_allow_html=True,
)
flash_goster()

SAYFALAR[secili_sayfa]()
if secili_sayfa in ("Genel bakış", "Yeni bildirim", "Bildirim sorgula", "Yönetici girişi",
                    "İstatistikler", "Araştırma ve test"):
    altbilgi()
