import datetime
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

load_dotenv()
# -------- CONFIGURATION --------

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
CALENDAR_ID = os.getenv("CALENDAR_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "Disponibilités")
SERVICE_ACCOUNT_FILE = "service_account.json"

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = "cb8244901b35d460f7881d7d920ee84204e4348cd682dabf860690df3fe6793e@group.calendar.google.com"  # ou autre ID d'agenda
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
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
    events = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat() + 'Z',
        timeMax=end.isoformat() + 'Z',
        singleEvents=True
    ).execute().get("items", [])
    return len(events) == 0

@app.command("/rdv")
def handle_rdv(ack, body, respond):
    ack()
    user = body["user_name"]
    rows = load_sheet_rows()
    today = datetime.datetime.now().strftime('%A')
    slots = get_slots_for_day(today, rows)
    service = get_calendar_service()
    
    available = []
    for start, end in slots:
        if is_slot_free(service, start, end):
            available.append((start, end))
    if not available:
        respond("Aucun créneau libre aujourd’hui 😕")
        return

    blocks = []
    for i, (start, end) in enumerate(available[:3]):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Créneau {i+1}* : {start.strftime('%H:%M')} - {end.strftime('%H:%M')}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Réserver"},
                "value": f"{start.isoformat()}|{end.isoformat()}",
                "action_id": "book_meeting"
            }
        })

    respond(
        text="Voici les créneaux disponibles aujourd’hui :",
        blocks=blocks
    )

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
def handle_rdv(ack, body, respond):
    ack()
    user = body["user_name"]

    service = get_calendar_service()

    # Chercher les événements déjà pris aujourd’hui
    now = datetime.datetime.utcnow()
    start_time = now.isoformat() + 'Z'
    end_time = (now + datetime.timedelta(days=1)).isoformat() + 'Z'

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time,
        timeMax=end_time,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])

    busy_times = [
        (e['start']['dateTime'], e['end']['dateTime'])
        for e in events if 'dateTime' in e['start']
    ]

    # Créneaux entre 9h et 17h
    free_slots = []
    today = now.date()
    for hour in range(9, 17):
        slot_start = datetime.datetime.combine(today, datetime.time(hour, 0)).isoformat() + 'Z'
        slot_end = datetime.datetime.combine(today, datetime.time(hour + 1, 0)).isoformat() + 'Z'
        if not any(bs <= slot_start < be for bs, be in busy_times):
            free_slots.append((slot_start, slot_end))

    if not free_slots:
        respond("Désolé, aucun créneau libre aujourd’hui 😕")
        return

    # Proposer des boutons cliquables avec action_id
    blocks = []
    for i, (start, end) in enumerate(free_slots[:3]):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Créneau {i+1}* : {start[11:16]} - {end[11:16]}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Réserver"},
                "action_id": "book_meeting",  # <-- Action ID REQUIS ici
                "value": f"{start}|{end}"
            }
        })

    respond(
        text="Voici mes créneaux libres aujourd’hui :",
        blocks=blocks
    )

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

    respond(f"✅ Rendez-vous réservé de {start[11:16]} à {end[11:16]}")

# Lancer le bot
if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
