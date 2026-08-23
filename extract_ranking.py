#!/usr/bin/env python3
"""
Extractor mensual de ratings de billeteras digitales Perú
Big Data S.A.C. — Ranking Mensual de Billeteras Digitales Perú

Lee catalogo_billeteras_peru.csv (nombre, institucion, servicio, app_id_android, app_id_ios)
y genera cuatro archivos con la extracción del mes:
  - datos_YYYY-MM.csv            (Android / Google Play: rating, reseñas, instalaciones,
                                   categoría, desarrollador, versión publicada, fechas de
                                   lanzamiento/actualización, precio)
  - datos_YYYY-MM_ios.csv        (iOS / App Store: mismos campos donde aplica)
  - iconos_YYYY-MM.json          (icono de cada app en base64, listo para incrustar en el
                                   dashboard sin depender de cargar imágenes externas)
  - calidad_servicio_YYYY-MM.csv (Android: de las reseñas de 1★ más recientes, cuántas tienen
                                   respuesta del desarrollador y en cuántos días — insumo para
                                   la sección PRO "Calidad de Servicio")

Fuentes:
  - Android: librería no oficial `google-play-scraper` (lee el HTML público de Play Store),
    tanto para la ficha de la app (`app`) como para las reseñas (`reviews`).
  - iOS: API oficial y gratuita de Apple `itunes.apple.com/lookup`. Apple no expone
    públicamente las respuestas de los desarrolladores a reseñas de apps de terceros (solo el
    propio dueño de la app puede verlas vía App Store Connect), así que "Calidad de Servicio"
    solo existe para Android.

Regla del proyecto: nunca se inventa un dato. Si una app falla (id incorrecto, app
retirada de la tienda, error de red) se marca "s/d" en esa fila y el proceso continúa
con las demás — un solo fallo nunca detiene la corrida completa. Lo mismo aplica al
icono: si no se puede descargar o procesar, esa app simplemente no aparece en el JSON
de iconos y el dashboard usa un avatar de respaldo.

Uso:
  python extract_ranking.py                  # usa el mes actual (UTC)
  python extract_ranking.py --month 2026-08   # fuerza un mes (pruebas / backfill)
"""
import argparse
import csv
import datetime
import io
import json
import sys
import time

import requests
from google_play_scraper import app as gplay_app
from google_play_scraper import reviews as gplay_reviews
from google_play_scraper import Sort as gplay_sort
from google_play_scraper.exceptions import NotFoundError

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:  # el script sigue funcionando sin iconos si falta Pillow
    HAS_PIL = False

CATALOG_PATH = "catalogo_billeteras_peru.csv"
COUNTRY = "pe"
LANG = "es"
REQUEST_DELAY_SECONDS = 1.5  # pausa entre llamadas para no saturar las tiendas
ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
ICON_MAX_SIZE = 128  # px — icono reducido para que el JSON no pese demasiado
RESENAS_1ESTRELLA_COUNT = 20  # cuántas reseñas de 1★ más recientes se analizan por app

ANDROID_FIELDS = ["nombre", "institucion", "servicio", "app_id_android",
                   "rating", "num_resenas", "instalaciones", "instalaciones_reales",
                   "categoria", "desarrollador", "version", "es_gratis", "fecha_lanzamiento",
                   "fecha_actualizacion", "fecha_extraccion", "error"]
IOS_FIELDS = ["nombre", "institucion", "servicio", "app_id_ios",
              "rating", "num_resenas", "categoria", "desarrollador", "es_gratis",
              "fecha_lanzamiento", "fecha_actualizacion_version",
              "fecha_extraccion", "error"]
CALIDAD_FIELDS = ["nombre", "institucion", "servicio", "app_id_android",
                   "resenas_1estrella_analizadas", "resenas_1estrella_respondidas",
                   "pct_respondidas", "tiempo_respuesta_promedio_dias",
                   "fecha_extraccion", "error"]


def load_catalog(path=CATALOG_PATH):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def is_empty(value):
    return not value or value.strip().lower() in ("", "s/d", "sd", "n/a")


def fetch_android(app_id):
    """Devuelve un dict con los datos de Android para un app_id, o error si falla."""
    if is_empty(app_id):
        return {"error": "sin app_id"}
    try:
        data = gplay_app(app_id, lang=LANG, country=COUNTRY)
        updated_ts = data.get("updated")
        fecha_actualizacion = None
        if updated_ts:
            try:
                fecha_actualizacion = datetime.datetime.utcfromtimestamp(updated_ts).date().isoformat()
            except (OverflowError, OSError, TypeError, ValueError):
                fecha_actualizacion = None
        return {
            "rating": data.get("score"),
            "num_resenas": data.get("ratings"),        # nº total de calificaciones
            "instalaciones": data.get("installs"),      # ej. "500,000+" (rango, no exacto)
            "instalaciones_reales": data.get("realInstalls"),  # cifra exacta que reporta Play Store
            "categoria": data.get("genre"),
            "desarrollador": data.get("developer"),
            "version": data.get("version"),
            "es_gratis": data.get("free"),
            "fecha_lanzamiento": data.get("released"),
            "fecha_actualizacion": fecha_actualizacion,
            "icono_url": data.get("icon"),
            "error": None,
        }
    except NotFoundError:
        return {"error": "app no encontrada (retirada de la tienda o app_id incorrecto)"}
    except Exception as e:  # noqa: BLE001 - cualquier fallo se registra y no detiene la corrida
        return {"error": f"error: {e}"}


