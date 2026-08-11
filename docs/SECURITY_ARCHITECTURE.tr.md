# goster.me Güvenlik Mimarisi

Bu belge, public `goster.me` servisinin güvenlik modelini maintainer ve dışarıdan inceleyen kişiler için yeterli olacak seviyede anlatır. Operasyonel secret'lar, exact deployment değerleri, internal route'lar, süre parametreleri ve host'a özgü ayrıntılar bilinçli olarak burada yer almaz.

## Önce teknik olmayan kısa açıklama

`goster.me`, kullanıcının verdiği bir web adresindeki eğitim videosunu, oyunu veya etkinliği mümkün olduğunca temiz ve dikkat dağıtmayan biçimde göstermeye çalışır. Kaynak site bizim kontrolümüzde olmadığı için reklam, takip kodu, bozuk JavaScript veya beklenmeyen davranış içerebilir.

Bu yüzden sistem iki temel yol kullanır:

```text
Temiz embed varsa      -> temiz embed kullan
Embed yoksa            -> ayrı güvenlik alanında çalıştır
İçeriği tanımıyorsak   -> çalıştırma, fail closed
```

Kaynak sayfanın kendi HTML/JavaScript'ini çalıştırmak gerekiyorsa bu kod ana `goster.me` alanında çalıştırılmaz. Ayrı bir origin ve browser sandbox içinde tutulur. Böylece üçüncü taraf kodu ana uygulamanın cookie, storage, DOM ve origin yetkilerini alamaz.

Bu ayrı origin'in adının kısa veya daha az açıklayıcı olması güvenlik sağlamaz. Güvenlik; origin ayrımı, imzalı ve kısa ömürlü erişim, browser sandbox kuralları, CSP, merkezi URL doğrulama, read-only storage ve process kısıtlarının birlikte uygulanmasından gelir.

## Güvenlik hedefleri

`goster.me`, kullanıcı tarafından verilen URL'leri kabul eder ve bazı durumlarda üçüncü taraf içerik çeker. Bu nedenle URL ve remote içerik güvenilmeyen veri olarak kabul edilir.

Temel hedefler:

- server-side request abuse'u engellemek;
- üçüncü taraf HTML/JavaScript'i hiçbir zaman ana `goster.me` origin yetkileriyle çalıştırmamak;
- mümkün olduğunda provider'ın temiz embed'ini kullanmak;
- temiz embed yoksa native uygulamayı ayrı güvenlik origin'inde izole etmek;
- bilinmeyen ve desteklenmeyen içerikte fail closed davranmak;
- storage ve process kaynak tüketimini sınırlandırmak;
- tracking, reklam ve gereksiz bilgi ifşasını azaltmak.

## Yüksek seviyeli güven modeli

```text
kullanıcı URL'si
   |
   v
merkezi URL / redirect doğrulama
   |
   v
içerik sınıflandırma
   |
   +---- temiz provider embed ----> ana ürün shell'i
   |
   +---- native sayfa içeriği ----> ayrı origin + browser sandbox
```

Ayrı origin kozmetik bir subdomain değil, güvenlik sınırıdır. Hostname tek başına authorization mekanizması değildir.

## URL ve network kontrolleri

Tüm remote fetch işlemleri merkezi doğrulamadan geçmelidir. Site adapter'ları daha zayıf paralel fetch yolları oluşturmamalıdır.

Uygulama scheme, host, redirect ve hedef doğrulaması yapar ve explicit source allowlist kullanır. Desteklenmeyen içerik arbitrary remote HTML execution'a fallback etmez.

## Rendering politikası

İki tercih edilen rendering yolu vardır:

1. **Clean embed** — provider destekliyorsa doğrudan temiz embed kullanılır.
2. **Isolated native content** — etkinlik yalnızca kaynak sayfa içinde çalışıyorsa içerik isolate olarak sınıflandırılır ve dedicated isolation service üzerinden gösterilir.

Adapter'ın görevi içeriği sınıflandırmak ve ilgili activity root'u tanımaktır. Adapter browser'a ek yetki vermez.

## Isolation sınırı

