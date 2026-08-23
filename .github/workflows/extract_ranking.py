#!/usr/bin/env python3
"""
Extractor mensual de ratings de billeteras digitales Perú
Big Data S.A.C. — Ranking Mensual de Billeteras Digitales Perú

Lee catalogo_billeteras_peru.csv (nombre, institucion, servicio, app_id_android, app_id_ios)
y genera dos archivos con la extracción del mes:
  - datos_YYYY-MM.csv       (Android / Google Play: rating, nº reseñas, instalaciones)
  - datos_YYYY-MM_ios.csv   (iOS / App Store: rating, nº reseñas)

Fuentes:
  - Android: librería no oficial `google-play-scraper` (lee el HTML público de Play Store).
  - iOS: API oficial y gratuita de Apple `itunes.apple.com/lookup`.

Regla del proyecto: nunca se inventa un dato. Si una app falla (id incorrecto, app
retirada de la tienda, error de red) se marca "s/d" en esa fila y el proceso continúa
con las demás — un solo fallo nunca detiene la corrida completa.

Uso:
  python extract_ranking.py                  # usa el mes actual (UTC)
  python extract_ranking.py --month 2026-08   # fuerza un mes (pruebas / backfill)
"""
import argparse
import csv
import datetime
import sys
import time

import requests
from google_play_scraper import app as gplay_app
from google_play_scraper.exceptions import NotFoundError

CATALOG_PATH = "catalogo_billeteras_peru.csv"
COUNTRY = "pe"
LANG = "es"
REQUEST_DELAY_SECONDS = 1.5  # pausa entre llamadas para no saturar las tiendas
ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"

ANDROID_FIELDS = ["nombre", "institucion", "servicio", "app_id_android",
                   "rating", "num_resenas", "instalaciones", "fecha_extraccion", "error"]
IOS_FIELDS = ["nombre", "institucion", "servicio", "app_id_ios",
              "rating", "num_resenas", "fecha_extraccion", "error"]


def load_catalog(path=CATALOG_PATH):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def is_empty(value):
    return not value or value.strip().lower() in ("", "s/d", "sd", "n/a")


def fetch_android(app_id):
    """Devuelve (rating, num_resenas, instalaciones, error) para un app_id de Android."""
    if is_empty(app_id):
        return None, None, None, "sin app_id"
    try:
        data = gplay_app(app_id, lang=LANG, country=COUNTRY)
        rating = data.get("score")
        reviews = data.get("ratings")       # nº total de calificaciones (no solo reseñas escritas)
        installs = data.get("installs")     # ej. "500,000+" — Google no publica cifra exacta
        return rating, reviews, installs, None
    except NotFoundError:
        return None, None, None, "app no encontrada (retirada de la tienda o app_id incorrecto)"
    except Exception as e:  # noqa: BLE001 - cualquier fallo se registra y no detiene la corrida
        return None, None, None, f"error: {e}"


def fetch_ios(app_id):
    """Devuelve (rating, num_resenas, error) para un app_id numérico de iTunes."""
    if is_empty(app_id):
        return None, None, "sin app_id"
    try:
        resp = requests.get(
            ITUNES_LOOKUP_URL,
            params={"id": app_id, "country": COUNTRY},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("resultCount"):
            return None, None, "app no encontrada en storefront PE"
        result = payload["results"][0]
        rating = result.get("averageUserRating")
        reviews = result.get("userRatingCount")
        return rating, reviews, None
    except Exception as e:  # noqa: BLE001
        return None, None, f"error: {e}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--month", default=None,
                         help="Mes a extraer en formato YYYY-MM (default: mes actual, UTC).")
    args = parser.parse_args()

    if args.month:
        try:
            datetime.datetime.strptime(args.month, "%Y-%m")
        except ValueError:
            sys.exit(f"--month debe tener formato YYYY-MM, recibido: {args.month}")
        month_str = args.month
    else:
        month_str = datetime.date.today().strftime("%Y-%m")

    catalog = load_catalog()
    fecha_extraccion = datetime.date.today().isoformat()

    android_rows = []
    ios_rows = []

    for i, row in enumerate(catalog, start=1):
        nombre = row["nombre"]
        print(f"[{i}/{len(catalog)}] {nombre}", flush=True)

        rating_a, reviews_a, installs_a, err_a = fetch_android(row.get("app_id_android", ""))
        android_rows.append({
            "nombre": nombre,
            "institucion": row.get("institucion", ""),
            "servicio": row.get("servicio", ""),
            "app_id_android": row.get("app_id_android", ""),
            "rating": rating_a if rating_a is not None else "s/d",
            "num_resenas": reviews_a if reviews_a is not None else "s/d",
            "instalaciones": installs_a if installs_a is not None else "s/d",
            "fecha_extraccion": fecha_extraccion,
            "error": err_a or "",
        })
        if err_a:
            print(f"    Android: {err_a}", flush=True)
        time.sleep(REQUEST_DELAY_SECONDS)

        rating_i, reviews_i, err_i = fetch_ios(row.get("app_id_ios", ""))
        ios_rows.append({
            "nombre": nombre,
            "institucion": row.get("institucion", ""),
            "servicio": row.get("servicio", ""),
            "app_id_ios": row.get("app_id_ios", ""),
            "rating": rating_i if rating_i is not None else "s/d",
            "num_resenas": reviews_i if reviews_i is not None else "s/d",
            "fecha_extraccion": fecha_extraccion,
            "error": err_i or "",
        })
        if err_i and not is_empty(row.get("app_id_ios", "")):
            print(f"    iOS: {err_i}", flush=True)
        time.sleep(REQUEST_DELAY_SECONDS)

    android_path = f"datos_{month_str}.csv"
    ios_path = f"datos_{month_str}_ios.csv"

    with open(android_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ANDROID_FIELDS)
        writer.writeheader()
        writer.writerows(android_rows)

    with open(ios_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=IOS_FIELDS)
        writer.writeheader()
        writer.writerows(ios_rows)

    fallos_android = sum(1 for r in android_rows if r["error"])
    fallos_ios = sum(1 for r in ios_rows if r["error"] and not is_empty(r["app_id_ios"]))
    print(f"\nListo: {android_path} ({len(android_rows)} apps, {fallos_android} con error/s-d)")
    print(f"Listo: {ios_path} ({len(ios_rows)} apps, {fallos_ios} con error/s-d)")


if __name__ == "__main__":
    main()
