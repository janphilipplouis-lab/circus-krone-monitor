import json
import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import resend


KRONE_URL = (
    "https://www.circus-krone.com/winterspielzeit-muenchen/"
)

MUENCHEN_TICKET_URL = (
    "https://tickets.muenchenticket.de/shops/218/events/437156"
)

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
        "url": url,
        "text": text[:40000],
        "links": links[:500]
    }


def analyse(krone, ticket):
    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"]
    )

    prompt = f"""
Du bist ein sehr genauer Ticket-Monitor.

Prüfe ZWEI Webseiten und entscheide,
ob der Vorverkauf für die

WINTERSPIELZEIT 2026/27
IM CIRCUS KRONE-BAU MÜNCHEN

bereits gestartet ist.

ZIELVERANSTALTUNG:

Circus Krone-Bau
Marsstraße 43
80335 München

Premiere:
25. Dezember 2026

--------------------------------------------------
SEHR WICHTIG
--------------------------------------------------

NICHT relevant sind:

- Rosenheim
- Ingolstadt
- Weßling
- andere Städte
- Weihnachtscircusse im Zelt
- andere Circus-Krone-Veranstaltungen
- ältere Winterspielzeiten
- allgemeine Circus-Krone-Tickets

Eine Veranstaltung darf nur als Treffer gelten,
wenn sie eindeutig zum CIRCUS KRONE-BAU IN MÜNCHEN
gehört und die Winterspielzeit 2026/27 betrifft.

started=true darf nur zurückgegeben werden, wenn:

1. konkrete Tickets für München 2026/27 buchbar sind

ODER

2. Circus Krone ausdrücklich mitteilt,
   dass der Vorverkauf für die Münchner
   Winterspielzeit 2026/27 begonnen hat.

Eine bloße Ankündigung wie
"Informationen zum Vorverkaufsstart folgen im Herbst"
bedeutet eindeutig:

started=false

Wenn du auch nur geringfügig unsicher bist:

started=false

--------------------------------------------------
ERWARTETES ERGEBNIS
--------------------------------------------------

Antworte ausschließlich mit gültigem JSON:

{{
  "started": true oder false,
  "confidence": Zahl zwischen 0 und 1,
  "reason": "kurze Begründung",
  "ticket_url": "direkter Ticketlink oder leer"
}}

--------------------------------------------------
KRONE
--------------------------------------------------

{json.dumps(krone, ensure_ascii=False)}

--------------------------------------------------
MÜNCHEN TICKET
--------------------------------------------------

{json.dumps(ticket, ensure_ascii=False)}
"""

    response = client.responses.create(
        model=os.environ.get(
            "OPENAI_MODEL",
            "gpt-5.6"
        ),
        input=prompt
    )

    return json.loads(
        response.output_text
    )


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
            🎟️ DIREKT ZU DEN TICKETS
          </a>
        </p>
        """
    else:
        ticket_link = ""

    html = f"""
    <html>
      <body>
        <h2>🎪 Circus Krone – VORVERKAUF GESTARTET!</h2>

        <p>
          Der Vorverkauf für die
          <strong>Winterspielzeit 2026/27</strong>
          im Circus Krone-Bau München
          scheint gestartet zu sein.
        </p>

        <p>
          <strong>Premiere:</strong>
          25. Dezember 2026
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

        <hr>

        <p>
          Dies ist eine automatische Benachrichtigung
          des Circus-Krone-Monitors.
        </p>
      </body>
    </html>
    """

    params = {
        "from": "onboarding@resend.dev",
        "to": [os.environ["ALERT_EMAIL"]],
        "subject": "🎪 Circus Krone: Vorverkauf gestartet!",
        "html": html
    }

    email = resend.Emails.send(params)

    print("Alarm-E-Mail versendet:")
    print(email)


def main():
    print("================================")
    print("Circus Krone Ticket Monitor")
    print("================================")

    print()
    print("Prüfe Circus Krone...")

    krone = get_page(KRONE_URL)

    print("Prüfe München Ticket...")

    ticket = get_page(MUENCHEN_TICKET_URL)

    print("Analysiere beide Quellen...")

    result = analyse(
        krone,
        ticket
    )

    print()
    print("ERGEBNIS DER KI:")
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )

    print()

    if (
        result["started"]
        and result["confidence"] >= 0.90
    ):
        print("🚨 VORVERKAUF GESTARTET!")

        send_email(result)

        print(
            "Alarm-E-Mail wurde versendet."
        )

    else:
        print(
            "Noch kein sicherer Vorverkaufsstart."
        )
        print(
            "Keine E-Mail wird versendet."
        )

    print()
    print("Prüfung abgeschlossen.")


if __name__ == "__main__":
    main()
