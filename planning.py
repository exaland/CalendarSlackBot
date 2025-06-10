import datetime
import pytz
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account

load_dotenv()
# -------- CONFIGURATION --------

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
CALENDAR_ID = os.getenv("CALENDAR_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "Disponibilités")
SERVICE_ACCOUNT_FILE = "service_account.json"

SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
SHEET_ID = os.getenv("SHEET_ID", "1yNTdEt5607pVyrrsp7Tiy8Vu1aOkZg-ucA6yr3kN1XA")  # ID Google Sheet

creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
timezone = pytz.timezone('Europe/Paris')
TIMEZONE = "Europe/Paris"

calendar_service = build("calendar", "v3", credentials=creds)
sheet_client = gspread.authorize(creds)
sheet = sheet_client.open_by_key(SHEET_ID).sheet1
app = App(token=SLACK_BOT_TOKEN)

# -- Google Sheets
def load_sheet_rows():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    return sheet.get_all_records()

def get_slots_for_day(day_name, rows):
    slots = []
    for row in rows:
        if row['Jour'].lower() != day_name.lower() or row['Actif'].strip().lower() != 'oui':
            continue
        try:
            start_time = datetime.datetime.strptime(row['Heure début'], '%H:%M').time()
            end_time = datetime.datetime.strptime(row['Heure fin'], '%H:%M').time()
            duration = int(row['Durée créneau (min)'])
        except:
            continue
        day = datetime.datetime.now()
        while day.strftime('%A').lower() != day_name.lower():
            day += datetime.timedelta(days=1)
        current = datetime.datetime.combine(day.date(), start_time)
        end = datetime.datetime.combine(day.date(), end_time)
        while current + datetime.timedelta(minutes=duration) <= end:
            slots.append((current, current + datetime.timedelta(minutes=duration)))
            current += datetime.timedelta(minutes=duration)
    return slots

# -- Google Calendar
def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    return build("calendar", "v3", credentials=creds)

def is_slot_free(service, start, end):
    # Convertir en fuseau horaire et en ISO 8601
    start_utc = start.astimezone(pytz.UTC).isoformat()
    end_utc = end.astimezone(pytz.UTC).isoformat()

    events = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_utc,
        timeMax=end_utc,
        singleEvents=True
    ).execute().get("items", [])
    return len(events) == 0

@app.action("book_meeting")
def handle_booking(ack, body, respond):
    ack()
    user = body["user"]["username"]
    value = body["actions"][0]["value"]
    start_str, end_str = value.split('|')
    start = datetime.datetime.fromisoformat(start_str)
    end = datetime.datetime.fromisoformat(end_str)
    service = get_calendar_service()

    event = {
        "summary": f"Rendez-vous avec {user}",
        "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Paris"},
        "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Paris"},
    }

    service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    respond(f"✅ Rendez-vous réservé : {start.strftime('%H:%M')} → {end.strftime('%H:%M')}")


@app.command("/dispos")
def open_availability_modal(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "update_availability",
            "title": {"type": "plain_text", "text": "Modifier mes créneaux"},
            "submit": {"type": "plain_text", "text": "Mettre à jour"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "day_block",
                    "element": {
                        "type": "static_select",
                        "action_id": "day",
                        "placeholder": {"type": "plain_text", "text": "Jour"},
                        "options": [
                            {"text": {"type": "plain_text", "text": j}, "value": j}
                            for j in ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
                        ],
                    },
                    "label": {"type": "plain_text", "text": "Jour de la semaine"},
                },
                {
                "type": "input",
                "block_id": "start_time_block",
                "label": {"type": "plain_text", "text": "Heure de début"},
                "element": {
                    "type": "static_select",
                    "action_id": "start_time_input",
                    "placeholder": {"type": "plain_text", "text": "Choisis une heure"},
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "09:00"},
                            "value": "09:00"
                        },
                        {
                            "text": {"type": "plain_text", "text": "10:00"},
                            "value": "10:00"
                        },
                        {
                            "text": {"type": "plain_text", "text": "11:00"},
                            "value": "11:00"
                        },
                        {
                            "text": {"type": "plain_text", "text": "14:00"},
                            "value": "14:00"
                        },
                        {
                            "text": {"type": "plain_text", "text": "15:00"},
                            "value": "15:00"
                        },
                        {
                            "text": {"type": "plain_text", "text": "16:00"},
                            "value": "16:00"
                        }
                    ]
                }
            },{
                    "type": "input",
                    "block_id": "end_time_block",
                    "label": {"type": "plain_text", "text": "Heure de début"},
                    "element": {
                        "type": "static_select",
                        "action_id": "end_time_input",
                        "placeholder": {"type": "plain_text", "text": "Choisis une heure"},
                        "options": [
                            {
                                "text": {"type": "plain_text", "text": "09:00"},
                                "value": "09:00"
                            },
                            {
                                "text": {"type": "plain_text", "text": "10:00"},
                                "value": "10:00"
                            },
                            {
                                "text": {"type": "plain_text", "text": "11:00"},
                                "value": "11:00"
                            },
                            {
                                "text": {"type": "plain_text", "text": "14:00"},
                                "value": "14:00"
                            },
                            {
                                "text": {"type": "plain_text", "text": "15:00"},
                                "value": "15:00"
                            },
                            {
                                "text": {"type": "plain_text", "text": "16:00"},
                                "value": "16:00"
                            }
                        ]
                    }
                },
                {
                    "type": "input",
                    "block_id": "duration_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "duration",
                        "placeholder": {"type": "plain_text", "text": "ex: 30"},
                    },
                    "label": {"type": "plain_text", "text": "Durée des créneaux (en minutes)"},
                },
                {
                    "type": "input",
                    "block_id": "active_block",
                    "element": {
                        "type": "static_select",
                        "action_id": "active",
                        "options": [
                            {"text": {"type": "plain_text", "text": "Oui"}, "value": "oui"},
                            {"text": {"type": "plain_text", "text": "Non"}, "value": "non"},
                        ],
                    },
                    "label": {"type": "plain_text", "text": "Activer ?"},
                },
            ],
        }
    )
    
    
