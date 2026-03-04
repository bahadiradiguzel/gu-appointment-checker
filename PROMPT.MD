Utrecht belediyesinin randevu sayfasını (Qmatic Web Booking) periyodik olarak kontrol edecek ve “Verhuizing vanuit buitenland (immigration)” türünde, 1 kişilik randevu için yeni bir uygun tarih/slot açıldığında Telegram’a mesaj gönderecek bir Python projesi yaz.

Web sitesi:
https://afspraak.utrecht.nl/qmaticwebbooking/

İSTEKLERİM:

GENEL MİMARİ

Script Python 3 ile çalışsın.

Yapılandırılabilir olsun: servis adı, lokasyon (varsa), minimum tarih, kontrol aralığı gibi parametreler kod başında sabitler olarak dursun.

Script, bir önceki çalışmada gördüğü uygun tarih/slot listesini yerel bir JSON dosyasında saklasın (örneğin state.json).

Yeni çalışmada güncel listeyi çekip eskiyle karşılaştırsın; yeni eklenen tarih veya slot varsa Telegram’a bildirim göndersin.

Qmatic SAYFASINA ERİŞİM (SELENIUM)

Qmatic Web Booking SPA bir uygulama, muhtemelen açık bir public API yerine JavaScript ile takvimi yüklüyor.
​

Bu nedenle Selenium kullan:

selenium ve uygun WebDriver (Chrome veya Firefox) ile çalışan kod yaz.

Headless modda çalışabilsin.

Script şu adımları otomatik yapsın:

https://afspraak.utrecht.nl/qmaticwebbooking/ adresini aç.

Servis/ürün seçim ekranında “Verhuizing vanuit buitenland (immigration)” hizmetini seç. (Bu adı metinle veya uygun CSS/XPath ile bul.)

Kişi sayısı ekranında 1 kişilik randevu seç.

Uygun tarihlerin göründüğü takvim ekranına ilerle.

Takvim ekranında:

HTML’de uygun tarihleri temsil eden elementleri bul (ör. “enabled/available day” class’ı olan hücreler).

Bu tarihlerden bir liste üret: ["2026-03-10", "2026-03-12", ...] gibi.

Mümkünse her tarih için bir veya daha fazla saat slotu da çıkar (örneğin [{"date": "2026-03-10", "times": ["09:00", "09:20"]}, ...] formatında), ama takvim yapısı karmaşıksa sadece tarih bazlı takip de kabul.

DURUM YÖNETİMİ (STATE)

load_previous_state() fonksiyonu: önceki çalışmada kaydedilmiş JSON’u (yoksa boş liste) okuyup döndürsün.

save_state(current_state) fonksiyonu: son bulunan tarih/slot listesini JSON olarak kaydetsin.

diff_states(old_state, new_state) fonksiyonu: eskiye göre yeni eklenen tarih/slotları bulsun.

Eğer fark yoksa, script sadece log yazıp çıksın; fark varsa Telegram’a mesaj gitsin.

TELEGRAM BİLDİRİM ENTEGRASYONU

Telegram Bot API kullan.
​

Kodun başında şu sabitler olsun:

TELEGRAM_BOT_TOKEN = "BURAYA_TOKEN_GELECEK"

TELEGRAM_CHAT_ID = "BURAYA_CHAT_ID_GELECEK"

Basit bir fonksiyon yaz:

python
import requests

TELEGRAM_BOT_TOKEN = "BURAYA_TOKEN_GELECEK"
TELEGRAM_CHAT_ID = "BURAYA_CHAT_ID_GELECEK"

def send_telegram_message(text: str):
url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
params = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
resp = requests.get(url, params=params)
resp.raise_for_status()
​

Yeni tarih/slot bulunduğunda, örnek mesaj formatı:

"Utrecht – Verhuizing vanuit buitenland için yeni randevu açıldı: 2026-03-10 (09:00, 09:20)"

Birden fazla yeni tarih varsa hepsini bir mesajda listeler.

LOGGING VE HATA YÖNETİMİ

logging modülünü kullan, INFO ve ERROR seviyesinde log yaz.

Selenium tarafında beklenmeyen hata olursa exception yakalanıp loglansın, script temizce sonlansın.

Element’leri bulurken uygun beklemeler (WebDriverWait, expected_conditions) kullan ki sayfa yüklenmesini beklemeden hata vermesin.

ÇALIŞTIRMA VE ZAMANLAMA

if __name__ == "__main__": bloğunda:

Selenium driver’ı başlat.

Akışı sırayla çağır:

Önceki state’i yükle.

Siteye bağlan, uygun tarih/slot listesini çıkar.

Farkı hesapla; yeni slot varsa Telegram’a mesaj gönder.

Güncel state’i kaydet.

Driver’ı kapat.

Script tek çalıştırmada bunu yapsın; ben bunu cron veya başka bir scheduler ile periyodik çağıracağım.

KOD KALİTESİ

Tüm kodu tek bir .py dosyası içinde ver.

Fonksiyonları temiz bir şekilde ayır (setup_driver(), navigate_to_calendar(driver), get_available_slots(driver) vb.).

Gerekli requirements.txt içeriğini de ayrıca yaz (ör: selenium, requests, vs.).

Kodun içinde “BURAYA_TOKEN_GELECEK” gibi yerleri açıkça işaretle ki ben sonradan kendi Telegram token ve chat_id’mi yazabileyim.

Lütfen:

Selenium ile element seçerken generic ve anlaşılır CSS/XPath örnekleri ver.

Gerekirse, Qmatic takvim yapısı için mantıklı varsayımlar yap; HTML class adları kesin değilse, yoruma satırında “burayı kendi sayfandaki class adına göre güncelle” gibi not düş.

Bana doğrudan çalıştırılabilir, eksiksiz bir Python dosyası ve yanında küçük bir requirements.txt üret.