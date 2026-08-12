# goster.me

**Gerekmeyen hiçbir şeyi goster.me.**

goster.me, internette görmek istediğimiz içerik ile o içeriğin etrafına yerleştirilen
reklam, öneri, otomatik oynatma, dikkat çekme mekanizmaları, karmaşık navigasyon ve
gereksiz sayfa kalabalığının aynı şey olmadığı fikrinden doğdu.

Bir videoyu izlemek, bir oyunu oynamak, bir ödevi yapmak veya bir etkinliği açmak
istediğimizde kaynak sitenin bütün arayüzünü de kabul etmek zorunda değiliz.
Özellikle çocuklarımız için.

> **İçeriğe erişmek, onu çevreleyen dikkat ekonomisini kabul etmek değildir.**

Bu yüzden alan adı aynı zamanda ürünün mesajıdır:

- Bana reklam **goster.me**.
- Çocuğuma dikkat dağıtıcı şeyler **goster.me**.
- Karmakarışık bir sayfa **goster.me**.
- Videoyu göster. YouTube'u **goster.me**.
- İçeriği göster. Gerisini **goster.me**.

## Ne yapar?

Kullanıcı normal bir web bağlantısını goster.me'ye verir. Resolver ve adapter katmanı
bağlantının gerçekten istenen bölümünü bulur; renderer mümkün olduğunda yalnızca bu
içeriği gösterir.

```text
uzun / karmaşık kaynak URL
        |
        v
resolver + content adapter
        |
        +-- YouTube --------> contained video
        +-- Wordwall -------> clean embed
        +-- native exercise -> isolated application
        +-- collection -----> clean activity list
        +-- unknown --------> fail closed / review
        |
        v
goster.me/k7p3mx
```

Public kısa bağlantılar özellikle başka bir cihazda açılabilsin diye insan tarafından
okunabilir ve söylenebilir olmalıdır. Kısa kod alfabesi `0/O`, `1/I/l`, `2/Z`, `5/S`
gibi kolay karışan karakterleri kullanmaz.

Varsayılan kısa bağlantı ömrü şu anda 14 gündür. Bu süre deployment ortamında
`GOSTER_LINK_TTL_SECONDS` ile değiştirilebilir. Kısa bağlantılar SQLite içinde kalıcı
olarak saklanır; web servisinin yeniden başlaması bağlantıları kaybettirmez.

## Tasarım ilkeleri

- Gerçek içeriği öne çıkar; goster.me arayüzünün kendisi dikkat istememeli.
- Kaynak sitenin gereksiz navigasyonunu çocuğa veya son kullanıcıya taşıma.
- Etkileşimli uygulamaları, JavaScript'leri orijinal DOM'a bağlıysa bozma.
- Mümkün olduğunda temiz provider embed'lerini tercih et.
- Geniş ve kırılgan scraping yerine açık adapter fingerprint'leri kullan.
- Güvenli biçimde tanımlanamayan içerikte fail closed davran.
- Media acquisition ile presentation katmanını ayrı tut.
- Gerçek öğretmen/veli URL corpus'unu compatibility benchmark olarak kullan.
- Paylaşılan temiz görünümde `goster.me`, geri, kopyala ve paylaş kontrolleri görünür
  ve tutarlı olmalı.

## Kısa bağlantı modeli

Public ürünün canonical biçimi:

```text
https://goster.me/k7p3mx
```

Eski prototipteki `/g/<id>` rotası geçiş dönemi için compatibility route olarak
korunabilir, ancak kullanıcıya gösterilen/kopyalanan URL kısa canonical adres olmalıdır.

Kısa bağlantı store'u `shortlinks.py` içindedir. Varsayılan veritabanı:

```text
/var/lib/goster.me/goster.sqlite3
```

Değiştirmek için:

```bash
export GOSTER_DATABASE=/path/to/goster.sqlite3
```

## Public uygulama

`product_app.py`, mevcut adapter/renderer kodunu yeniden yazmadan public ürün
kabuğunu ekler:

