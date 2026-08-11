# goster.me Güvenlik Mimarisi

Bu belge, public `goster.me` servisinin güvenlik modelini ve korunması gereken mimari kuralları tanımlar. Adapter ve rendering kodları ileride refactor edilse bile burada tarif edilen güvenlik sınırlarının geçerli kalması amaçlanır.

## Önce teknik olmayan kısa açıklama

`goster.me`, kullanıcının verdiği bir web adresindeki eğitim videosunu, oyunu veya etkinliği mümkün olduğunca temiz ve dikkat dağıtmayan bir biçimde göstermeye çalışır. Bu işin zor tarafı şudur: kaynak site bizim kontrolümüzde değildir. Reklam, takip kodu, üçüncü taraf JavaScript veya beklenmeyen davranışlar içerebilir.

Bu nedenle sistem iki farklı yaklaşım kullanır:

- Kaynak sitenin zaten temiz bir embed sürümü varsa, örneğin Wordwall veya YouTube embed'i, doğrudan onu kullanırız.
- Temiz embed yoksa ve etkinlik kaynak sayfanın kendi HTML/JavaScript'i içinde çalışıyorsa, bu kodu ana `goster.me` alanında çalıştırmayız. Ayrı bir güvenlik alanına göndeririz.

Bu ikinci alan sandbox'tır. Mantıksal olarak şu şekilde düşünülebilir:

```text
Kullanıcı
   |
   v
goster.me
   |
   |  güvenli ürün arayüzü, kısa link, QR, paylaşım
   |
   +---------------------------+
                               |
                               v
                           s.goster.me
                               |
                               v
                     üçüncü taraf HTML / JavaScript
```

Amaç şudur: kaynak sitedeki JavaScript kötü niyetli, bozuk veya aşırı meraklı olsa bile `goster.me`'nin kendi cookie'lerine, local storage'ına, DOM'una veya uygulama yetkilerine sahip olmasın.

Sandbox'ın adının gizli olması bir güvenlik önlemi değildir. `s.goster.me` kısa ve nötr bir isimdir; gerçek güvenlik ayrı origin, kısa ömürlü imzalı erişim URL'si, browser sandbox kuralları, CSP, merkezi URL doğrulama ve read-only storage gibi katmanlardan gelir.

Basit güvenlik prensibimiz şudur:

```text
Temiz embed varsa      -> temiz embed kullan
Embed yoksa            -> ayrı sandbox origin'de çalıştır
İçeriği tanımıyorsak   -> çalıştırma, fail closed
```

## Güvenlik hedefleri

Servis, güvenilmeyen kullanıcılar tarafından verilen URL'leri kabul eder ve üçüncü taraf sitelerden içerik çeker. Temel hedefler şunlardır:

1. Gönderilen bir URL'nin `goster.me`'yi SSRF proxy'sine dönüştürmesine izin vermemek.
2. Üçüncü taraf HTML veya JavaScript'i hiçbir zaman ana `goster.me` origin yetkileriyle çalıştırmamak.
3. Kaynak sayfayı çalıştırmak yerine mümkün olduğunca temiz provider embed'lerini tercih etmek.
4. Kaynak sayfanın çalıştırılması zorunluysa bunu yalnızca ayrı sandbox origin ve browser sandbox kısıtları altında yapmak.
5. Bilinmeyen veya desteklenmeyen içerikte fail closed davranmak.
6. Storage ve process kaynak tüketimini sınırlandırmak.
7. Gereksiz analytics, reklam, server version ve uygulama bilgisini dışarı vermemek.

## Güven sınırları

```text
Internet / kullanıcı tarafından verilen URL
        |
        v
+-------------------------+
| URL + redirect security |
| security.py             |
+-------------------------+
        |
        v
+-------------------------+
| adapters / discovery    |
| yalnızca sınıflandırma  |
+-------------------------+
        |
        +---------------- clean embed ----------------+
        |                                              |
        v                                              v
 render_mode=isolate                            render_mode=embed
        |                                              |
        v                                              v
+-------------------------+                    primary shell
| short-link database     |                           |
+-------------------------+                           v
        |                                         provider iframe
        v
primary `goster.me/<code>`
        |
        | kısa ömürlü imzalı capability URL
        v
`s.goster.me/v/<code>?exp=...&sig=...`
        |
        v
browser sandbox içinde third-party HTML/JS
```

Ayrı sandbox origin kozmetik bir subdomain değil, gerçek bir güvenlik sınırıdır.

## URL ve network güvenliği

`security.py`, URL ve network doğrulamasının sahibi olmalıdır. Adapter'lar bunun daha zayıf paralel bir sürümünü uygulamamalıdır.

Mevcut kurallar:

- Yalnızca HTTP ve HTTPS.
- Hostname zorunlu.
- URL içinde kullanıcı adı/parola bilgisi reddedilir.
- Ham IPv4/IPv6 literal adresleri reddedilir.
- Standard dışı portlar reddedilir.
- URL uzunluğu sınırlandırılır.
- Redirect hedefleri açılmadan önce doğrulanır.
- Adapter fetch işlemleri explicit host allowlist kullanır.
- YouTube video ID'leri sıkı biçimde doğrulanır.