Üçüncü taraf source HTML hiçbir zaman primary application'dan same-origin içerik olarak servis edilmez.

Isolation service bilinçli olarak dar tutulur:

- yalnızca önceden sınıflandırılmış isolate içeriği servis eder;
- short-link storage'a read-only erişir;
- application data oluşturamaz veya değiştiremez;
- merkezi URL ve redirect doğrulama yolunu tekrar kullanır;
- mümkün olduğunda bilinen reklam ve analytics execution'ını kaldırır;
- yalnızca primary product origin tarafından frame edilmesi amaçlanır;
- genel resolver veya arbitrary file-serving interface sunmaz.

Isolation içeriğine erişim, primary service tarafından üretilen kısa ömürlü imzalı capability gerektirir. Bu mekanizma end-user authentication yerine geçmez.

## Browser sandboxing

Isolated document ayrı origin'de olmasının yanında browser sandbox kısıtları içinde de çalışır.

Kritik invariant şudur: üçüncü taraf isolated content primary application ile same-origin authority elde etmemelidir. Bu sınırı zayıflatan değişiklikler ayrı security review gerektirir.

Content Security Policy ve ilgili browser kontrolleri framing, form, plugin ve diğer yetkileri ayrıca sınırlar.

## Privacy ve bilgi minimizasyonu

Sistem mümkün olduğunda isolated content içindeki bilinen reklam ve analytics execution'ını kaldırır. Public response'lar da gereksiz backend implementation ve version bilgisini dışarı vermemeye çalışır.

Bunlar defense-in-depth ve privacy katmanlarıdır; origin separation veya browser sandbox yerine geçmez.

## Storage ve process kontrolleri

Application storage row, payload ve database-growth limitleriyle sınırlandırılır; expired data için periodic maintenance uygulanır.

Process'ler non-root service identity ile çalışır ve systemd üzerinden CPU, memory, task ve file-descriptor limitleri ile ek hardening uygulanır. Public traffic reverse proxy üzerinde sonlanır; application listener'ları doğrudan Internet'e açılmamalıdır.

## Adapter refactor'larında korunması gereken invariants

İleride yapılacak adapter modularization şu kuralları korumalıdır:

1. adapter'lar classify/discover eder ama centralized network validation'ı bypass etmez;
2. clean embed source-page isolation'a tercih edilir;
3. bilinmeyen içerik fail closed olur;
4. isolate içerik yalnızca dedicated isolation origin üzerinden render edilir;
5. third-party HTML/JavaScript primary origin yetkileriyle servis edilmez;
6. isolated browser content primary application ile same-origin privilege alamaz;
7. isolation service application storage'a karşı read-only kalır;
8. yalnızca isolated content identifier'ını bilmek erişim için yeterli değildir;
9. site adapter'ları eklenirken, silinirken veya yeniden organize edilirken security regression testleri green kalmalıdır.

## Deployment prensipleri

Production deployment sırasında en azından şunlar doğrulanmalıdır:

- primary ve isolation service aynı amaçlanan security configuration'ı kullanıyor;
- application listener'ları reverse proxy arkasında private kalıyor;
- doğrudan unsigned isolation access reddediliyor;
- signed isolate content yalnızca amaçlanan framing bağlamında çalışıyor;
- browser sandbox ve CSP restriction'ları aktif;
- desteklenen kaynaklarda reklam/analytics stripping devam ediyor;
- traffic switch öncesi full security regression suite geçiyor.

Exact production path'leri, secret'lar, port assignment'ları, signing formatı ve timing değerleri public architecture dokümanı yerine deployment configuration içinde tutulmalıdır.

## Bilinen sınırlamalar

Bazı legacy third-party uygulamalar isolated document içinde daha permissive script davranışı gerektirebilir. Bu yalnızca primary origin'den ayrıldıkları ve browser sandbox ile sınırlandıkları için kabul edilebilir.

Primary application CSP'si legacy inline asset'ler kaldırıldıkça daha da sıkılaştırılabilir. Storage limitleri application-level safeguard'dır; OS veya filesystem quota'nın yerini tutmaz.
