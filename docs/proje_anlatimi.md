# Hastane projesi, baştan sona

Bu metin, Graubünden pilotunun nereden başladığını, hangi verinin nereye gittiğini ve ekranda neyin durduğunu anlatır. Öğretmen için İngilizce not `docs/graubunden_report.md`, Almanca rapor `docs/graubunden_bericht.md` dosyasındadır. Bu dosya, yapılan işi anlamak içindir.

Sayılar 11 Kasım 2026 kopyası olan `data/pilot.sqlite` dosyasındandır. Ekran bu dosyayı okur.

## 1. Proje ne işe yarıyor

Amaç, İsviçre hastaneleri hakkında “bu sayı hangi resmi hücreden geldi, bu bölüm adı hangi sayfada yazıyor” diye geri dönülebilen bir bilgi grafı kurmaktır. Pilot, ana kantonu Graubünden olan 18 kuruluştur.

Bir cümlelik örnek: Kantonsspital Graubünden’in 2024 akut yatak sayısı 343’tür. Bu sayı kuruluşa aittir. Aynı kuruluşun Spital Walenstadt adlı sahası St. Gallen kantonundadır. Yatak, Walenstadt’a kopyalanmaz.

## 2. Büyük resim

Veri üç katmanda durur.

```text
Resmi dosya ve hastane sayfası
        |
        v
PostgreSQL          yüklemenin kaydı
        |
        v
data/pilot.sqlite   ekranın okuduğu kopya
        |
        v
Bellekteki RDF graf  ekran ve SPARQL bunu okur
        |
        v
Streamlit ekranı     http://localhost:8502
```

Yükleyici PostgreSQL’e yazar. Bölüm adları üç Spitalliste PDF’inden gelir. Resmi listesi yazılan kuruluşların sayfa bölüm iddiaları silindi. Kabul edilmiş iddia kalmadı. `data/pilot.sqlite` bu halin kopyasıdır. Ekran Docker açmadan bu dosyadan grafı kurar. Bu kopyanın GR projeksiyonu 25.241 üçlüdür: 538 aday iddia, 213 doğrulanmış iddia, 0 kabul edilmiş iddia. Doğrulanmış sayı BAG hücrelerini, üç listedeki bölümleri ve üç saha çıkarımını birlikte sayar. Graf elle çizilmez. Satır değişirse kopya yeniden alınır.

Üç tür kayıt vardır. Karışmamaları işin özüdür.

| Kayıt | Örnek | Durum |
|---|---|---|
| BAG hücresi | KSGR, 343 yatak | `verified` |
| Üç Spitalliste PDF’indeki bölüm | Thusis Gynäkologie; PDGR Forensische Psychiatrie; Andeer muskuloskelettale Rehabilitation | `verified` bölüm |
| Hastane sayfasındaki menü veya cümle | bir klinik adı | `candidate` |

Kod satırı ayrı durur. `GYN1` bir bölümdür demez. “Bu hizmet OKP kapsamında faturalanabilir” der. O satır `service_mandate` tablosunda kalır ve grafın yanında gösterilir.

## 3. Nereden hangi veriyi aldık

### 3.1 BAG 2024 anahtar rakamları