def fetch_ios(app_id):
    """Devuelve un dict con los datos de iOS para un app_id numérico de iTunes, o error si falla."""
    if is_empty(app_id):
        return {"error": "sin app_id"}
    try:
        resp = requests.get(
            ITUNES_LOOKUP_URL,
            params={"id": app_id, "country": COUNTRY},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("resultCount"):
            return {"error": "app no encontrada en storefront PE"}
        result = payload["results"][0]

        def fecha(v):
            return v.split("T")[0] if v else None

        return {
            "rating": result.get("averageUserRating"),
            "num_resenas": result.get("userRatingCount"),
            "categoria": result.get("primaryGenreName"),
            "desarrollador": result.get("sellerName"),
            "es_gratis": (result.get("price") == 0),
            "fecha_lanzamiento": fecha(result.get("releaseDate")),
            "fecha_actualizacion_version": fecha(result.get("currentVersionReleaseDate")),
            "icono_url": result.get("artworkUrl512") or result.get("artworkUrl100"),
            "error": None,
        }
    except Exception as e:  # noqa: BLE001
        return {"error": f"error: {e}"}


def fetch_calidad_servicio(app_id, count=RESENAS_1ESTRELLA_COUNT):
    """Analiza las N reseñas de 1★ más recientes de una app en Google Play y mide qué
    porcentaje tiene respuesta del desarrollador y en cuántos días, en promedio.
    Solo Android: Apple no expone las respuestas de desarrolladores a reseñas de apps
    de terceros vía API pública. Nunca inventa un dato: si falla, se marca "s/d" con
    el motivo en la columna `error`, igual que el resto del extractor."""
    if is_empty(app_id):
        return {"error": "sin app_id"}
    try:
        result, _ = gplay_reviews(
            app_id,
            lang=LANG,
            country=COUNTRY,
            sort=gplay_sort.NEWEST,
            count=count,
            filter_score_with=1,
        )
        analizadas = len(result)
        if analizadas == 0:
            # La app no tiene reseñas de 1★ recientes — es un dato válido (buena señal),
            # no un fallo, así que no se marca "error".
            return {
                "resenas_analizadas": 0,
                "resenas_respondidas": 0,
                "pct_respondidas": None,
                "tiempo_respuesta_promedio_dias": None,
                "error": None,
            }
        respondidas = [r for r in result if r.get("replyContent")]
        tiempos_dias = []
        for r in respondidas:
            fecha_resena = r.get("at")
            fecha_respuesta = r.get("repliedAt")
            if fecha_resena and fecha_respuesta:
                delta_dias = (fecha_respuesta - fecha_resena).total_seconds() / 86400
                if delta_dias >= 0:  # descarta timestamps inconsistentes
                    tiempos_dias.append(delta_dias)
        tiempo_prom = sum(tiempos_dias) / len(tiempos_dias) if tiempos_dias else None
        return {
            "resenas_analizadas": analizadas,
            "resenas_respondidas": len(respondidas),
            "pct_respondidas": round(100 * len(respondidas) / analizadas, 2),
            "tiempo_respuesta_promedio_dias": round(tiempo_prom, 2) if tiempo_prom is not None else None,
            "error": None,
        }
    except NotFoundError:
        return {"error": "app no encontrada (retirada de la tienda o app_id incorrecto)"}
    except Exception as e:  # noqa: BLE001 - un fallo puntual no debe tumbar la corrida
        return {"error": f"error: {e}"}


def descargar_icono_b64(url):
    """Descarga un icono, lo reduce a ICON_MAX_SIZE px y lo devuelve como data URI base64.
    Devuelve None si algo falla — nunca detiene la corrida ni el resto de la extracción."""
    if not url or not HAS_PIL:
        return None
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        img.thumbnail((ICON_MAX_SIZE, ICON_MAX_SIZE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        import base64
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:  # noqa: BLE001 - un icono roto nunca debe tumbar la corrida
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--month", default=None,
                         help="Mes a extraer en formato YYYY-MM (default: mes actual, UTC).")
    parser.add_argument("--skip-icons", action="store_true",
                         help="No descargar iconos (corre más rápido, útil para pruebas).")
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
    calidad_rows = []
    iconos = {}

    for i, row in enumerate(catalog, start=1):
        nombre = row["nombre"]
        print(f"[{i}/{len(catalog)}] {nombre}", flush=True)

        a = fetch_android(row.get("app_id_android", ""))
        android_rows.append({
            "nombre": nombre,
            "institucion": row.get("institucion", ""),
            "servicio": row.get("servicio", ""),
            "app_id_android": row.get("app_id_android", ""),
            "rating": a.get("rating") if a.get("rating") is not None else "s/d",
            "num_resenas": a.get("num_resenas") if a.get("num_resenas") is not None else "s/d",
            "instalaciones": a.get("instalaciones") if a.get("instalaciones") is not None else "s/d",
            "instalaciones_reales": a.get("instalaciones_reales") if a.get("instalaciones_reales") is not None else "s/d",
            "categoria": a.get("categoria") or "s/d",
            "desarrollador": a.get("desarrollador") or "s/d",
            "version": a.get("version") or "s/d",
            "es_gratis": a.get("es_gratis") if a.get("es_gratis") is not None else "s/d",
            "fecha_lanzamiento": a.get("fecha_lanzamiento") or "s/d",
            "fecha_actualizacion": a.get("fecha_actualizacion") or "s/d",
            "fecha_extraccion": fecha_extraccion,
            "error": a.get("error") or "",
        })
        if a.get("error"):
            print(f"    Android: {a['error']}", flush=True)
        time.sleep(REQUEST_DELAY_SECONDS)

        c = fetch_calidad_servicio(row.get("app_id_android", ""))
        calidad_rows.append({
            "nombre": nombre,
            "institucion": row.get("institucion", ""),
            "servicio": row.get("servicio", ""),
            "app_id_android": row.get("app_id_android", ""),
            "resenas_1estrella_analizadas": c.get("resenas_analizadas") if c.get("resenas_analizadas") is not None else "s/d",
            "resenas_1estrella_respondidas": c.get("resenas_respondidas") if c.get("resenas_respondidas") is not None else "s/d",
            "pct_respondidas": c.get("pct_respondidas") if c.get("pct_respondidas") is not None else "s/d",
            "tiempo_respuesta_promedio_dias": c.get("tiempo_respuesta_promedio_dias") if c.get("tiempo_respuesta_promedio_dias") is not None else "s/d",
            "fecha_extraccion": fecha_extraccion,
            "error": c.get("error") or "",
        })
        if c.get("error"):
            print(f"    Calidad de servicio: {c['error']}", flush=True)
        time.sleep(REQUEST_DELAY_SECONDS)

        b = fetch_ios(row.get("app_id_ios", ""))
        ios_rows.append({
            "nombre": nombre,
            "institucion": row.get("institucion", ""),
            "servicio": row.get("servicio", ""),
            "app_id_ios": row.get("app_id_ios", ""),
            "rating": b.get("rating") if b.get("rating") is not None else "s/d",
            "num_resenas": b.get("num_resenas") if b.get("num_resenas") is not None else "s/d",
            "categoria": b.get("categoria") or "s/d",
            "desarrollador": b.get("desarrollador") or "s/d",
            "es_gratis": b.get("es_gratis") if b.get("es_gratis") is not None else "s/d",
            "fecha_lanzamiento": b.get("fecha_lanzamiento") or "s/d",
            "fecha_actualizacion_version": b.get("fecha_actualizacion_version") or "s/d",
            "fecha_extraccion": fecha_extraccion,
            "error": b.get("error") or "",
        })
        if b.get("error") and not is_empty(row.get("app_id_ios", "")):
            print(f"    iOS: {b['error']}", flush=True)

        if not args.skip_icons:
            icono_url = a.get("icono_url") or b.get("icono_url")
            if icono_url:
                b64 = descargar_icono_b64(icono_url)
                if b64:
                    iconos[nombre] = b64
                time.sleep(0.5)

        time.sleep(REQUEST_DELAY_SECONDS)

    android_path = f"datos_{month_str}.csv"
    ios_path = f"datos_{month_str}_ios.csv"
    iconos_path = f"iconos_{month_str}.json"
    calidad_path = f"calidad_servicio_{month_str}.csv"

    with open(android_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ANDROID_FIELDS)
        writer.writeheader()
        writer.writerows(android_rows)

    with open(ios_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=IOS_FIELDS)
        writer.writeheader()
        writer.writerows(ios_rows)

    with open(iconos_path, "w", encoding="utf-8") as f:
        json.dump(iconos, f)

    with open(calidad_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CALIDAD_FIELDS)
        writer.writeheader()
        writer.writerows(calidad_rows)

    fallos_android = sum(1 for r in android_rows if r["error"])
    fallos_ios = sum(1 for r in ios_rows if r["error"] and not is_empty(r["app_id_ios"]))
    fallos_calidad = sum(1 for r in calidad_rows if r["error"])
    print(f"\nListo: {android_path} ({len(android_rows)} apps, {fallos_android} con error/s-d)")
    print(f"Listo: {ios_path} ({len(ios_rows)} apps, {fallos_ios} con error/s-d)")
    print(f"Listo: {iconos_path} ({len(iconos)}/{len(catalog)} iconos descargados)")
    print(f"Listo: {calidad_path} ({len(calidad_rows)} apps, {fallos_calidad} con error/s-d)")


if __name__ == "__main__":
    main()
