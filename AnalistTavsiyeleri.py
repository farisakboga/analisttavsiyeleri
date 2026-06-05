import os
import json
from playwright.sync_api import sync_playwright
import pandas as pd

HEDEF_URL = "https://fintables.com/analist-tavsiyeleri"

def veriyi_cek(page):
    print(f"\nAdresine gidiliyor: {HEDEF_URL}")

    # GitHub Actions'da bot tespitini zorlaştırmak için gerçekçi headers
    page.set_extra_http_headers({
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    })

    page.goto(HEDEF_URL, wait_until="domcontentloaded", timeout=60000)

    # networkidle yerine sabit bekleme + selector — CI'da daha güvenilir
    print("Sayfa JS render bekleniyor (5 sn)...")
    page.wait_for_timeout(5000)

    # Tablo gelmezse HTML'i artifact olarak kaydet ve hata ver
    try:
        page.wait_for_selector("tbody tr", timeout=30000)
    except Exception:
        html_icerik = page.content()
        with open("debug_sayfa.html", "w", encoding="utf-8") as f:
            f.write(html_icerik)
        print("HATA: 'tbody tr' bulunamadı. Sayfa içeriği 'debug_sayfa.html' olarak kaydedildi.")
        print(f"Sayfa başlığı: {page.title()}")
        print("HTML önizleme (ilk 2000 karakter):")
        print(html_icerik[:2000])
        return pd.DataFrame()

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

        # Hem window hem de içerideki scrollable div'leri kaydır
        page.evaluate("window.scrollBy(0, 600)")
        page.evaluate("""
            const divs = document.querySelectorAll('div');
            divs.forEach(div => {
                if (div.scrollHeight > div.clientHeight + 10 &&
                    window.getComputedStyle(div).overflowY !== 'hidden') {
                    div.scrollBy(0, 600);
                }
            });
        """)
        page.wait_for_timeout(300)

        mevcut_satir_sayisi = len(tum_satirlar)
        if mevcut_satir_sayisi == son_satir_sayisi:
            durma_sayaci += 1
            if durma_sayaci >= 8:
                break
        else:
            durma_sayaci = 0
            son_satir_sayisi = mevcut_satir_sayisi

        if adim % 20 == 0:
            print(f"  Adım {adim}: {mevcut_satir_sayisi} satır toplandı...")

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
    # Temizleme sonrası boş kalanları None yap
    df[col] = df[col].replace({'': None, '-': None, 'None': None})
    # Debug: hangi değerler geliyor
    print(f"[DEBUG] {col} örnek değerler:", df[col].dropna().head(5).tolist())
    print(f"[DEBUG] {col} boş kayıt sayısı:", df[col].isna().sum())

    return df


def main():
    # Sabit dosya adı — her çalışmada üzerine yazar, Git'e commit edilebilir
    dosya_adi_json = "analist_tavsiyeleri.json"

    with sync_playwright() as p:
        print("\nChromium başlatılıyor...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="tr-TR",
        )
        page = context.new_page()

        try:
            df = veriyi_cek(page)
        except Exception as e:
            print(f"HATA: {e}")
            import traceback
            traceback.print_exc()
            df = pd.DataFrame()
        finally:
            context.close()
            browser.close()

    if not df.empty:
        print(f"\nVeri JSON dosyasına yazılıyor: {dosya_adi_json}")
        temiz_df = df.astype(object).where(pd.notnull(df), None)
        with open(dosya_adi_json, 'w', encoding='utf-8') as f:
            json.dump(temiz_df.to_dict(orient='records'), f, ensure_ascii=False, indent=2)
        print(f"TAMAMLANDI: {len(df)} satır '{dosya_adi_json}' dosyasına kaydedildi.")
    else:
        print("\nKaydedilecek veri bulunamadı.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
