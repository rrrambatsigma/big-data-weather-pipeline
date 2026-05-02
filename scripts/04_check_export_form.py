from pathlib import Path

import requests
from bs4 import BeautifulSoup


URL = "https://app3.pertanian.go.id/eksim/eksporProvAsal.php"


def main():
    response = requests.get(URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    forms = soup.find_all("form")
    print(f"Jumlah form ditemukan: {len(forms)}")

    for form_index, form in enumerate(forms, start=1):
        print(f"\n=== FORM {form_index} ===")
        print("method:", form.get("method"))
        print("action:", form.get("action"))

        selects = form.find_all("select")
        for select in selects:
            print("\nSELECT")
            print("name:", select.get("name"))
            print("id:", select.get("id"))

            options = select.find_all("option")
            for option in options[:20]:
                print(
                    "  value:",
                    option.get("value"),
                    "| text:",
                    option.get_text(strip=True)
                )

        inputs = form.find_all("input")
        for input_tag in inputs:
            print("\nINPUT")
            print("type:", input_tag.get("type"))
            print("name:", input_tag.get("name"))
            print("value:", input_tag.get("value"))


if __name__ == "__main__":
    main()