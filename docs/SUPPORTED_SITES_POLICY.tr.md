# Desteklenen Siteler ve Entegrasyon Politikası

Bu belge, goster.me'nin hangi sitelerle teknik olarak çalıştığını nasıl ifade ettiğimizi ve yeni destek, uyumluluk sorunu veya çıkarılma taleplerini nasıl ele aldığımızı açıklar.

Türkçe bu projenin birincil ürün ve politika dilidir. Aynı bilginin İngilizce sürümü `SUPPORTED_SITES_POLICY.md` dosyasında bulunur.

## "Destekleniyor" ne demek?

Bir sitenin goster.me tarafından **destekleniyor** olarak listelenmesi yalnızca teknik uyumluluğu ifade eder.

Bu ifade ortaklık, sponsorluk, resmi onay, ticari ilişki, içerik sahipliği veya site sahibi adına hareket etme anlamına gelmez.

goster.me'nin amacı, kullanıcı tarafından özellikle talep edilen içeriği daha sade ve dikkat dağıtıcı unsurları azaltılmış bir görünümde sunmaktır.

## Desteklenen siteler listesi

Desteklenen siteler ve sağlayıcılar için tek bir canonical katalog oluşturulacaktır. Bu katalog mümkün olduğunca adapter registry ile aynı kaynaktan üretilecek ve hem codebase hem public site tarafından kullanılacaktır.

Liste, gerektiği ölçüde site/sağlayıcı adı, destek türü (`embed`, `isolate` vb.), bilinen önemli sınırlamalar ve destek durumunu gösterebilir. Public liste gereksiz altyapı veya güvenlik ayrıntıları yayımlamayacaktır.

## Yeni bir site için destek istemek

Bir kullanıcı, katkıcı veya site sahibi yeni bir site ya da içerik türü için destek talep edebilir. İlk aşamada bunun için GitHub Issue açılması yeterlidir.

Talepte mümkünse örnek URL, gösterilmesi beklenen asıl içerik, mevcut durumda neyin çalışmadığı veya gereksiz olduğu ve gerekiyorsa kısa teknik not bulunmalıdır.

Her talebin kabul edileceği garanti edilmez. Değerlendirmede güvenlik, teknik uygulanabilirlik, sürdürülebilirlik, içerik kaynağının davranışı ve goster.me'nin içerik-minimizasyonu amacı dikkate alınır.

## Mevcut bir entegrasyonla ilgili sorun bildirmek

Şunlar için GitHub Issue açılabilir: içerik yanlış veya eksik gösteriliyorsa, gerekli bir kontrol çalışmıyorsa, gereğinden fazla kaynak sayfa içeriği kalıyorsa, dışarı yönlendiren bir bağlantı kaçıyorsa, reklam/takip bileşeni çalışmaya devam ediyorsa veya site değişikliği nedeniyle adapter bozulduysa.

Mümkünse örnek URL ve gözlenen davranış eklenmelidir.

## Site sahibi olarak çıkarılma talep etmek

Bir site sahibi veya yetkili temsilci, sitesinin goster.me tarafından işlenmesini istemiyorsa **çıkarılma / exclusion talebi** açabilir. İlk aşamada bu talep GitHub Issues üzerinden yapılabilir.

Talep gereksiz bürokrasi yaratmadan ele alınacaktır. Talebin gerçekten site sahibi veya yetkili bir temsilciden geldiğinin anlaşılması gerektiğinde makul bir doğrulama istenebilir.

Doğrulanmış çıkarılma taleplerini mümkün olduğunca hızlı ve şeffaf biçimde ele almayı hedefliyoruz. Çıkarılma işlemi gerektiğinde ilgili domainin adapter eşleşmesinden kaldırılmasını, belirli bir içerik ailesinin devre dışı bırakılmasını, destek kataloğunun ve ilgili test/dokümantasyonun güncellenmesini kapsayabilir.

Güvenlik ve kötüye kullanım önleme mekanizmaları korunur.

## Yeniden eklenme veya kapsam değişikliği

Daha önce çıkarılmış bir site yeniden desteklenmek isterse veya yalnız belirli içerik türlerinin desteklenmesini isterse yeni bir Issue ile kapsam görüşülebilir. Bu kararlar da teknik uygulanabilirlik, güvenlik ve sürdürülebilirlik kriterleriyle değerlendirilir.

## Şeffaflık ve takip

Destek, uyumluluk ve çıkarılma taleplerinin mümkün olduğunca GitHub üzerinde izlenebilir olmasını tercih ediyoruz. Böylece talebin ne olduğu, hangi kararın alındığı, hangi kod değişikliğinin yapıldığı ve hangi doğrulamanın gerçekleştirildiği sonradan anlaşılabilir.

Güvenlik açığı, kişisel veri veya başka hassas bilgi içeren konular public Issue içinde paylaşılmamalıdır. Bu tür durumlar için uygun private bildirim yolu ayrıca tanımlanacaktır.

## Dil politikası

Türkçe, goster.me'nin başlangıç kullanıcı kitlesi için birincil dildir. Public ürün ve politika metinlerinde Türkçe sürüm önce tasarlanır.

İngilizce sürüm ikincil sunum önceliğine sahiptir ancak içerik olarak eksik olmamalıdır. Türkçe bilmeyen kullanıcı, katkıcı veya site sahibi aynı süreçleri, seçenekleri ve temel hakları İngilizce olarak anlayabilmelidir.

İki dil arasında maddi bir politika farkı oluşmaması hedeflenir.

## Uygulama notu

Bu belge policy contract'ını tanımlar. Desteklenen sitelerin gerçek listesi, modular adapter refactor ile birlikte oluşturulacak canonical adapter/provider kataloğundan üretilecektir.

Takip: GitHub Issue #11 — `Publish supported-sites catalog and inclusion/exclusion policy`.
