import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from google.oauth2 import service_account
from googleapiclient.discovery import build
import gspread

# -- CONFIGURATION --
SLACK_BOT_TOKEN = "xoxb-..."
SLACK_APP_TOKEN = "xapp-..."
CALENDAR_ID = "tonemail@gmail.com"
SHEET_ID = "1a2B3cD4e5F6GhIjKlMnOpQrStUvWxYz"  # ID Google Sheet
SERVICE_ACCOUNT_FILE = "service_account.json"
TIMEZONE = "Europe/Paris"

# -- INIT GOOGLE APIs --
SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/spreadsheets"]
creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

calendar_service = build("calendar", "v3", credentials=creds)
sheet_client = gspread.authorize(creds)
sheet = sheet_client.open_by_key(SHEET_ID).sheet1

# -- INIT SLACK APP --
app = App(token=SLACK_BOT_TOKEN)

@app.command("/rdv")
def open_modal(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "rdv_submit",
            "title": {"type": "plain_text", "text": "Prendre un RDV"},
            "submit": {"type": "plain_text", "text": "Confirmer"},
            "close": {"type": "plain_text", "text": "Annuler"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "start_time_block",
                    "label": {"type": "plain_text", "text": "Heure de début"},
                    "element": {
                        "type": "static_select",
                        "action_id": "start_time_input",
                        "placeholder": {"type": "plain_text", "text": "Choisis une heure"},
                        "options": [
                            {"text": {"type": "plain_text", "text": f"{h:02d}:00"}, "value": f"{h:02d}:00"}
                            for h in range(9, 18)
                        ]
                    }
                },
                {
                    "type": "input",
                    "block_id": "duration_block",
                    "label": {"type": "plain_text", "text": "Durée"},
                    "element": {
                        "type": "static_select",
                        "action_id": "duration_input",
                        "placeholder": {"type": "plain_text", "text": "Choisis la durée"},
                        "options": [
                            {"text": {"type": "plain_text", "text": "30 min"}, "value": "30"},
                            {"text": {"type": "plain_text", "text": "1h"}, "value": "60"},
                            {"text": {"type": "plain_text", "text": "1h30"}, "value": "90"}
                        ]
                    }
                },
                {
                    "type": "input",
                    "block_id": "subject_block",
                    "label": {"type": "plain_text", "text": "Sujet"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "subject_input",
                        "placeholder": {"type": "plain_text", "text": "Ex: entretien, démo..."}
                    }
                }
            ]
        }
    )

@app.view("rdv_submit")
def handle_submission(ack, body, view, logger, client):
    ack()
    user = body["user"]["username"]
    values = view["state"]["values"]

    start_hour = values["start_time_block"]["start_time_input"]["selected_option"]["value"]
    duration_min = int(values["duration_block"]["duration_input"]["selected_option"]["value"])
    subject = values["subject_block"]["subject_input"]["value"]

    now = datetime.datetime.now()
    start_dt = datetime.datetime.combine(now.date(), datetime.datetime.strptime(start_hour, "%H:%M").time())
    end_dt = start_dt + datetime.timedelta(minutes=duration_min)

    start_str = start_dt.isoformat()
    end_str = end_dt.isoformat()

    # 🔍 Vérifier si un événement existe déjà
    events = calendar_service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_str,
        timeMax=end_str,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    if events.get("items"):
        client.chat_postMessage(channel=body["user"]["id"], text="❌ Ce créneau est déjà occupé.")
        return

    # ✅ Créer l'événement dans Calendar
    event = {
        "summary": f"{subject} - {user}",
        "start": {"dateTime": start_str, "timeZone": TIMEZONE},
        "end": {"dateTime": end_str, "timeZone": TIMEZONE},
    }
    calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

    # 🧾 Ajouter à Google Sheet
    sheet.append_row([str(now.date()), start_hour, f"{duration_min} min", subject, user])

    # ✅ Confirmer
    client.chat_postMessage(channel=body["user"]["id"], text=f"✅ RDV confirmé à {start_hour} pour {duration_min} min.")

# Lancement
if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
