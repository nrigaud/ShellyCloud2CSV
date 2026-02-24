import requests
import json
import csv
import argparse
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# ==========================================
# CONFIGURATION SHELLY CLOUD
# ==========================================
# Remplacez ces valeurs par vos propres informations dans le fichier .env
SERVER_URL = os.getenv("SERVER_URL", "")  # Sans le / à la fin
AUTH_KEY = os.getenv("AUTH_KEY", "")
DEVICE_ID = "349454718dfd"

# Vérifier que les variables requises sont présentes
if not SERVER_URL or not AUTH_KEY:
    raise ValueError("Erreur: AUTH_KEY et SERVER_URL doivent être définis dans le fichier .env")


def fetch_shelly_3em_data():
    """Récupère l'état instantané d'un Shelly 3EM."""
    url = f"{SERVER_URL}/device/status"
    payload = {"id": DEVICE_ID, "auth_key": AUTH_KEY}

    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        result = response.json()

        if not result.get("isok"):
            raise RuntimeError(f"Erreur Shelly Cloud: {result.get('errors', 'inconnu')}")

        device_status = result["data"]["device_status"]
        emeters = device_status.get("emeters", [])

        if len(emeters) < 1:
            raise RuntimeError("Aucun emeter trouvé dans la réponse.")

        timestamp = datetime.now(timezone.utc).isoformat()
        rows = []

        for i, em in enumerate(emeters, start=1):
            rows.append({
                "timestamp": timestamp,
                "phase": i,
                "power_W": em.get("power", 0.0),
                "voltage_V": em.get("voltage", 0.0),
                "total_Wh": em.get("total", 0.0),
            })

        return rows

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Erreur de connexion HTTP: {e}")
    except json.JSONDecodeError:
        raise RuntimeError("Réponse du serveur non JSON valide")


def export_to_csv(rows, filename="shelly_consumption.csv", append=True):
    """Exporte la liste de dictionnaires dans un fichier CSV dynamiquement."""
    if not rows:
        print("Aucune donnée à exporter.")
        return

    # CORRECTION : On déduit les colonnes automatiquement pour s'adapter à l'historique ou au direct
    fieldnames = list(rows[0].keys())

    write_header = True
    if append and os.path.exists(filename):
        write_header = False

    mode = "a" if append else "w"
    with open(filename, mode, newline="", encoding="utf-8") as csvfile:
        # extrasaction='ignore' évite les erreurs si des données inattendues s'y glissent
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        if write_header:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)


def fetch_shelly_history(start_iso, end_iso):
    """Récupère l'historique de consommation via la nouvelle API V2 de Shelly."""
    try:
        dt_from = datetime.fromisoformat(start_iso)
        dt_to = datetime.fromisoformat(end_iso)
        
        date_from_str = dt_from.strftime("%Y-%m-%d %H:%M:%S")
        date_to_str = dt_to.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        raise ValueError("Les dates doivent être au format ISO, ex: 2024-01-01T00:00:00")

    # Les nouveaux endpoints découverts pour la V2
    # On teste d'abord em-3p, et si ça échoue, on tente le générique
    endpoints = [
        f"{SERVER_URL}/v2/statistics/power-consumption/em-3p",
        f"{SERVER_URL}/v2/statistics/power-consumption"
    ]
    
    rows = []

    for channel in range(3): 
        print(f"Récupération de l'historique pour la phase {channel + 1}...")
        
        payload = {
            "id": DEVICE_ID,
            "auth_key": AUTH_KEY,
            "channel": channel,
            "date_range": "custom",
            "date_from": date_from_str,
            "date_to": date_to_str
        }

        success = False
        
        for url in endpoints:
            try:
                # Shelly V2 accepte parfois le POST form-encoded, mais beaucoup de requêtes API web utilisent désormais GET avec les paramètres URL
                # Nous testons un GET (très commun sur la V2 Cloud) :
                response = requests.get(url, params=payload)
                
                # Si erreur 405 (Méthode non autorisée) ou 404, on fallback sur l'autre URL de la liste
                if response.status_code != 200:
                    continue

                result = response.json()
                if result.get("isok"):
                    history = result.get("data", {}).get("history", [])
                    
                    for item in history:
                        rows.append({
                            "timestamp": item.get("datetime", ""),
                            "phase": channel + 1,
                            "energy_Wh": item.get("consumption", 0.0)
                        })
                    success = True
                    break # L'URL a fonctionné, on arrête de tester les autres endpoints pour ce canal
                    
            except requests.exceptions.RequestException:
                pass # Échec de la requête, on laisse la boucle tenter l'URL suivante
            except json.JSONDecodeError:
                pass 

        if not success:
            print(f"Erreur : Impossible de récupérer l'historique pour le canal {channel} avec les nouveaux endpoints V2.")

    # Trier la liste chronologiquement puis par phase
    rows.sort(key=lambda r: (r.get("timestamp", ""), r.get("phase", 0)))
    return rows


def main():
    parser = argparse.ArgumentParser(description="Récupère les données Shelly 3EM et exporte en CSV")
    parser.add_argument("--out", "-o", default="shelly_consumption.csv", help="Fichier CSV de sortie")
    parser.add_argument("--no-append", dest="append", action="store_false", help="Écrase le fichier au lieu d'ajouter")
    parser.add_argument("--print", dest="printout", action="store_true", help="Affiche les valeurs récupérées à l'écran")
    parser.add_argument("--from", dest="from_iso", help="Date de début (ISO) pour historique, ex: 2024-01-01T00:00")
    parser.add_argument("--to", dest="to_iso", help="Date de fin (ISO) pour historique, ex: 2024-01-02T00:00")

    args = parser.parse_args()

    if args.from_iso and args.to_iso:
        try:
            rows = fetch_shelly_history(args.from_iso, args.to_iso)
        except Exception as e:
            print(f"Erreur lors de la récupération de l'historique: {e}")
            return 1

        try:
            export_to_csv(rows, filename=args.out, append=args.append)
        except Exception as e:
            print(f"Erreur lors de l'export CSV: {e}")
            return 1

        if args.printout:
            print(f"Historique exporté vers {args.out} :")
            for r in rows:
                print(f"{r['timestamp']} - Phase {r['phase']}: {r['energy_Wh']} Wh")
        return 0

    # État actuel (live)
    try:
        rows = fetch_shelly_3em_data()
    except RuntimeError as e:
        print(f"Erreur: {e}")
        return 1

    try:
        export_to_csv(rows, filename=args.out, append=args.append)
    except Exception as e:
        print(f"Erreur lors de l'export CSV: {e}")
        return 1

    if args.printout:
        print(f"Données exportées vers {args.out} :")
        for r in rows:
            print(f"{r['timestamp']} - Phase {r['phase']}: {r['power_W']} W, {r['voltage_V']} V, {r['total_Wh']} Wh")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
