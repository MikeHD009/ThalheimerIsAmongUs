# =========================
# ROLLEN-KONFIGURATION
# Einzige Quelle der Wahrheit fuer main.py (Client) UND server.py (Server).
# Aus AmogususRollen.docx.
# =========================

TEAM_CREW = "Besatzung"
TEAM_IMPOSTOR = "Imposter"
TEAM_INDEPENDENT = "Eigenstaendig"

# Feste Reihenfolge -> Netzwerk-ID (Index in dieser Liste). NICHT umsortieren,
# sonst laufen alte/neue Clients auseinander. role_id 255 = kein Custom-Rolle (generisch).
ROLE_ORDER = [
    "monika", "steinermike", "martin", "stroblpeter", "evelyn", "laurin", "david", "noah", "vladimir",
    "poeschl_froeschl", "vogelscheicher", "pleschbergsteiger", "yoshi", "kaliyoga",
    "tappeihnachtsmann", "felix", "orakel", "raphi",
    "ramona",
]

NO_ROLE_ID = 255

ROLES = {
    "monika": {
        "name": "Monika Hogrieder",
        "team": TEAM_IMPOSTOR,
        "desc": "Platziere einmal pro Spiel eine Flagge bei dir. Danach wirst du alle paar Sekunden automatisch dorthin zurueckteleportiert.",
        "image": "Monika_Hogrieder.png",
    },
    "steinermike": {
        "name": "Steinermike",
        "team": TEAM_IMPOSTOR,
        "desc": "Sprengt andere Spieler in die Luft. Deine Opfer hinterlassen keine Leiche.",
        "image": "Steinermike.png",
    },
    "martin": {
        "name": "Martin",
        "team": TEAM_IMPOSTOR,
        "desc": "Hoehere Kill-Reichweite und hoeherer Kill-Cooldown, dafuer steckt danach eine Schere in der Leiche.",
        "image": "Martin.png",
    },
    "stroblpeter": {
        "name": "Stroblpeter",
        "team": TEAM_IMPOSTOR,
        "desc": "Merke dir einen Spieler. Nach 10s kannst du dich hinter ihn teleportieren und ihn damit killen.",
        "image": "Stroblpeter.png",
    },
    "evelyn": {
        "name": "Evelyn",
        "team": TEAM_IMPOSTOR,
        "desc": "Oeffne alle 30s fuer 20s die Fenster. Spieler die sich laenger als 5s in einem Fensterraum aufhalten, sterben.",
        "image": "Evelyn.png",
    },
    "laurin": {
        "name": "Laurin",
        "team": TEAM_IMPOSTOR,
        "desc": "Kann insgesamt 3 mal den Aufgaben-Fortschritt der Crew sabotieren.",
        "image": "Laurin.png",
        "max_uses": 3,
    },
    "david": {
        "name": "David",
        "team": TEAM_IMPOSTOR,
        "desc": "Markiere einen Spieler: seine naechste Chat-Nachricht wird fuer alle zu zufaellig gemischten Buchstaben.",
        "image": "David.png",
    },
    "noah": {
        "name": "Noah",
        "team": TEAM_IMPOSTOR,
        "desc": "Platziert eine Falle. Spieler die darauftreten sterben sofort.",
        "image": "Noah.png",
    },
    "vladimir": {
        "name": "Vladimir",
        "team": TEAM_IMPOSTOR,
        "desc": "Passiv: Getoetete Spieler koennen nicht sofort als Geist umherspuken und muessen erst ein Intro abwarten.",
        "image": "Vladimir.png",
    },
    "poeschl_froeschl": {
        "name": "Pöschl&Fröschl",
        "team": TEAM_CREW,
        "desc": "Fröschl spuert Leichen auf und zeigt dir die Richtung zur naechsten Leiche.",
        "image": "Pöschl&Fröschl.png",
    },
    "vogelscheicher": {
        "name": "Vogelscheicher",
        "team": TEAM_CREW,
        "desc": "Platziere eine Attrappe von dir und werde fuer kurze Zeit unsichtbar.",
        "image": "Vogelscheicher.png",
    },
    "pleschbergsteiger": {
        "name": "Pleschbergsteiger",
        "team": TEAM_CREW,
        "desc": "Gehe zum Geist eines anderen Spielers, um ihn einmalig wiederzubeleben.",
        "image": "Pleschbergsteiger.png",
        "max_uses": 1,
    },
    "yoshi": {
        "name": "Yoshi",
        "team": TEAM_CREW,
        "desc": "Finde bis zu 3 mal den Standard auf der Map. Jeder Fund erlaubt dir, die Rolle eines Spielers aufzudecken.",
        "image": "Yoshi.png",
        "max_uses": 3,
        "find_count": 3,
    },
    "kaliyoga": {
        "name": "Kaliyoga",
        "team": TEAM_CREW,
        "desc": "Kann einmal pro Spiel ein Bonus-Notfallmeeting herbeirufen, auch waehrend des eigenen Cooldowns.",
        "image": "Kaliyoga.png",
    },
    "tappeihnachtsmann": {
        "name": "Tappeihnachtsmann",
        "team": TEAM_CREW,
        "desc": "Finde bis zu 5 Geschenke auf der Map. Jedes gibt allen Spielern 10s Unsterblichkeit.",
        "image": "Tappeihnachtsmann.png",
        "max_uses": 5,
    },
    "felix": {
        "name": "Felix",
        "team": TEAM_CREW,
        "desc": "Kann normal Aufgaben erledigen, aber sie gelten immer als unerledigt und zaehlen nicht zum Fortschritt. Kann also eigentlich nichts.",
        "image": "Felix.png",
    },
    "orakel": {
        "name": "Orakel",
        "team": TEAM_CREW,
        "desc": "Das Orakel hat immer Recht: deine Stimme bei Abstimmungen zaehlt 3-fach.",
        "image": "Orakel.png",
    },
    "raphi": {
        "name": "Raphi",
        "team": TEAM_CREW,
        "desc": "Hat 10 eigene Aufgaben: auf der Map verstreute Pfandflaschen finden und sammeln.",
        "image": "Raphi.png",
    },
    "ramona": {
        "name": "Ramona (Boss)",
        "team": TEAM_INDEPENDENT,
        "desc": "Alle 10s kannst du die Unterschrift eines Spielers in deiner Naehe faelschen und ihm die Rechte nehmen. Haben alle Spieler keine Rechte mehr, stelle dich 10s lang ununterbrochen zum Regal beim Spawn, um zu gewinnen.",
        "image": "Ramona_(Boss).png",
    },
}

_ID_TO_KEY = {i: key for i, key in enumerate(ROLE_ORDER)}
_KEY_TO_ID = {key: i for i, key in enumerate(ROLE_ORDER)}


def role_id_of(key):
    if key is None:
        return NO_ROLE_ID
    return _KEY_TO_ID[key]


def role_key_of(role_id):
    if role_id == NO_ROLE_ID:
        return None
    return _ID_TO_KEY.get(role_id)


def team_of(key):
    if key is None:
        return None
    return ROLES[key]["team"]


def max_uses_of(key):
    if key is None:
        return None
    return ROLES[key].get("max_uses")


def keys_by_team(team):
    return [k for k in ROLE_ORDER if ROLES[k]["team"] == team]


def bitmask_of(enabled_keys):
    mask = 0
    for key in enabled_keys:
        mask |= (1 << role_id_of(key))
    return mask


def keys_from_bitmask(mask):
    keys = []
    for i, key in enumerate(ROLE_ORDER):
        if mask & (1 << i):
            keys.append(key)
    return keys
