import json
import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import resend

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
        href = link.get("href", "")

        if href:
            links.append({
                "text": link.get_text(
                    " ",
                    strip=True
                ),
                "url": href
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

Prüfe die folgende Webseite:

{KRONE_URL}

Die einzige relevante Frage lautet:

Hat der Vorverkauf für die
WINTERSPIELZEIT 2026/27
im CIRCUS KRONE-BAU IN MÜNCHEN
bereits begonnen?

Es geht ausschließlich um:

Circus Krone-Bau
Marsstraße 43
80335 München

Winterspielzeit 2026/27
Premiere: 25. Dezember 2026

NICHT relevant sind:

- Rosenheim
- Ingolstadt
- andere Städte
- andere Weihnachtscircusse
- Veranstaltungen im Circus-Krone-Zelt
- ältere Winterspielzeiten
- allgemeine Tickets
- Programmankündigungen ohne buchbare Tickets

started darf nur true sein, wenn konkrete Tickets
für Vorstellungen im Circus Krone-Bau München
2026/27 tatsächlich erhältlich bzw. buchbar sind
oder ausdrücklich mitgeteilt wird, dass der Vorverkauf
für diese Veranstaltung begonnen hat.

Wenn nur angekündigt wird, dass Informationen zum
Vorverkaufsstart später folgen, muss started=false sein.

Wenn du nicht sicher bist, muss started=false sein.

Antworte ausschließlich mit gültigem JSON:

{{
  "started": true oder false,
  "confidence": Zahl zwischen 0 und 1,
  "reason": "kurze Begründung",
  "ticket_url": "direkter Ticketlink oder leer"
}}

WEBSEITENINHALT:

{json.dumps(page, ensure_ascii=False)}
"""

    response = client.responses.create(
        model=os.environ.get(
            "OPENAI_MODEL",
            "gpt-5.6"
        ),
        input=prompt
    )

    return json.loads(response.output_text)


def send_email(result):
    resend.api_key = os.environ["RESEND_API_KEY"]

    ticket_url = result.get(
        "ticket_url",
        ""
    )

    if ticket_url:
        ticket_link = f"""
        <p>
          <a href="{ticket_url}">
            🎟️ Direkt zu den Tickets
          </a>
        </p>
        """
    else:
        ticket_link = ""

    html = f"""
    <html>
      <body>
        <h2>🎪 Circus Krone – Vorverkauf gestartet!</h2>

        <p>
          Der Vorverkauf für die
          <strong>Winterspielzeit 2026/27</strong>
          im Circus Krone-Bau München scheint gestartet zu sein.
        </p>

        <p>
          <strong>Premiere:</strong> 25. Dezember 2026
        </p>

        <p>
          <strong>KI-Einschätzung:</strong><br>
          {result["reason"]}
        </p>

        <p>
          <strong>Konfidenz:</strong>
          {result["confidence"]:.0%}
        </p>

        {ticket_link}

        <p>
          Bitte die Verfügbarkeit sicherheitshalber
          direkt beim Anbieter überprüfen.
        </p>
      </body>
    </html>
    """

    params = {
        "from": "Circus Krone Monitor <onboarding@resend.dev>",
        "to": [os.environ["ALERT_EMAIL"]],
        "subject": "🎪 Circus Krone: Vorverkauf gestartet!",
        "html": html
    }

    email = resend.Emails.send(params)

    print("E-Mail erfolgreich versendet:")
    print(email)


def main():
    print("================================")
    print("Circus Krone Ticket Monitor")
    print("================================")

    page = get_page(KRONE_URL)

    result = analyse(page)

    print()
    print("ERGEBNIS DER KI:")
    print(json.dumps(
        result,
        ensure_ascii=False,
        indent=2
    ))
print()

if result["started"]:
    print("🚨 VORVERKAUF GESTARTET!")

    send_email(result)

    print("Alarm-E-Mail wurde versendet.")
else:
    print("Noch kein Vorverkaufsstart. Keine E-Mail.")

print()
print("Prüfung abgeschlossen.")



if __name__ == "__main__":
    main()