Kaynak dosya `kzp24_data.xlsx`. Katalog sayfası [Kennzahlen der Schweizer Spitäler 2024](https://opendata.swiss/de/dataset/kennzahlen-der-schweizer-spitaler-2024). Dosyanın kendisi [kzp24_data.xlsx](https://opendata.bagnet.ch/?r=/download&path=L0taUC9renAyNC9renAyNF9kYXRhLnhsc3g%3D). İsviçre genelinde 270 kuruluş vardır. Ana kantonu GR olanlar 18’dir.

Bu dosyadan şunlar gelir:

- Kuruluşun resmi adı ve ana kantonu
- Sahalar ve her sahanın kantonu
- Akut işletme yatağı, ölçü kodu `BettenStatA`
- Ekipman kodları: MRI, CT, PET, CC, LB, Lito, Angio, Dia

Basit örnek. Excel’de KSGR satırında yatak hücresi 343 yazar. Yükleyici bunu bir istatistik gözlemine çevirir. Kapsam `establishment` olur. Saha kimliği boş kalır.

Aynı dosyada KSGR’nin bir sahası Spital Walenstadt’tır ve kanton kodu SG’dir. Bu, “GR hastanesinin SG’de sahası var” demektir. Saha, kuruluştan kopmaz.

BAG sayfasında bazı adlar bozuk karakterle durur. KSGR saha adı `Kantonsspital Graub?nden` olarak saklanır. Soru işareti onarılmaz. Kaynakta öyle basılıdır.

### 3.2 Graubünden Spitalliste

Kaynak, kantonun [Spitalliste sayfası](https://www.gr.ch/DE/institutionen/verwaltung/djsg/ga/InstitutionenGesundeitswesens/Spitaeler/Seiten/SpitallisteSpitalplanung.aspx). Üç PDF:

- [Akutsomatik](https://www.gr.ch/DE/institutionen/verwaltung/djsg/ga/InstitutionenGesundeitswesens/Spitaeler/Dok%20Spitler/Spitalliste_Akutsomatik.pdf), Nisan 2026
- [Psikiyatri](https://www.gr.ch/DE/institutionen/verwaltung/djsg/ga/InstitutionenGesundeitswesens/Spitaeler/Dok%20Spitler/Spitalliste%20Psychiatrie.pdf), Ağustos 2025
- [Rehabilitasyon](https://www.gr.ch/DE/institutionen/verwaltung/djsg/ga/InstitutionenGesundeitswesens/Spitaeler/Dok%20Spitler/Spitalliste_Rehabilitation.pdf), Ağustos 2024

Bölüm adları bu üç PDF’ten gelir. Akut PDF’te hastane adının altındaki tabloda ilk sütun bölüm adıdır. Aynı satırın kodu ve sağdaki etiket, faturalama yetkisidir. Kod `GYN1`, etiket `Gynäkologie` olan satır `service_mandate` olarak kalır. İlk sütundaki `Gynäkologie` ise `hasDepartment` olur, durumu `verified` olur.

Thusis’in ilk sütununda 17 bölüm vardır: Basispaket, Dermatologie, Neurologie, Endokrinologie, Gastroenterologie, Viszeralchirurgie, Hämatologie, Herz, Urologie, Pneumologie, Bewegungsapparat chirurgisch, Rheumatologie, Gynäkologie, Geburtshilfe, Neugeborene, (Radio-) Onkologie, Querschnittsbereiche. Sağdaki `BEW1`, `GYN1`, `GYNT` gibi kodlar bölüm değildir. KSGR’de 24, Savognin’de 10 bölüm vardır. Satır kaydırma birleştirilir: `Querschnitts-` ve `bereiche` tek ad olur. Dipnot ve `Z04` kod satırı bölüm olmaz.

Akut listede adı bağlanan kuruluşların eski sayfa bölüm iddiaları silindi. Yerine bu sütun yazıldı. Psikiyatri ve rehabilitasyon listelerinde tablo yoktur. Bölüm, `Leistungsauftrag` altındaki satırdır. Dipnot ve kesik satır alınmaz. PDGR’nin 9 bölümü, Holistica’nın tek bölümü, Seewis’in 6 bölümü ve reha Andeer’in tek bölümü buradan gelir. Rehazentrum Chur’un başlığı `Kliniken Valens, Rehazentrum Chur…` diye basılıdır. Virgülden önceki ad Kliniken Valens olduğu için bu satırlar o kuruluşa yazılır.

Yüklenen yetki sayıları, gözden geçirilmiş takma adlardan sonra:

| Liste | Satır | Tam ad eşleşmesi | Gözden geçirilmiş takma ad | Eşleşmeyen |
|---|---:|---:|---:|---:|
| Akut | 678 | 277 | 233 | 168 |
| Psikiyatri | 30 | 0 | 22 | 8 |
| Rehabilitasyon | 37 | 6 | 15 | 16 |

Kanton içi eşleşmeyenler, üç Zürcher Reha başlığıdır. Bu ad, 2024 GR kuruluş listesindeki 18 addan biri değildir. Otomatik birleştirilmez.

### 3.3 Hastane web siteleri ve PDF’ler

18 kuruluşun resmi sitesi `gr_websites.py` içine elle yazıldı. Adres, hastanenin kendi sayfasından veya Bündner Spital- und Klinikverein üye listesinden alındı. Posta adresi, 2024 rakamlarıyla karşılaştırıldı.

Menü örneği, Savognin’in [Gynäkologie sayfası](https://www.cds-savognin.ch/DE/spital-praxis/externen-fachspezialisten/gynaekologie.html). On sekiz kuruluşun ana adresi:

- [Kantonsspital Graubünden](https://www.ksgr.ch/)
- [Spital Oberengadin](https://www.spital-oberengadin.ch/)
- [Regionalspital Surselva](https://www.rss.ch/)
- [Spital Davos](https://www.spitaldavos.ch/de)
- [Ospidal d'Engiadina Bassa](https://cseb.ch/)
- [Spital Thusis](https://www.spitalthusis.ch/)
- [Ospedale San Sisto](https://www.csvp.ch/it/)
- [Center da Sanadad Savognin](https://www.cds-savognin.ch/DE/home.html)
- [Center da Sanadad Val Müstair](http://csvm.ch/de/)
- [Centro Sanitario Bregaglia](https://www.csbregaglia.ch/it/)
- [Psychiatrische Dienste Graubünden](https://www.pdgr.ch/)
- [Clinica Holistica Engiadina](https://www.clinica-holistica.ch/de)
- [Hochgebirgsklinik Davos](https://hochgebirgsklinik.ch/)
- [Rehaklinik Seewis](https://www.rehaklinik-seewis.ch/de/)
- [Rehazentrum Chur](https://valens.ch/reha-chur/)
- [reha andeer](https://reha-andeer.ch/de/die-reha-andeer)
- [Klinik Gut](https://www.klinik-gut.ch/)
- [Flury Stiftung Spital Schiers](https://www.flurystiftung.ch/de/spital-schiers)

Kaydedilen derlem:

- 1262 belge
- 1246 belge bir kuruluşa bağlı
- 16 belge bağlı değil (`valens.ch` üzerinde `/reha-chur` dışında kalanlar)
- 19102 metin parçası

Metin parçası, bir HTML bölümü veya bir PDF sayfasıdır. Belgenin tamamı tek bir metin kutusuna konmaz. OCR’ı bozulan sayfa, sessizce atılmaz. Başarısız parça olarak yazılır.

## 4. İsim nasıl bağlandı

Aynı hastane kaynaklarda farklı yazılır. Bağlama kuralı dardır.

Yöntem `exact_normalized_name_2024`:

1. Unicode birleştirilir (NFC).
2. Harfler küçük harfe çevrilir.
3. Art arda boşluklar tek boşluğa iner.

Şunlar yapılmaz: `AG` veya `SA` silinmez, tire silinmez, eksik kelime tamamlanmaz.

Örnek. `Kantonsspital Graubünden` ile `Kantonsspital Graubünden` eşleşir. `Klinik für Gynäkologie` ile `Gynäkologie` eşleşmez. Yakın görünen ad, eşleşmemiş kalır.

Virgülden önceki tam ad da kullanılır. `Kliniken Valens, Rehazentrum Chur…` ifadesinde virgülden önceki kısım tam olarak `Kliniken Valens` olduğu için kayıt, ana kantonu SG olan BAG kuruluşuna gider. GR’deki Rehazentrum Chur’a gitmez. Rehazentrum Chur’un aday klinikleri vardır. Üst yetki satırı, GR kuruluşuna yazılmaz.

Gözden geçirilmiş takma adlar ayrı bir listededir. Unterengadin buna örnektir. Listeye elle konur. Otomatik birleşme yoktur.

Zürcher RehaZentren Davos, 18 GR kuruluşundan biri değildir. Eşleşmeden kalır. BAG’daki `Z?rcher RehaZentren Klinik Davos` sahası, ZH kuruluşu Stiftung Kliniken Valens Davos’a aittir. Graubünden’de duran gerçek bir sahadır. Kuruluşun ana kantonu ZH’dir.

## 5. Yapılandırılmış veriden ne üretildi

Yükleyici Excel satırını tablolara böler.

Kuruluş: Kantonsspital Graubünden, ana kanton GR.

Saha: Spital Walenstadt, kanton SG. Bağ `siteOf` yönündedir. Saha, kuruluşu gösterir. Ters yöndeki “kuruluşun sahası” Excel’de ayrı bir hücre olarak yoktu. O yüzden ikinci bir üçlü uydurulmaz.

Yatak: 343, ölçü `BettenStatA`, kapsam kuruluş. Bir SPARQL sorgusu bu sayıyı isterken “bu istatistiğin sahası var mı” diye bakar. Saha bağlıysa satır elenir. Canlı sonuç 343’tür.

Ekipman: `MRI` bir `EquipmentPresence` kodudur. “Hastanede MRI cihazı var” cümlesi ayrı bir kayıttır. O cümle `MedicalDevice` adayı olur. Kodun yerine geçmez.

## 6. Sayfalardan ne çıkarıldı

Üç çıkarma yolu vardır.

**Katalog bağlantısı.** Hastanenin kendi dizininde son yol parçası bir bölüm adıdır. Örnek: bir KSGR sayfasının adresi `.../gynaekologie` ise etiket oradan okunur. Dil öneki yok sayılır. `?page=2` tutulur. Adresin içindeki kelime, saha atamak için kullanılmaz. Saha, metin sahayı açıkça yazmıyorsa boş kalır.

**Ana sayfa menüsü.** Katalog sayfası olmayan kuruluşlarda menü etiketleri okunur. Katalogu olan kuruluş atlanır. Böylece aynı menü iki kez yazılmaz.

**Açık ifade.** Bir başlık veya cümle bir şeyi adıyla söylüyorsa aday iddia olur. Çıkan ilişki türleri:

| Metindeki şey | Graf ilişkisi |
|---|---|
| Bölüm | `hasDepartment` |
| Klinik | `hasClinic` |
| Hizmet | `hasService` |
| Tedavi | `offersTreatment` |
| Cihaz adı | `mentionsEquipment` |
| İş birliği | `cooperatesWith` |
| Bağlılık | `affiliatedWith` |
| Etkinlik | `hasEvent` |

“Partnerlerimiz” gibi belirsiz bir cümle iş birliği olmaz. Yine de yükleyici e-posta, menü artığı, iş ilanı ve kesik cümle de yazmıştı. Bunlar satır satır okunup silindi. Kalan adaylar `candidate` olarak duruyor.

Her çıkarma bir kanıtla durur: yöntem, sayfa veya adres, kısa alıntı. Sayfadan gelen bir kelime, ikinci bir resmi metin aynı adı kullanana kadar `candidate` kalır. Üç Spitalliste PDF’indeki bölüm adı kopyalanmış bir satırdır. Durumu `verified` olur. Akut listede bu ad tablonun ilk sütunudur. Psikiyatri ve rehabilitasyon listesinde `Leistungsauftrag` altındaki satırdır.

Resmi listesi yazılan kuruluşların sayfa bölüm iddiaları silindi. Forensische Psychiatrie psikiyatri listesinin satırıdır. Rehazentrum Chur’un sayfa bölümleri durur, çünkü rehabilitasyon PDF’indeki iki satır virgül kuralıyla Kliniken Valens’e yazılır.

## 7. Bir aday neden kabul edildi

Kural seçilmiş bir eşiğidir. Yasa değildir.

BAG hücresi kopyalanmış bir hücredir. Durumu `verified` olur.

Hastane sayfasındaki bir kelime, yayımlanmış bir kelimedir. Tek başına `accepted` olmaz. Kabul için ikisi birden gerekir:

1. Hastanenin kendi kaydedilmiş dizini veya menüsü bu etiketi kullanır.
2. Aynı kuruluşun üst Spitalliste yetkisi, aynı etiketi kullanır.

Karşılaştırma, bölüm 4’teki normalleştirmeyle yapılır. Alt kodlar (`GYN1.1`) üst yetki sayılmaz. `Klinik für Gynäkologie`, `Gynäkologie` ile aynı sayılmaz. Cümleden çıkan ifade aday kalır.

Bölüm listesi bu kuraldan gelmez. Üç PDF’in bölüm satırıdır ve `verified` durur. Akut listede satır, tablonun ilk sütunudur. Psikiyatri ve rehabilitasyon listesinde `Leistungsauftrag` altındaki satırdır. Savognin’de Gynäkologie akut sütundadır. PDGR’de Forensische Psychiatrie psikiyatri satırıdır. Sayfadan çıkarılmış eski bölüm satırları, resmi listesi olan kuruluşlar için silindi.

Kural sayfa etiketi için durur. Kabul edilmiş iddia kalmadı.

## 8. Tek çıkarım

İki BAG hücresi karşılaştırılır: kuruluşun ana kantonu ve sahanın kantonu. Farklıysa grafa ayrı bir iddia eklenir.

- Kip: `inferred`
- Yöntem: `site_canton_differs_from_home`
- Durum: `verified`
- Dayanak: sahanın kendi kanıtı

Üç saha bu kurala girer:

| Saha | Kuruluş | Ana kanton | Saha kantonu |
|---|---|---|---|
| Spital Walenstadt | Kantonsspital Graubünden | GR | SG |
| PDGR Tagesklinik Glarus | Psychiatrische Dienste Graubünden | GR | GR dışında |
| Z?rcher RehaZentren Klinik Davos | Stiftung Kliniken Valens Davos | ZH | GR |

Bu iddia, “kuruluşun sahası şudur” üçlüsünün yerine geçmez. `siteOf` durur. Çıkarım, “bu saha ana kantonun dışındadır” diye ayrıca yazılır. Dayanak, sahanın kanton hücresini tekrarlayan bir öncül iddiadır (`derivedFrom`). HermiT pilotun üzerine çalıştırılmaz. KSGR örneğinde çalışır ve yazılmamış `hasSite` tersini üretir.

## 9. Graf nasıl çiziliyor

Ekran varsayılanı: bütün pilot, bütün çıkarılan iddialar, bölüm ve klinik. Resmi bölüm üç Spitalliste PDF’inden gelir. Akut listede tablonun ilk sütunudur. Psikiyatri ve rehabilitasyon listesinde `Leistungsauftrag` altındaki satırdır.

Savognin bu görünümde 15 düğüm ve 15 bağ gösterir. On bölüm şunlardır: Basispaket, Basispaket Elektiv, Dermatologie, Neurologie, Gastroenterologie, Urologie, Pneumologie, Bewegungsapparat chirurgisch, Rheumatologie, Gynäkologie. Thusis 17 bölüm, KSGR 24 bölüm gösterir. PDGR’nin 9 bölümü psikiyatri PDF’indendir: Akutpsychiatrie / Psychotherapie, Rehabilitationspsychiatrie, Gerontopsychiatrie, Abhängigkeitserkrankungen, Stressfolgeerkrankungen, Forensische Psychiatrie, Psychosomatik, Kinder und Jugendliche, Hometreatment.

Tüm pilot açılırsa paylaşılan kanton, ekipman kodu veya aynı normal ad tek düğüm olur. İki hastane aynı bölüm adını kullanıyorsa o düğümde buluşur. Altın düğüm, ana kantonun dışındaki sahadır.

Çizim vis-network ile yapılır. Fizik kapalıdır. Düğümler halkalar halinde durur. Çok düğüm varken etiketler gizlenir.

## 10. SPARQL nerede

SPARQL, Wikidata’ya gitmez. Ayrı bir üçlü veritabanı da yoktur. RDFLib, `data/pilot.sqlite` içinden kurulan grafı bellekte sorgular.

Ekranda yedi hazır soru vardır:

1. Gynäkologie bölümü olan kuruluşlar. Akut listenin ilk sütunundan: Savognin, Engiadina Bassa, Valposchiavo, Flury, KSGR, Surselva, Spital Davos, Oberengadin, Thusis
2. Spital Walenstadt’ın kantonu
3. KSGR yatak sayısı, sahaya bağlı olmadan
4. Ana kantonun dışındaki sahalar
5. Kuruluş başına kabul edilmiş iddia sayısı
6. GR kuruluşlarının ekipman kodları
7. Sahası GR’de olup kuruluşu başka kantonda olanlar

Yedinci sorunun canlı cevabı tektir: saha `Z?rcher RehaZentren Klinik Davos`, kuruluş Stiftung Kliniken Valens Davos, ana kanton ZH.

Beşinci soru kabul edilmiş iddiayı sayar. Kalan kabul edilmiş iddia yoktur. Sorgu satır döndürmez.

**Your query** kutusuna elle `SELECT` yazılır. `shi:` ve `skos:` önceden tanımlıdır. İsim karşılaştırması `FILTER` içine yazılır, çünkü metinler tipli dizidir. Düz üçlü kalıbı bu dizilerle eşleşmez.

James Bond projesindeki SPARQL başkadır. O çalışma Wikidata’dan film ve oyuncu çekmek için sorgu yazmış, rapora basmıştır. Ekranında serbest kutu, sayım ve ekipman sorusu yoktur.

## 11. Ekranda ne var

Adres: `http://localhost:8502`

Üstte iki sayı vardır: grafdaki kuruluşlar ve 751 iddia. 751, 538 aday iddia ile 213 doğrulanmış iddianın toplamıdır. Kuruluş, saha, kanton, yatak ve ekipman kodu bu sayının dışındadır. PDGR bölümleri doğrulanmış iddiaların içindedir.

Sonra graf: bütün pilot veya seçili kuruluş. Varsayılan resim bütün çıkarılan iddiaları açar. Diğer seçenek üç PDF’teki resmi bölümlerdir. İlişki türü seçilir. Etkinlik ve bağlılık listede yoktur. Satırları veritabanında durur. Başka kantonun işlettiği GR sahası ayrı bir tablo olarak durmaz. Aynı olgu, seçili kuruluşun altında ve yedinci hazır sorguda görünür.

Grafın altında SPARQL. Hazır sorunun metni de görünür.

Seçili kuruluşun altında üç sütun:

- Doğrulanmış graf: yatak, GR’deki sahalar, dış kanton sahası, ekipman
- Spitalliste yetkisi: kod ve etiket. Bölüm üçlüsü değildir
- Belge iddiaları: tür, ad, durum

Ekranda kapsam boşluğu yazılmaz. Okunamayan dosyalar (PowerPoint, 404, taranmış PDF, 20 MB üstü dosya) Almanca raporda durur. Bu dosyalardan iddia çıkmaz.

## 12. Hangi araç kullanıldı

| Araç | Ne için |
|---|---|
| Python 3.11 | Bütün yükleyiciler ve sorgular |
| `data/pilot.sqlite` | Ekranın okuduğu hazır kopya. `run.bat` bunu açar |
| PostgreSQL 16, Docker | Yüklemenin kaydı. Bağlantı `postgresql+psycopg://shi:shi@localhost:5432/shi`. Ekran için gerekmez |
| SQLAlchemy | Tablolar ve sorgular |
| Alembic | Şema göçleri. Son göç hizmet yetkisi tablosunu ekler |
| psycopg | Python’un PostgreSQL sürücüsü |
| openpyxl ve pandas | Excel |
| PyMuPDF | Spitalliste ve hastane PDF’leri |
| Pydantic | Ayrıştırılmış satırın biçimi |
| RDFLib | Ontoloji, graf, SPARQL |
| pySHACL | Şekil denetimi. Rapor `data/exports/shacl-report.txt` |
| owlready2 ve HermiT | Yalnız KSGR örneğinde `hasSite` tersini üretir. Sonuç `data/exports/reasoner-example.txt` |
| Streamlit | Ekran. FastAPI’nin önünde durmaz. `data/pilot.sqlite` dosyasını ve grafı doğrudan okur |
| vis-network | Ağ resmi |
| pytest | Bellekteki sqlite üzerinde birim testler. Gerçek dosya yoksa o test atlanır |

Test veritabanı `sqlite://` olur ve tablolar test sırasında kurulur.

## 13. Bilerek yapılmayanlar

Bunlar eksik bırakıldı, çünkü kural öyle kuruldu:

- Faturalama kodu bölüm yapılmadı. Bölüm adı üç Spitalliste PDF’inden gelir: akut tablonun ilk sütunu, psikiyatri ve rehabilitasyon listelerinde `Leistungsauftrag` altındaki satır.
- URL’deki kelimeden saha uydurulmadı.
- Yatak, sahaya kopyalanmadı.
- Yakın adlar birleştirilmedi.
- BAG’daki `?` harfi düzeltilmedi.
- Ters özellikler, Excel’de varmış gibi yazılmadı. HermiT bunları yalnız KSGR örneğinde üretir.
- Aday iddialar grafın dışında bırakılmadı. İstendiği için grafın içindeler ve durumları üstlerinde duruyor.
- Asistan ve FastAPI yok.
- SHACL, pySHACL ile hem örnekte hem pilotta çalışır. Rapor `data/exports/shacl-report.txt` dosyasındadır.

Yıllık veya kalite raporu, başlıkta ya da adreste `jahresbericht`, `geschäftsbericht` veya `qualitätsbericht` geçen belge sayılır. Oberengadin, Bregaglia, Holistica, Val Müstair, Valposchiavo, Hochgebirgsklinik, Seewis ve Rehazentrum Chur için bu iz bulunamadı. Bu, rapor yoktur demek değildir. Kaydedilen sayfalarda bu iz yoktur.

## 14. Bir kuruluşu baştan sona izlemek

Kantonsspital Graubünden üzerinden bütün yol:

1. Excel’de kuruluş, ana kanton GR, yatak 343, ekipman kodları ve Chur’daki saha okunur.
2. Aynı dosyada Spital Walenstadt, kanton SG olarak okunur.
3. Ad, 2024 kuruluş adıyla harfi harfine bağlanır.
4. `ksgr.ch` kaydedilir, bölümlere ayrılır, menü ve cümlelerden aday iddialar yazılır.
5. Spitalliste’deki KSGR kod satırları yetki tablosuna gider. Akut listenin ilk sütunu, 24 bölüm olarak grafa yazılır. Gynäkologie bu listededir. PDGR’nin 9 bölümü psikiyatri PDF’inden, rehabilitasyon satırları rehabilitasyon PDF’inden gelir.
6. Sayfa etiketi ile üst yetki etiketi aynıysa, o sayfa etiketi kabul edilir. Üç listedeki bölüm satırı bu yoldan gelmez.
7. Walenstadt için çıkarım iddiası eklenir: saha SG’de, ev GR’de.
8. Ekran kuruluşu, yatağı, ekipmanı, GR sahasını, Walenstadt’ı ve üç listedeki bölümü birlikte gösterir.
9. SPARQL “KSGR yatak, sahasız” sorusu 343 döndürür. “Walenstadt kantonu” sorusu SG döndürür.

## 15. Dosyalar nerede

| Dosya | İş |
|---|---|
| `src/.../ingestion/structured/kzp.py` | Excel ayrıştırma |
| `src/.../ingestion/structured/load_kzp.py` | Excel’i veritabanına yazma |
| `src/.../ingestion/structured/spitalliste.py` | Üç PDF’in yetki listesi; akut ilk sütun ve psikiyatri ile rehabilitasyon satırları |
| `src/.../ingestion/structured/load_department_column.py` | Üç PDF’teki bölüm adlarını `verified` olarak yazar |
| `src/.../ingestion/structured/name_link.py` | Ad normalleştirme |
| `src/.../ingestion/documents/gr_websites.py` | 18 sitenin adresleri |
| `src/.../ingestion/documents/catalog_pages.py` | Dizin etiketleri |
| `src/.../ingestion/documents/extract_mentions.py` | Cümle ve başlık |
| `src/.../knowledge_graph/project.py` | Tablodan grafa |
| `src/.../knowledge_graph/accept.py` | İki metin aynıysa kabul |
| `src/.../knowledge_graph/queries.py` | SPARQL |
| `src/.../knowledge_graph/network.py` | Ağ resmi |
| `frontend/app.py` | Ekran. `data/pilot.sqlite` dosyasını okur |
| `scripts/export_pilot_sqlite.py` | PostgreSQL değişince kopyayı yeniler |
| `run.bat` | Ortamı kurar ve ekranı açar |
| `ontology/swiss_hospital_ontology.ttl` | Sınıflar ve ilişkiler |
| `ontology/shapes/core.shacl.ttl` | SHACL şekilleri |
| `ontology/examples/ksgr-2024.ttl` | HermiT’in çalıştığı KSGR örneği |
| `docs/graubunden_report.md` | Öğretmen için İngilizce not |

Ham dosyalar `data/raw` ve `data/documents` altındadır. Git’e konmaz. Ekranın okuduğu hazır kopya `data/pilot.sqlite` dosyasıdır. Bu dosya depoya girer. Turtle, JSON-LD, SHACL raporu ve HermiT sonucu `data/exports` altındadır. Onlar da depoya konmaz.

## 16. Her tablodan bir satır

Satırlar `data/pilot.sqlite` dosyasındandır. Örneklerin çoğu Kantonsspital Graubünden’dendir. Kimlik numaraları yazılmadı. Boş üç tablo da burada durur: `list_membership`, `quality_indicator`, `quality_observation`. İçlerinde satır yoktur.

### `source`

Kaynağın kendisi. Dört satır vardır. Biri:

| Sütun | Değer |
|---|---|
| Kod | `BAG-KZP-2024` |
| Ad | Kennzahlen der Schweizer Spitäler 2024 |
| Adres | https://opendata.swiss/de/dataset/kennzahlen-der-schweizer-spitaler-2024 |
| Güvenirlik | `official_federal_publication` |

Diğer üç kod: `GR-SPITALLISTE`, `GR-WEB-PAGES`, `GR-CATALOG-LINKS`.

### `source_file`

İndirilen dosyanın kaydı. Excel satırı:

| Sütun | Değer |
|---|---|
| Kaynak | `BAG-KZP-2024` |
| Dosya adı | `kzp24_data.xlsx` |

Spitalliste satırı: kaynak `GR-SPITALLISTE`, dosya adı `akutsomatik.pdf`. `psychiatrie.pdf` ve `rehabilitation.pdf` ayrı satırlardır.

### `hospital_organization`

Kuruluş. Ad bu tabloda durmaz.

| Sütun | Değer |
|---|---|
| Ana kanton | GR |
| Tip | `K112` |
| Hukuki biçim | `R2` |
| Sokak | Loestrasse 170 |
| Yer | 7000 Chur |
| Yıl | 2024 |
| Durum | `verified` |

### `organization_name`

Kuruluşun adı.

| Sütun | Değer |
|---|---|
| Ad | Kantonsspital Graubünden |
| Rol | `source_primary` |
| Eşleşme | `exact` |

### `hospital_site`

Saha. Ad bu tabloda durmaz.

| Sütun | Değer |
|---|---|
| Kanton | SG |
| Sokak | Spitalstrasse 5 |
| Yer | 8880 Walenstadt |
| Yıl | 2024 |

Bu saha Kantonsspital Graubünden’e bağlıdır.

### `site_name`

Sahanın adı.

| Sütun | Değer |
|---|---|
| Ad | Spital Walenstadt |
| Rol | `source_primary` |

### `organization_code_set`

Ekipman kodu.

| Sütun | Değer |
|---|---|
| Küme | `equipment` |
| Kod | MRI |
| Yıl | 2024 |

### `measure_definition`

Ölçünün tanımı. Sayı burada durmaz.

| Sütun | Değer |
|---|---|
| Kod | `BettenStatA` |
| Birim | `bed_operating_average` |
| Faaliyet | A |
| Kapsam | `establishment` |
| Yayım | `published` |

### `statistic_observation`

Ölçülen sayı.

| Sütun | Değer |
|---|---|
| Ölçü | `BettenStatA` |
| Yıl | 2024 |
| Faaliyet | A |
| Kapsam | `establishment` |
| Sayı | 343 |
| Ham değer | 343 |
| Durum | `value` |
| Birim | `bed_operating_average` |

Saha kimliği boştur. 343 yatak kuruluşa aittir.

### `service_mandate`

Faturalama yetkisi. Graf düğümü olmaz.

| Sütun | Değer |
|---|---|
| Liste | `akutsomatik` |
| Baskı | April 2026 |
| Kapsam | `in_canton` |
| PDF’teki ad | Kantonsspital Graubünden, Chur |
| Kod | `GYN1` |
| Etiket | Gynäkologie |
| Eşleşme | `exact` |

### `document`

Kaydedilmiş sayfa.

| Sütun | Değer |
|---|---|
| Başlık | Center da Sanadad Savognin \| Home |
| Adres | https://www.cds-savognin.ch/DE/home.html |
| Tür | `html` |
| Dil | de |
| İşlenme | `parsed` |

### `document_chunk`

Sayfadan kesilen parça. Savognin’in Gynäkologie başlığı altındaki bir parça:

| Sütun | Değer |
|---|---|
| Bölüm | Gynäkologie |
| Dil | de |
| Sıra | 2 |
| Sayfa | boş |
| Metin | Vertrauen Sie auf unser Fachwissen. |

Bu metin bölüm listesi değildir. Bölüm adı, alttaki `assertion` satırındadır.

### `evidence`

İddianın kanıtı.

| Sütun | Değer |
|---|---|
| Alıntı | Gynäkologie |
| Sayfa | boş |
| Bölüm | `first column` |
| Adres | akut Spitalliste PDF’i |
| Yöntem | `spitalliste_department_column` |

### `assertion`

İddia. Resmi bölüm:

| Sütun | Değer |
|---|---|
| İlişki | `hasDepartment` |
| Ad | Gynäkologie |
| Durum | `verified` |
| Kip | `documented` |
| Model | boş |
| Saha | boş |

Sayfadan çıkan klinik:

| Sütun | Değer |
|---|---|
| İlişki | `hasClinic` |
| Ad | Augenklinik |
| Durum | `candidate` |
| Kip | `extracted` |

İki satır da Kantonsspital Graubünden’e aittir. Birincisi `evidence` satırındaki PDF alıntısına bağlıdır.

### `entity_crosswalk`

Aynı kaynak satırının ikinci kez yazılmasını tutan parmak izi.

| Sütun | Değer |
|---|---|
| Hedef tablo | `assertion` |
| Eşleşme | `exact` |
| Yöntem | `spitalliste_department_column` |

### Boş tablolar

`list_membership`, `quality_indicator` ve `quality_observation` tabloları şemada durur. Pilot yüklemesi onlara satır yazmamıştır.
