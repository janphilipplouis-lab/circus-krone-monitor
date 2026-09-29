import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

KRONE_URL = "https://www.circus-krone.com/winterspielzeit-muenchen/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 Circus-Krone-Monitor/1.0"
}


def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    for element in soup(
        ["script", "style", "noscript", "svg"]
    ):
        element.decompose()

    text = soup.get_text(
        " ",
        strip=True
    )

    links = []

    for link in soup.find_all("a", href=True):
        links.append({
            "text": link.get_text(
                " ",
                strip=True
            ),
            "url": link["href"]
        })

    return {
        "text": text[:30000],
        "links": links[:300]
    }


def analyse(page):
    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"]
    )

    prompt = f"""
Du bist ein sehr genauer Ticket-Monitor.

Untersuche diese Webseite:

https://www.circus-krone.com/winterspielzeit-muenchen/

Die entscheidende Frage ist:

Hat der Vorverkauf für die
WINTERSPIELZEIT 2026/27
im CIRCUS KRONE-BAU IN MÜNCHEN
bereits begonnen?

Es geht ausschließlich um den
Circus Krone-Bau in München,
Marsstraße 43,
und die Winterspielzeit 2026/27
mit Premiere am 25. Dezember 2026.

NICHT berücksichtigen:
- Rosenheim
- Ingolstadt
- andere Weihnachtscircusse
- andere Städte
- ältere Winterspielzeiten
- allgemeine Circus-Krone-Tickets

Ein Vorverkauf gilt nur dann als gestartet,
wenn konkrete Tickets für München 2026/27
buchbar oder ausdrücklich zum Verkauf
freigegeben sind.

Eine bloße Programmankündigung bedeutet:
started = false.

Antworte ausschließlich mit diesem JSON:

{{
  "started": true oder false,
  "confidence": Zahl zwischen 0 und 1,
  "reason": "kurze Begründung",
  "ticket_url": "direkter Ticketlink oder leer"
}}

WEBSEITE:

{page}
"""

    response = client.responses.create(
        model="gpt-5.6-luna",
        input=prompt
    )

    return response.output_text


def main():
    print("================================")
    print("Circus Krone Ticket Monitor")
    print("================================")

    page = get_page(KRONE_URL)

    result = analyse(page)

    print()
    print("ERGEBNIS DER KI:")
    print(result)
    print()


if __name__ == "__main__":
    main()