- manifesto odaklı minimal landing page;
- her page load'da sakin biçimde seçilen tek örnek slogan;
- persistent human-friendly kısa URL;
- canonical `/<short-code>` route;
- branded viewer toolbar;
- copy/share davranışı;
- expired-link ekranı.

Çalıştırmak için:

```bash
python3 product_app.py
```

Varsayılan bind ayarları environment ile değiştirilebilir:

```bash
GOSTER_HOST=127.0.0.1 GOSTER_PORT=8090 python3 product_app.py
```

## Childsafe ve Childsafe Inbox

Projenin kökeni çocuklar için daha kontrollü bir web deneyimi oluşturma ihtiyacıdır.
Bu kullanım alanı **Childsafe** olarak devam eder.

**Childsafe Inbox** ise ebeveynin/öğretmenin paylaştığı bağlantıları yerel medya ve
Jellyfin iş akışına alan özel ingestion aracıdır. Public goster.me ürünü bununla aynı
adapter bilgisini paylaşabilir, ancak yalnızca Jellyfin veya yalnızca çocuk içeriğiyle
sınırlı değildir.

## Render modları

### `embed`

Kaynakta zaten temiz bir provider URL varsa yalnızca etkinlik embed edilir.

```text
source page
    -> adapter discovers provider URL
    -> goster.me embeds only the activity
```

### `isolate`

Interactive uygulama kaynak sayfanın kendi DOM/JavaScript yapısına bağlıysa HTML'i
parçalamak yerine uygulamanın DOM root'u görünür bırakılır, sayfanın geri kalanı
izole edilir.

```text
source page
    -> adapter identifies application fingerprint
    -> selector is returned
    -> renderer hides unrelated page content
```

## Mevcut adapter aileleri

Proof of concept bugün şu içerik ailelerini kapsar:

- YouTube;
- Wordwall embed'leri;
- eğitim sitelerine gömülmüş Wordwall etkinlikleri;
- TestSaati Zombify quiz'leri;
- İlkokul Akademi native interactive exercises;
- İlkokul Akademi trusted GitHub Pages exercise embed'leri;
- gerçek URL corpus'undan eklenen diğer kontrollü eğitim sitesi adapter'ları.

Yeni provider'lar gerçek kullanımda görülen URL'lere göre eklenir.

## Önemli dosyalar

`product_app.py`
: Public goster.me ürün kabuğu ve canonical short-link route'ları.

`public_app.py`
: Mevcut public renderer ve adapter entegrasyonu.

`shortlinks.py`
: SQLite persistent short-link store, human-friendly code generation ve TTL.

`app.py`
: Childsafe Inbox web service.

`adapters.py`
: URL matching, content resolution ve adapter implementations.

`test-adapter`
: Tek URL resolve/inspection aracı.

`analyze-corpus`
: WhatsApp/chat URL corpus'unu bütün adapter'larla analiz eder.

## Test

Short-link davranışı yalnızca Python standard library kullanılarak test edilebilir:

```bash
python3 -m unittest -v test_shortlinks.py
```

Adapter geliştirmede temsilî URL'leri önce `test-adapter` ile kontrol edin; milestone
öncesinde tam corpus regression çalıştırın.

## Mahremiyet odaklı ürün ölçümü

goster.me üçüncü taraf analytics JavaScript'i, cookie, ham IP adresi, User-Agent,
referrer veya cihaz parmak izi saklamaz. Ürünün çalışıp çalışmadığını anlamak için
izinli olay adları ile provider, adapter, render mode ve doğrulanmış kampanya etiketi
kaydedilir. Tekrarları yaklaşık saymak ve operatör testlerini filtrelemek için IP
adresinden anahtarlı, günlük değişen bir `visitor_tag` üretilir. Bu etiket günler
arasında kullanıcı takibi yapmaz; yine de anonim veri olarak değil, kısa ömürlü
pseudonymous ölçüm verisi olarak ele alınır. Kaynak URL analytics tablosuna yazılmaz.

Veli grubu duyurusu için kullanılacak kampanya bağlantısı:

```text
https://goster.me/?from=veli-whatsapp-2026-08
```

