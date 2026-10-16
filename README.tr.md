# Tek kanallı EOG/EEG ile göz kırpması algılama

Arduino Uno, alından tek bir biyopotansiyel kanalını örnekleyip bilgisayara gönderir. Python sinyali filtreler ve eşik tabanlı bir dedektörle göz kırpmalarını algılar.

> **Durum:** Kod tamamlandı ve sentetik sinyallerle test edildi. Ölçülmüş sonuç henüz yok; kayıtlar alındıktan sonra eklenecek.

- Donanım: Arduino Uno R3, **TODO: sensör modeli**, sinyal çıkışı A0'a. 250 Hz, 115200 baud.
- Kayıt ve değerlendirme: sinyal zinciri ve sınırlamalar için ayrıntılar [README.md](README.md) dosyasında.

```bash
pip install -r requirements.txt
python demo.py --synthetic   # sentetik sinyal, sonuç değildir
pytest -q
```
