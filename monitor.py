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
    "https://www.muenchenticket.de/event/"
    "circus-krone-winterprogramm-2026-27-39357/"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    )
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
        label = link.get_text(
            " ",
            strip=True
        )

        if href:
            links.append({
                "text": label,
                "url": href
            })

    return {
        "url": url,
        "text": text[:50000],
        "links": links[:500]
    }


def definitely_not_available(page):
    text = page["text"].lower()

    markers = [
        "nicht verfügbar",
        "noch nicht verfügbar",
        "nicht buchbar",
        "noch nicht buchbar",
        "vorverkauf noch nicht gestartet",
        "vorverkauf startet",
        "vorverkaufsstart folgt",
    ]

    found = [
        marker
        for marker in markers
        if marker in text
    ]

    if found:
        print(
            "München Ticket enthält "
            "Nicht-Verfügbar-Hinweis:"
        )

        for marker in found:
            print(f"  - {marker}")

        return True

    return False


def has_real_ticket_action(page):
    """
    Konservative technische Prüfung.

    Wir suchen nach Hinweisen, dass tatsächlich
    eine Buchungsaktion angeboten wird.
    """

    text = page["text"].lower()

    positive_markers = [
        "ticket kaufen",
        "tickets kaufen",
        "jetzt buchen",
        "tickets buchen",
        "platz auswählen",
        "plätze auswählen",
        "kaufen",
        "buchen",
    ]

    negative_markers = [
        "nicht verfügbar",
        "noch nicht verfügbar",
        "nicht buchbar",
    ]

    if any(
        marker in text
        for marker in negative_markers
    ):
        return False

    return any(
        marker in text
        for marker in positive_markers
    )


def analyse_with_ai(krone, ticket):
    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"]
    )

    prompt = f"""
Du bist eine zweite, sehr konservative Kontrolle
für einen Ticket-Monitor.

Gesucht wird ausschließlich:

CIRCUS KRONE-BAU MÜNCHEN
WINTERSPIELZEIT 2026/27
Premiere 25.12.2026

Eine Veranstaltungsliste allein bedeutet NICHT,
dass der Vorverkauf gestartet ist.

Wenn München Ticket "Nicht verfügbar",
"nicht buchbar" oder eine sinngemäße Aussage
zeigt, MUSS started=false sein.

started=true nur dann, wenn konkrete Tickets
tatsächlich gekauft/gebucht werden können.

Wenn Zweifel bestehen: false.

Antworte ausschließlich als JSON:

{{
  "started": true oder false,
  "confidence": 0.0 bis 1.0,
  "reason": "kurze Begründung",
  "ticket_url": "URL oder leer"
}}

CIRCUS-KRONE-SEITE:

{json.dumps(krone, ensure_ascii=False)}

MÜNCHEN-TICKET-SEITE:

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
        MUENCHEN_TICKET_URL
    )

    html = f"""
    <html>
      <body>
        <h2>🎪 Circus Krone – Vorverkauf gestartet!</h2>

        <p>
          Der Vorverkauf für die
          <strong>Winterspielzeit 2026/27</strong>
          im Circus Krone-Bau München
          scheint tatsächlich buchbar zu sein.
        </p>

        <p>
          <strong>Premiere:</strong>
          25. Dezember 2026
        </p>

        <p>
          <strong>Direkt zu den Tickets:</strong><br>
          <a href="{ticket_url}">
            Tickets öffnen
          </a>
        </p>

        <p>
          <strong>Kontrolle:</strong><br>
          {result["reason"]}
        </p>

        <p>
          KI-Konfidenz:
          {result["confidence"]:.0%}
        </p>
      </body>
    </html>
    """

    params = {
        "from": "onboarding@resend.dev",
        "to": [os.environ["ALERT_EMAIL"]],
        "subject": (
            "🎪 Circus Krone: Vorverkauf gestartet!"
        ),
        "html": html
    }

    email = resend.Emails.send(params)

    print(
        "Alarm-E-Mail versendet:"
    )
    print(email)


def main():
    print("================================")
    print("Circus Krone Ticket Monitor")
    print("================================")

    print()
    print("Prüfe Circus Krone...")

    krone = get_page(
        KRONE_URL
    )

    print("Prüfe München Ticket...")

    ticket = get_page(
        MUENCHEN_TICKET_URL
    )

    # ------------------------------------------------
    # 1. HARTE NEGATIVPRÜFUNG
    # ------------------------------------------------

    unavailable = definitely_not_available(
        ticket
    )

    if unavailable:
        print()
        print(
            "❌ Tickets sind laut München Ticket "
            "nicht verfügbar."
        )
        print(
            "Keine KI-Alarmprüfung erforderlich."
        )
        print()
        print("Prüfung abgeschlossen.")
        return

    # ------------------------------------------------
    # 2. TECHNISCHE POSITIVPRÜFUNG
    # ------------------------------------------------

    ticket_action = has_real_ticket_action(
        ticket
    )

    print()
    print(
        "Technische Buchungsprüfung:",
        ticket_action
    )

    # ------------------------------------------------
    # 3. KI-ZWEITMEINUNG
    # ------------------------------------------------

    print()
    print("Analysiere beide Quellen mit KI...")

    result = analyse_with_ai(
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

    # ------------------------------------------------
    # 4. ALARM NUR BEI DOPPELTER BESTÄTIGUNG
    # ------------------------------------------------

    confirmed = (
        ticket_action
        and result.get("started") is True
        and result.get("confidence", 0) >= 0.90
    )

    print()

    if confirmed:
        print(
            "🚨 VORVERKAUF TECHNISCH + "
            "MIT KI BESTÄTIGT!"
        )

        send_email(result)

        print(
            "Alarm-E-Mail wurde versendet."
        )

    else:
        print(
            "❌ Kein ausreichend bestätigter "
            "Vorverkaufsstart."
        )
        print(
            "Keine E-Mail wird versendet."
        )

    print()
    print("Prüfung abgeschlossen.")


if __name__ == "__main__":
    main()
