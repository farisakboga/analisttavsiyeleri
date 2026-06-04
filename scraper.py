import json
import os
from playwright.sync_api import sync_playwright
from datetime import datetime, timezone
import pandas as pd

HEDEF_URL = "https://fintables.com/analist-tavsiyeleri"
CIKTI_DOSYASI = "data/analist_tavsiyeleri.json"

def veriyi_cek(page):
    print(f"Adresine gidiliyor: {HEDEF_URL}")
    page.goto(HEDEF_URL)

    print("Tablonun yüklenmesi bekleniyor...")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("tbody tr", timeout=20000)

    tum_satirlar = {}
    headers = []

    print("Verileri kaydırılarak toplanıyor...")

    son_satir_sayisi = 0
    durma_sayaci = 0

    for adim in range(300):
        js_veri = page.evaluate("""
            () => {
                const result = { headers: [], rows: [] };
                const ths = document.querySelectorAll('thead th');
                result.headers = Array.from(ths).map(th => th.innerText.trim().replace(/\\s+/g, ' '));
                const rows = document.querySelectorAll('tbody tr');
                rows.forEach(row => {
                    const cols = row.querySelectorAll('td');
                    if (cols.length > 0) {
                        result.rows.push(Array.from(cols).map(td => td.innerText.trim().replace(/\\s+/g, ' ')));
                    }
                });
                return result;
            }
        """)

        if not headers and js_veri['headers']:
            headers = js_veri['headers']

        for row_data in js_veri['rows']:
            if row_data and row_data[0] != "":
                anahtar = tuple(row_data)
                if anahtar not in tum_satirlar:
                    tum_satirlar[anahtar] = row_data

        page.evaluate("window.scrollBy(0, 400)")
        page.evaluate("""
            const scrollableDivs = document.querySelectorAll('div');
            scrollableDivs.forEach(div => {
                if (div.scrollHeight > div.clientHeight && window.getComputedStyle(div).overflowY !== 'hidden') {
                    div.scrollBy(0, 400);
                }
            });
        """)

        page.wait_for_timeout(200)

        mevcut_satir_sayisi = len(tum_satirlar)

        if mevcut_satir_sayisi == son_satir_sayisi:
            durma_sayaci += 1
            if durma_sayaci >= 5:
                break
        else:
            durma_sayaci = 0
            son_satir_sayisi = mevcut_satir_sayisi

    print(f"Tarama bitti. {len(tum_satirlar)} adet benzersiz satır toplandı.")

    if not tum_satirlar:
        print("HATA: Tablo verisi bulunamadı.")
        return pd.DataFrame()

    veri_listesi = list(tum_satirlar.values())
    max_cols = max(len(r) for r in veri_listesi)
    for r in veri_listesi:
        while len(r) < max_cols:
            r.append("-")
    if not headers or len(headers) < max_cols:
        headers = [f"Sütun {i+1}" for i in range(max_cols)]
    else:
        headers = headers[:max_cols]

    df = pd.DataFrame(veri_listesi, columns=headers)

    # "Son Fiyat" sütunundaki gecikmeli fiyat göstergesi "G" harfini temizle
    son_fiyat_cols = [c for c in df.columns if "son fiyat" in c.lower()]
    for col in son_fiyat_cols:
        df[col] = df[col].astype(str).str.replace(r'^G\s*', '', regex=True).str.strip()

    return df

def main():
    os.makedirs("data", exist_ok=True)

    with sync_playwright() as p:
        print("Chromium başlatılıyor...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        try:
            df = veriyi_cek(page)
        except Exception as e:
            print(f"HATA: {e}")
            df = pd.DataFrame()
        finally:
            browser.close()

    if df.empty:
        print("Kaydedilecek veri yok, çıkılıyor.")
        raise SystemExit(1)

    temiz_df = df.astype(object).where(pd.notnull(df), None)
    cikti = {
        "guncelleme_zamani": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kayit_sayisi": len(temiz_df),
        "veriler": temiz_df.to_dict(orient="records")
    }

    with open(CIKTI_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)

    print(f"TAMAMLANDI: {len(temiz_df)} kayıt '{CIKTI_DOSYASI}' dosyasına yazıldı.")

if __name__ == "__main__":
    main()