Bilinmeyen içerik, remote HTML çalıştırmaya düşmek yerine generic public error ile sonuçlanmalıdır.

## Rendering politikası

Rendering modları bilinçli olarak az ve explicit tutulur.

### Temiz embed'ler

Bir provider temiz embed URL sunuyorsa source-page isolation yerine bu kullanılmalıdır. YouTube ve Wordwall bunun örnekleridir.

### İzole native içerik

Bazı eğitim siteleri etkinliği doğrudan kaynak sayfanın içinde çalıştırır ve ayrı bir temiz embed sağlamaz. Böyle bir içerik adapter tarafından şu şekilde sınıflandırılabilir:

```text
render_mode = isolate
selector = <bilinen activity root>
```

Adapter yalnızca içeriği ve activity root'u tanımlar. Browser'a ek yetki vermez.

## Sandbox origin

Üçüncü taraf source HTML yalnızca `s.goster.me` üzerinden servis edilir; ana origin üzerinden asla servis edilmez.

Sandbox servisi:

- Caddy arkasında yalnızca loopback'e bind olur;
- short-link SQLite veritabanını read-only açar;
- yalnızca canlı ve `render_mode=isolate` olan kayıtları servis eder;
- access counter artırmaz ve storage değiştirmez;
- source HTML'i primary service ile aynı redirect/host doğrulamasından geçirerek çeker;
- browser parse etmeden önce bilinen analytics/reklam execution bloklarını temizler;
- `Cache-Control: no-store` döner;
- Python version bilgisini gizler;
- genel resolver, static-file veya write endpoint sunmaz.

### İmzalı capability URL'leri

Şu tip çıplak bir URL sandbox içeriğine erişmek için yeterli değildir:

```text
https://s.goster.me/v/abc346
```

Primary service kısa ömürlü HMAC-SHA256 imzalı bir capability URL üretir:

```text
https://s.goster.me/v/abc346?exp=<unix-time>&sig=<hmac>
```

İmza short code ve expiry time'a bağlıdır. Sandbox; eksik, hatalı, süresi geçmiş, duplicate veya beklenmeyen query parametrelerini reddeder. Capability ömrü en fazla on dakikadır.

Her iki servis aynı secret'ı kullanır:

```text
GOSTER_SANDBOX_SIGNING_KEY
```

Key en az 32 byte olmalı ve repoya commit edilmemelidir. Primary service isolate URL imzalayamıyorsa fail closed davranmalıdır.

İmzalı URL bir bearer capability'dir. Geçerli URL'yi elde eden biri süresi dolana kadar tekrar kullanabilir. Amaç end-user authentication yapmak değil; çıplak sandbox route'larının tahmin edilmesini, enumerate edilmesini ve yanlışlıkla public capability olmasını engellemektir.

### Browser seviyesinde sandbox

Primary sayfa sandbox içeriğini iframe ile gömer ve özellikle `allow-same-origin` iznini vermez:

```text
sandbox="allow-scripts allow-modals allow-pointer-lock allow-presentation"
```

Ayrı bir security review yapılmadan `allow-same-origin` eklenmemelidir.

Sandbox response ayrıca CSP sandbox directive'i döner ve framing'i primary origin ile sınırlar:

```text
frame-ancestors https://goster.me
sandbox allow-scripts allow-modals allow-pointer-lock allow-presentation
object-src 'none'
form-action 'none'
```

Sandbox `X-Frame-Options: DENY` göndermemelidir; çünkü `goster.me` tarafından cross-origin iframe olarak gömülmesi meşru kullanımın parçasıdır.

Browser `Sec-Fetch-Dest` gönderiyorsa sandbox yalnızca `iframe` değerini kabul eder. Bu normal top-level browser navigation'ını engeller. Bu header yalnızca defense-in-depth katmanıdır; HTTP client bunu taklit edebileceğinden esas erişim kontrolü HMAC capability'dir.

## Primary-origin politikası

Primary origin ürün UI'sini, kısa linkleri, share/QR kontrollerini ve clean embed shell'lerini barındırır. Üçüncü taraf source HTML veya JavaScript hiçbir zaman same-origin içerik olarak buradan servis edilmemelidir.

Primary service security header'ları döner; Caddy public CSP'yi uygular ve backend kimliği açığa çıkaran header'ları kaldırır.

Mevcut primary CSP geçiş niteliğindedir çünkü legacy rendering hâlâ inline script/style içerir. İleride bunlar external file'a taşınmalı veya nonce/hash kullanılmalı; böylece `unsafe-inline` kaldırılmalıdır.

## Privacy filtering

Origin isolation ana origin'i korur, fakat üçüncü taraf analytics ve reklam kodları ürün amacı için gereksizdir. İzole HTML browser'a ulaşmadan önce şu bilinen execution blokları kaldırılır:

- Google Tag Manager
- Google Analytics
- AdSense / Google Syndication
- DoubleClick

