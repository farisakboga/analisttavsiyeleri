# Analist Tavsiyeleri Scraper

Her 30 dakikada bir [fintables.com/analist-tavsiyeleri](https://fintables.com/analist-tavsiyeleri) adresinden veri çeker ve `data/analist_tavsiyeleri.json` dosyasını günceller.

## JSON Formatı

```json
{
  "guncelleme_zamani": "2025-06-05T12:00:00Z",
  "kayit_sayisi": 120,
  "veriler": [
    { "Hisse": "THYAO", "Son Fiyat": "245,50", ... },
    ...
  ]
}
```

## Canlı Veri URL'si (GitHub Pages açıksa)

```
https://<KULLANICI_ADI>.github.io/<REPO_ADI>/data/analist_tavsiyeleri.json
```

## GitHub Pages Nasıl Açılır?

1. Repo → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / `/ (root)`
4. **Save**

## Elle Tetikleme

Actions sekmesi → **Analist Tavsiyeleri Güncelle** → **Run workflow**
