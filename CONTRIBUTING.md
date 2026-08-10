# goster.me'ye katkı

goster.me public arayüzünü bilinçli olarak küçük, hafif ve az bağımlılıklı tutar.
Amaç; tasarım, frontend ve adapter katkılarının, katkı sağlayan kişinin tüm
uygulamayı öğrenmesini gerektirmeden yapılabilmesidir.

İngilizce sürüm: [CONTRIBUTING.en.md](CONTRIBUTING.en.md)

## Public UI yapısı

- `static/product.css` — görsel tasarım, boşluklar, tipografi ve design token'ları
- `static/product.js` — kopyalama/paylaşma gibi küçük progressive-enhancement davranışları
- `product_app.py` — public route'lar, kısa bağlantılar, QR ve HTML yapısı
- `public_app.py` — olgunlaşmış içerik render davranışları
- `adapters.py` — kaynak tespiti ve gerçek içeriğin ayrıştırılması
- `shortlinks.py` — kalıcı kısa bağlantı deposu ve süre sonu yönetimi

## Tasarım ilkeleri

Arayüz, kaynak sitelere uyguladığımız içerik minimizasyonu yaklaşımını kendi
üzerinde de uygulamalıdır:

- chrome'dan önce içerik;
- mümkün olduğunca az hareket;
- amacı olmayan dekoratif UI eklememek;
- okunaklı tipografi ve rahat kontrast;
- mobile-first kontroller;
- semantic HTML ve klavye ile erişilebilir aksiyonlar;
- yalnızca görünüm için tracking veya üçüncü taraf asset kullanmamak;
- hareket eklendiğinde `prefers-reduced-motion` tercihine saygı göstermek.

Amaç bir SaaS landing page'i üretmek değil; sakin, anlaşılır ve güven veren bir
araç oluşturmaktır.

## Stil / CSS

`static/product.css` dosyasının başındaki CSS custom property'leri design token
olarak kullanın. Renk, boşluk, radius ve benzeri değerleri stylesheet'in farklı
yerlerine sabit değer olarak dağıtmak yerine mümkün olduğunca bu token'ları
değiştirin veya genişletin.

Bir CSS framework'ü zorunlu değildir. Bu bilinçli bir tercihtir: bir tasarımcı,
Python veya adapter mimarisini öğrenmeden tek bir normal CSS dosyasını değiştirerek
yeni bir görsel giydirme deneyebilmelidir.

## JavaScript

JavaScript mümkün olduğunca progressive enhancement olmalıdır. Ana içerik büyük
bir client-side bundle olmadan erişilebilir kalmalıdır.

Tarayıcıya özel API'lerin fallback'i olmalıdır. Özellikle local/LAN üzerinden
HTTP ile geliştirme ve test desteklenen bir akıştır; Clipboard ve Web Share gibi
secure-context gerektiren API'ler başarısız olduğunda arayüz sessizce bozulmamalıdır.

## Adapter katkıları

Adapter'lar projenin temel işlevidir. Yeni bir site veya içerik tipi eklerken:

1. gerçek kullanıcıdan gelen örnek URL'leri temel alın;
2. genel scraping yerine mümkün olduğunca açık fingerprint kullanın;
3. yanlış içerik göstermemek için fail-closed davranışı koruyun;
4. `test-adapter` ile temsilî URL'leri doğrulayın;
5. uygun olduğunda corpus analizini yeniden çalıştırın.

## Bağımlılıklar

Yeni bir dependency gerçekten bir problemi çözmelidir. Büyük uygulama framework'leri
yerine iyi tanımlanmış bir işi yapan küçük ve odaklı kütüphaneleri tercih edin.

## Testler

Bir değişiklik göndermeden önce en azından:

```sh
python -m unittest -v test_shortlinks.py
python -m py_compile product_app.py public_app.py adapters.py shortlinks.py
```

UI değişikliklerinde en az bir dar mobil viewport ve bir desktop viewport test edin.
Adapter değişikliklerinde ilgili gerçek URL örneklerini ayrıca doğrulayın.