Bu bir hygiene/privacy katmanıdır; ana güvenlik sınırı değildir. Filtering genişletilse bile browser sandbox ve origin separation zorunlu kalır.

## Storage kontrolleri

Short-link storage defense-in-depth limitleri kullanır:

- maksimum row sayısı;
- LRU trimming için daha düşük target row sayısı;
- payload başına UTF-8 byte limiti;
- her application SQLite connection üzerinde uygulanan `max_page_count`;
- expiry ve trimming için periodic maintenance.

SQLite `max_page_count` connection/runtime guard'dır. Persistent database header ayarı değildir ve OS-level filesystem quota yerine geçmez.

Maintenance sırasında otomatik `VACUUM` bilinçli olarak yapılmaz; çünkü geçici olarak disk ve I/O tüketimini artırabilir.

## Process isolation ve resource limitleri

Systemd unit'leri loopback listener ve restrictive service ayarları kullanır. Bunlar arasında:

- dedicated non-root `gosterme` user;
- `NoNewPrivileges=true`;
- `ProtectSystem=strict`;
- `ProtectHome=true`;
- capability bounding set'in kaldırılması;
- private temporary/device namespace'leri;
- kernel/control-group korumaları;
- address-family restriction;
- memory, task, file-descriptor ve CPU limitleri.

Sandbox unit `/var/lib/goster.me` dizisine yalnızca read-only erişebilmelidir.

## Reverse proxy / DNS

Public TLS Caddy üzerinde sonlanır. Application listener'ları `127.0.0.1` üzerinde kalır.

Beklenen public routing:

```text
goster.me    -> Caddy -> 127.0.0.1:8090
s.goster.me  -> Caddy -> 127.0.0.1:8092
```

Internet'ten yalnızca Caddy erişilebilir olmalıdır. 8090/8092 portları firewall/security-group seviyesinde public olmamalıdır.

`s.goster.me` adının kısa veya daha az açıklayıcı olması security boundary değildir; aşağıdaki güvenlik kontrolleri isimden bağımsız olarak zorunludur.

## Adapter refactor'larında korunması gereken güvenlik invariants

Adapter modularization şu kuralları korumalıdır:

1. Adapter'lar içeriği classify/discover eder; centralized URL validation'ı bypass etmez.
2. Clean embed source-page isolation'a tercih edilir.
3. Bilinmeyen içerik fail closed olur.
4. `render_mode=isolate` yalnızca dedicated sandbox origin üzerinden render edilir.
5. Third-party HTML/JS hiçbir zaman `goster.me` üzerinden same-origin servis edilmez.
6. Sandbox iframe privileges hiçbir zaman `allow-same-origin` içermez.
7. Sandbox kayıtları read-only olmalı ve canlı isolate kayıtları olmalıdır.
8. Çıplak sandbox short code public capability değildir; kısa ömürlü geçerli signature zorunludur.
9. Site adapter'ları eklenmeden, silinmeden veya yeniden organize edilmeden önce security testlerinin tamamı green olmalıdır.

## Deployment checklist

Sandbox public edilmeden önce:

1. Güçlü signing key üret:

   ```bash
   openssl rand -hex 32
   ```

2. Yalnızca `/etc/goster.me/gosterme.env` içine koy:

   ```text
   GOSTER_SANDBOX_SIGNING_KEY=<generated-secret>
   GOSTER_SANDBOX_ORIGIN=https://s.goster.me
   ```

3. Main ve sandbox servislerinin aynı environment file'ı kullandığını doğrula.
4. 8090 ve 8092'nin yalnızca loopback üzerinde dinlediğini doğrula.
5. Main service entrypoint değiştirilmeden önce Caddy config'i validate edip reload et.
6. Çıplak sandbox `/v/<code>` isteğinin 404 verdiğini doğrula.
7. Invalid/expired signature'ın 404 verdiğini doğrula.
8. Signed iframe URL'nin 200 verdiğini doğrula.
9. Browser top-level navigation isteğinin `Sec-Fetch-Dest: document` olduğunda reddedildiğini doğrula.
10. CSP içinde `allow-same-origin` sandbox privilege olmadığını doğrula.
11. Bilinen reklam/analytics script URL'lerinin isolated output içinde bulunmadığını doğrula.
12. Full regression suite'i çalıştır.

## Bilinen sınırlamalar ve sonraki işler

- Signed sandbox URL'leri kısa expiry süresi boyunca replay edilebilir.
- Sandbox CSP broad HTTPS dependency'lere izin verir; çünkü native eğitim uygulamaları external asset kullanabilir. İleride adapter başına dependency allowlist ile sıkılaştırılabilir.
- Sandbox içindeki legacy third-party native app'ler için `unsafe-inline` / `unsafe-eval` gerekebilir. Bunlar yalnızca document ayrı origin'de ve browser-sandboxed olduğu için kabul edilebilir.
- Primary CSP, UI script/style externalized veya nonce/hash tabanlı olduktan sonra `unsafe-inline`'ı kaldırmalıdır.
- Storage byte limitleri filesystem quota değil, application/SQLite kontrolleridir.