Son 24 saatin raporu:

```bash
tools/goster analytics --since-hours 24
tools/goster analytics --since-milestone first-parent-whatsapp-announcement
tools/goster analytics --since-hours 24 --exclude-current-ssh-client
```

`--exclude-current-ssh-client`, SSH istemci adresi ile web erişim adresi aynıysa
operatör olaylarını rapordan çıkarır. VPN, mobil bağlantı veya değişen IP durumunda
`--exclude-ip ADDRESS` açıkça verilebilir. Filtre yalnızca visitor tag özelliği
deploy edildikten sonra kaydedilen olaylara uygulanabilir.

Visitor tag üretimi için `/etc/goster.me/gosterme.env` içinde en az 32 karakterlik,
ayrı bir `GOSTER_ANALYTICS_KEY` bulunmalıdır. Anahtar yoksa ölçüm çalışmaya devam
eder fakat olaylar visitor tag olmadan kaydedilir.

Ham analytics olayları varsayılan olarak 30 gün tutulur ve mevcut
`gosterme-storage-maintenance.timer` tarafından temizlenir. Süre
`GOSTER_ANALYTICS_RETENTION_SECONDS` ile değiştirilebilir.

Desteklenmeyen fakat geçerli URL denemeleri ayrı bir adapter backlog’unda tutulur.
Query string, fragment ve ziyaretçi bilgisi saklanmaz; muhtemel kimlik/token path
parçaları maskelenir. Aynı host/path hedefi tek satırda sayaç olarak güncellenir:

```bash
tools/goster unsupported list
tools/goster unsupported purge
```

Bu kayıtlar varsayılan olarak son görülmelerinden 30 gün sonra silinir.

## Özel geri bildirim

Ana sayfadaki **İletişim** bağlantısı, GitHub hesabı gerektirmeyen yerel bir mesaj
formu açar. Mesajlar herkese açık değildir ve yalnızca proje yöneticisinin CLI
üzerinden okuyabildiği SQLite tablosunda tutulur. Form ad, e-posta, telefon, IP,
User-Agent veya referrer istemez ve saklamaz. Kullanıcıdan çocuk adı veya başka
kişisel bilgi yazmaması açıkça istenir.

Okunmamış mesajları listelemek ve bir mesajı incelendi olarak işaretlemek için:

```bash
tools/goster feedback list
tools/goster feedback ack <receipt>
tools/goster feedback notify
```

Yeni mesajlar `gosterme-feedback-telegram.timer` ile yaklaşık 30 dakikada bir
Telegram’a iletilebilir. Başarılı teslim işaretlenmeden mesaj kuyruktan çıkarılmaz;
başarısız teslim bir sonraki çalıştırmada yeniden denenir. Telegram sınırını aşan
mesajlar bildirimde kısaltılır, tam metin SQLite ve operator CLI’da kalır. Bot token
ve hedef chat ID yalnızca `/etc/goster.me/gosterme.env` içindeki
`GOSTER_TELEGRAM_BOT_TOKEN` ve `GOSTER_TELEGRAM_CHAT_ID` değerlerinden okunur.

Mesajlar varsayılan olarak 90 gün sonra storage maintenance sırasında silinir.
Form, bellek içi rate limiting, form boyutu sınırı, alan allowlist'i, same-origin
kontrolü ve görünmez spam alanı ile korunur.

## Güvenlik yaklaşımı

goster.me unrestricted web proxy değildir. Temel yaklaşım **content minimization**dır:
kullanıcının istediği içeriği mümkün olduğunca korurken kaynak platformun gereksiz
arayüzünü, yönlendirmelerini ve dikkat çekme yüzeylerini taşımamak.

Unknown veya güvenli biçimde çözülemeyen içerik kontrollü bir fallback ya da uygun
adapter geliştirilene kadar unresolved kalmalıdır.

Public deployment için authentication, abuse/rate limiting, storage cleanup ve
provider-specific security politikaları ayrıca değerlendirilmelidir.

---

English documentation: [README.en.md](README.en.md)
