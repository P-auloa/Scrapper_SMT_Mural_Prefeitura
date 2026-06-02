#!/usr/bin/env python3
"""
Scrape PDFs from the Prefeitura Municipal de Santarém – Mural de Publicação.

Usage:
    pip install requests beautifulsoup4
    python C:/Users/paulo/scrape_santarem_pdfs.py

Author: OpenCode
"""

import os
import re
import pathlib
import sys
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---------- Configuration ----------
BASE_URL = "https://santarem.pa.gov.br"
LISTINGS_URL = urljoin(BASE_URL, "/mural-de-publicacoes")
MAX_PAGES = 1  # ✅ Defina quantas páginas quer varrer
KEYWORDS = [
    r"\bsmt\b",
    r"secretaria municipal de mobilidade e tr[âa]nsito",
    r"\bnov\b",
    r"gab\s*/\s*smt",
    r"nov\s*/\s*smt",
    r"n[úu]cleo de opera[çc][õo]es vi[áa]rias",
]

# Headers that mimic a common browser – helps with sites that block bots
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/112.0.0.0 Safari/537.36"
    )
}

# Desired output location – change this to wherever you want the PDFs stored
OUTPUT_DIR = pathlib.Path("PDFS")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR = OUTPUT_DIR
PDF_DIR.mkdir(exist_ok=True)

# ---------- Helpers ----------

def sanitize_filename(name: str, max_length: int = 80) -> str:
    """Remove/replace characters that are illegal in Windows file names."""
    bad_chars = r'<>:"/\\|?*'
    name = "".join(c if c not in bad_chars else "_" for c in name)
    # Strip trailing periods or spaces
    name = name.strip().strip(".")
    stem, _, ext = name.rpartition(".")
    if ext.lower() == "pdf":
        return stem[:max_length] + ".pdf"
    return name[:max_length]


def find_pdf_links(soup: BeautifulSoup) -> list[str]:
    """Return a list of absolute PDF URLs found inside a publication page."""
    urls = []
    # 1. <a href="...some.pdf">
    for a in soup.select('a[href$=".pdf"]'):
        urls.append(urljoin(BASE_URL, a["href"]))
    # 2. <embed src=".../some.pdf">
    for e in soup.select('embed[src$=".pdf"]'):
        urls.append(urljoin(BASE_URL, e["src"]))
    # 3. <object data="...some.pdf">
    for o in soup.select('object[data$=".pdf"], object > param[name="src"]'):
        data = o.get("data") or o.get("src")
        if data:
            urls.append(urljoin(BASE_URL, data))
    return urls


# ---------- Main scraping routine ----------

def scrape():
    publication_links = []

    for page in range(1, MAX_PAGES + 1):
        # Página 1 não precisa de ?page=1 em alguns sites, mas funciona assim também
        url = f"{LISTINGS_URL}?page={page}"
        print(f"Fetching page {page}: {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except Exception as exc:
            print(f"Failed to get page {page}: {exc}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        keyword_regex = re.compile(r"|".join(KEYWORDS), re.I)

        found = 0
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if not text:
                continue
            if keyword_regex.search(text) or keyword_regex.search(a["href"]):
                full_url = urljoin(BASE_URL, a["href"])
                publication_links.append((text, full_url))
                found += 1

        print(f"  → Found {found} candidates on page {page}.")

    print(f"\nTotal: {len(publication_links)} candidate publications.")

    for title, pub_url in publication_links:
        print(f"\nProcessing: {title}")
        try:
            pub_resp = requests.get(pub_url, headers=HEADERS, timeout=30)
            pub_resp.raise_for_status()
        except Exception as exc:
            print(f"  → Failed to fetch publication page: {exc}")
            continue
        pub_soup = BeautifulSoup(pub_resp.text, "html.parser")
        pdf_urls = find_pdf_links(pub_soup)
        if not pdf_urls:
            print("  → No PDF link found in this page.")
            continue
        for pdf_url in pdf_urls:
            pdf_original_name = os.path.basename(urlparse(pdf_url).path)
            pdf_original_stem, _, pdf_ext = pdf_original_name.rpartition(".")
            title_truncated = sanitize_filename(title, max_length=80)
            pdf_name_safe: str = f"{title_truncated}__{pdf_original_stem}.{pdf_ext}"

            pdf_path = PDF_DIR / pdf_name_safe

            if pdf_path.exists():
                print(f"  → Já existe, pulando: {pdf_name_safe}")
                continue
            
            print(f"  → Downloading PDF: {pdf_url}")
            try:
                pdf_resp = requests.get(pdf_url, headers=HEADERS, timeout=60)
                pdf_resp.raise_for_status()
                with open(pdf_path, "wb") as f:
                    f.write(pdf_resp.content)
                print(f"    → Saved to {pdf_path}")
            except Exception as exc:
                print(f"    → Failed to download PDF: {exc}")


# ---------- Entry point ----------
if __name__ == "__main__":
    scrape()