@app.view("update_availability")
def handle_submission(ack, body, view, respond):
    ack()

    values = view["state"]["values"]
    jour = values["day_block"]["day"]["selected_option"]["value"]
    heure_debut = view["state"]["values"]["start_time_block"]["start_time_input"]["selected_option"]["value"]
    heure_fin = view["state"]["values"]["end_time_block"]["end_time_input"]["selected_option"]["value"]
    duree = values["duration_block"]["duration"]["value"]
    actif = values["active_block"]["active"]["selected_option"]["value"]

    # Chargement + modification du Google Sheet
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    rows = sheet.get_all_records()

    updated = False
    for idx, row in enumerate(rows, start=2):  # Ligne 1 = header
        if row["Jour"].lower() == jour.lower():
            sheet.update(f"B{idx}", heure_debut)
            sheet.update(f"C{idx}", heure_fin)
            sheet.update(f"D{idx}", duree)
            sheet.update(f"E{idx}", actif)
            updated = True
            break

    if not updated:
        # Ajouter une nouvelle ligne
        sheet.append_row([jour, heure_debut, heure_fin, duree, actif])

    respond(f"✅ Créneaux mis à jour pour *{jour}* : {heure_debut} → {heure_fin} ({duree}min) / Actif : {actif}")


# -------- AUTHENTIFICATION GOOGLE --------
def get_calendar_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

# -------- BOT SLACK --------

# Commande Slack : /rdv
@app.command("/rdv")
def handle_rdv(ack, body, client):
    ack()
    rows = sheet.get_all_records()

    blocks = []
    for idx, row in enumerate(rows):
        if row["Disponible"] == "✅":
            date = row["Date"]
            time = row["Heure"]
            duration = int(row["Durée"])
            label = f"{date} - {time} ({duration} min)"
            value = f"{idx}|{date}|{time}|{duration}"
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{label}*"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Réserver"},
                    "action_id": "book_slot",
                    "value": value
                }
            })

    if not blocks:
        client.chat_postMessage(channel=body["user_id"], text="Aucun créneau disponible.")
        return

    client.chat_postMessage(
        channel=body["user_id"],
        text="Voici les créneaux disponibles :",
        blocks=blocks
    )

@app.action("book_slot")
def handle_booking(ack, body, client):
    ack()
    user = body["user"]["username"]
    value = body["actions"][0]["value"]
    row_idx, date_str, time_str, duration = value.split("|")
    row_idx = int(row_idx)
    duration = int(duration)

    start = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    end = start + datetime.timedelta(minutes=duration)

    start_iso = start.isoformat()
    end_iso = end.isoformat()

    # Vérifie disponibilité
    events = calendar_service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat() + "Z",
        timeMax=end.isoformat() + "Z",
        singleEvents=True
    ).execute()
    if events.get("items"):
        client.chat_postMessage(channel=body["user"]["id"], text="❌ Ce créneau est déjà réservé.")
        return

    # Réserve dans Calendar
    calendar_service.events().insert(calendarId=CALENDAR_ID, body={
        "summary": f"RDV avec {user}",
        "start": {"dateTime": start_iso, "timeZone": TIMEZONE},
        "end": {"dateTime": end_iso, "timeZone": TIMEZONE},
    }).execute()

    # Marque comme réservé dans la Sheet
    sheet.update_cell(row_idx + 2, 4, "❌")  # ligne +2 (en-tête + index 0)

    # Confirmation
    client.chat_postMessage(channel=body["user"]["id"],
                            text=f"✅ Rendez-vous confirmé : {date_str} à {time_str} pour {duration} min.")

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


# Interactivité bouton
@app.action("book_meeting")
def handle_booking(ack, body, respond):
    ack()
    user = body['user']['username']
    value = body['actions'][0]['value']
    start, end = value.split('|')

    service = get_calendar_service()

    event = {
        'summary': f'Rendez-vous avec {user}',
        'start': {'dateTime': start, 'timeZone': 'Europe/Paris'},
        'end': {'dateTime': end, 'timeZone': 'Europe/Paris'},
    }

    service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    
    print("response agenda :", t)

    respond(f"✅ Rendez-vous réservé de {start[11:16]} à {end[11:16]}")

# Lancer le bot
if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
