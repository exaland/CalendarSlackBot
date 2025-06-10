# PlanningSlack

Un bot Slack pour la gestion des créneaux de rendez-vous, connecté à Google Calendar et Google Sheets.

## Fonctionnalités

- **/rdv** : Affiche les créneaux disponibles aujourd’hui et permet de réserver un rendez-vous via Slack.
- **/dispos** : Permet de modifier ses créneaux de disponibilité via un modal interactif.
- Synchronisation automatique avec Google Calendar pour éviter les conflits.
- Gestion des disponibilités via un Google Sheet partagé.

## Prérequis

- Python 3.8+
- Un espace de travail Slack avec les tokens nécessaires (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`)
- Un projet Google Cloud avec API Calendar et Sheets activées
- Un fichier de service Google (`service_account.json`)
- Un fichier d’authentification OAuth (`credentials.json`)
- Un Google Sheet nommé comme dans la variable d’environnement `SHEET_NAME`

## Installation

1. Clone ce dépôt :
   ```bash
   git clone <url-du-repo>
   cd planningslack
   ```

2. Installe les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

3. Place tes fichiers `service_account.json`, `credentials.json` et `.env` dans le dossier du projet.

4. Remplis le fichier `.env` :
   ```
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   CALENDAR_ID=...
   SHEET_NAME=Disponibilités
   ```

## Utilisation

Lance le bot :
```bash
python planning.py
```

Dans Slack :
- Tape `/rdv` pour voir et réserver un créneau.
- Tape `/dispos` pour modifier tes disponibilités.

## Structure du projet

- `planning.py` : Code principal du bot (Slack, Google Calendar, Google Sheets)
- `.env` : Variables d’environnement
- `service_account.json` : Clé de service Google
- `credentials.json` : Identifiants OAuth Google

## Personnalisation

- Modifie les horaires, la durée ou les jours dans le Google Sheet.
- Adapte les commandes Slack selon tes besoins.

## Licence

MIT

---

**Contact** : Alexandre MAGNIER