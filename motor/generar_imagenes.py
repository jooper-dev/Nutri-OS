"""
Generación de imágenes — Nutri-OS · Fase 3b

Toma los prompts que escribió motor/fotos.py y genera la fotografía de cada
receta con la API de Gemini (Nano Banana). Las imágenes se guardan en
biblioteca/imagenes/[id].png y se generan UNA SOLA VEZ por receta: a partir de
ahí, cualquier paciente que la lleve la recibe con foto sin coste nuevo.

CLAVE DE API
    Se lee EXCLUSIVAMENTE de la variable de entorno GEMINI_API_KEY.
    Nunca se escribe en un archivo del proyecto, ni se imprime, ni se acepta
    como argumento. Si alguien la pega en el chat o en un archivo, hay que
    rotarla: este repositorio ya se filtró una vez por eso.

        export GEMINI_API_KEY="..."          (macOS / Linux)
        setx GEMINI_API_KEY "..."            (Windows, reabrir la terminal)

Uso:
    python motor/generar_imagenes.py --todas
    python motor/generar_imagenes.py <carpeta_paciente>
    python motor/generar_imagenes.py --todas --modelo gemini-3-pro-image
    python motor/generar_imagenes.py --solo muffins-zanahoria-avena --rehacer
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from comun import DIR_BIBLIOTECA, DIR_PACIENTES, ErrorNutriOS

DIR_PROMPTS = DIR_BIBLIOTECA / "prompts_imagen"
DIR_IMAGENES = DIR_BIBLIOTECA / "imagenes"

# Nano Banana 2. Se puede cambiar con --modelo; los nombres cambian con el
# tiempo y no conviene enterrarlos en el código.
MODELO_POR_DEFECTO = "gemini-3.1-flash-image"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

# Ninguna relación coincide con A4 (0.707). 2:3 es la más cercana de las que
# aceptan los modelos, y el recorte se hace SIEMPRE por el borde inferior:
# el tercio superior lo reservan los prompts para el título en Canva.
PROPORCION = "2:3"
A4 = 210 / 297

MAX_INTENTOS = 2


def clave() -> str:
    """Variable de entorno primero; si no, el archivo .env de la raíz."""
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k

    # .env está en .gitignore desde la primera línea del proyecto: es el único
    # sitio del repositorio donde una clave puede vivir sin acabar en GitHub.
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for linea in env.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea.startswith("GEMINI_API_KEY"):
                valor = linea.split("=", 1)[-1].strip().strip("\"'")
                if valor:
                    return valor

    raise ErrorNutriOS(
        "No hay clave de API.\n"
        "    Opción A — crea un archivo .env en la raíz del proyecto con esta línea:\n"
        "        GEMINI_API_KEY=tu_clave_aqui\n"
        "    Opción B — defínela como variable de entorno antes de ejecutar.\n"
        "    .env ya está en .gitignore, así que no se sube a GitHub.\n"
        "    NO la pegues en el chat ni en ningún otro archivo del proyecto."
    )


def llamar(prompt: str, modelo: str, api_key: str) -> bytes:
    """Una llamada. Devuelve los bytes de la imagen o lanza ErrorNutriOS."""
    cuerpo = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": PROPORCION},
        },
    }
    req = urllib.request.Request(
        ENDPOINT.format(modelo=modelo),
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        crudo = e.read().decode("utf-8", "ignore")
        try:
            msg = json.loads(crudo).get("error", {}).get("message", "")
        except json.JSONDecodeError:
            msg = crudo[:200]
        pistas = {
            "API_KEY_INVALID": "la clave de GEMINI_API_KEY no es válida",
            "PERMISSION_DENIED": "la clave no tiene permiso para este modelo",
            "was not found": f"el modelo «{modelo}» no existe o cambió de nombre; prueba con --modelo",
            "quota": "cuota agotada: espera o revisa la facturación",
            "RESOURCE_EXHAUSTED": "demasiadas llamadas seguidas: sube --pausa",
        }
        for aguja, texto in pistas.items():
            if aguja.lower() in (crudo + msg).lower():
                raise ErrorNutriOS(f"{texto} (HTTP {e.code})") from e
        raise ErrorNutriOS(f"HTTP {e.code} — {msg[:180]}") from e
    except urllib.error.URLError as e:
        raise ErrorNutriOS(f"sin conexión con la API — {e.reason}") from e

    for cand in datos.get("candidates") or []:
        for parte in (cand.get("content") or {}).get("parts") or []:
            blob = parte.get("inlineData") or parte.get("inline_data")
            if blob and blob.get("data"):
                return base64.b64decode(blob["data"])

    motivo = (datos.get("candidates") or [{}])[0].get("finishReason", "")
    bloqueo = (datos.get("promptFeedback") or {}).get("blockReason", "")
    raise ErrorNutriOS(
        f"la respuesta no trae imagen (finishReason={motivo or '?'}"
        + (f", blockReason={bloqueo}" if bloqueo else "")
        + ")"
    )


def recortar_a4(bruto: bytes) -> tuple[bytes, str]:
    """Recorta a proporción A4 quitando SOLO por abajo.

    Devuelve (bytes, aviso). El aviso va vacío si se recortó de verdad.

    Antes, sin Pillow, esto devolvía la imagen intacta y no decía nada: las
    fotos se guardaban en 2:3, entraban deformadas en el recetario y no había
    forma de saber por qué. Un recorte que no ocurre tiene que decirse.
    """
    try:
        from PIL import Image
    except ImportError:
        return bruto, (
            "Pillow no está instalado: la imagen se guarda en "
            f"{PROPORCION} sin recortar a A4 y saldrá deformada en el recetario.\n"
            "    Instálala con:  pip install -r requirements.txt"
        )

    im = Image.open(io.BytesIO(bruto)).convert("RGB")
    alto_objetivo = round(im.width / A4)
    if alto_objetivo < im.height:
        im = im.crop((0, 0, im.width, alto_objetivo))
    salida = io.BytesIO()
    im.save(salida, format="PNG")
    return salida.getvalue(), ""


def generar(
    rutas: list[Path],
    api_key: str,
    modelo: str = MODELO_POR_DEFECTO,
    pausa: float = 1.5,
    rehacer: bool = False,
) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    """Genera las imágenes de esos prompts. Devuelve (hechas, saltadas, fallidas).

    Nunca lanza: un fallo de una imagen se anota y se sigue con la siguiente.
    """
    DIR_IMAGENES.mkdir(parents=True, exist_ok=True)
    hechas: list[str] = []
    saltadas: list[str] = []
    fallidas: list[tuple[str, str]] = []

    aviso_recorte = ""
    for ruta in rutas:
        rid = ruta.stem
        destino = DIR_IMAGENES / f"{rid}.png"
        if destino.exists() and not rehacer:
            saltadas.append(rid)
            continue

        prompt = ruta.read_text(encoding="utf-8")
        ultimo = ""
        for intento in range(1, MAX_INTENTOS + 1):
            try:
                bruto = llamar(prompt, modelo, api_key)
                recortada, aviso = recortar_a4(bruto)
                destino.write_bytes(recortada)
                if aviso and not aviso_recorte:
                    aviso_recorte = aviso
                    print(f"  ⚠ {aviso}")
                hechas.append(rid)
                print(f"  ✓ {rid}")
                break
            except ErrorNutriOS as e:
                ultimo = str(e)
                if intento < MAX_INTENTOS:
                    time.sleep(3)
        else:
            # Nunca se deja el proceso colgado por una imagen: se anota y sigue.
            fallidas.append((rid, ultimo))
            print(f"  ✗ {rid} — {ultimo}")

        time.sleep(pausa)

    return hechas, saltadas, fallidas


def asegurar_imagenes(
    ids: list[str], modelo: str = MODELO_POR_DEFECTO, pausa: float = 1.5
) -> dict:
    """Consigue la foto de cada receta de la lista que aún no la tenga.

    Es la puerta que usa `render.py` antes de maquetar el recetario. **No lanza
    nunca**, ni siquiera sin clave de API: devuelve el resumen y quien llama
    decide qué contar. El recetario se maqueta igual sin foto, con la banda de
    color, y perder una fotografía nunca puede costar un plan.

    Resumen: {hechas, saltadas, fallidas: [(id, error)], sin_prompt, motivo}
    donde `motivo` explica por qué no se intentó nada (falta de clave).
    """
    resumen: dict = {
        "hechas": [],
        "saltadas": [],
        "fallidas": [],
        "sin_prompt": [],
        "motivo": None,
    }

    pendientes: list[Path] = []
    for rid in ids:
        prompt = DIR_PROMPTS / f"{rid}.txt"
        if not prompt.exists():
            resumen["sin_prompt"].append(rid)
        elif (DIR_IMAGENES / f"{rid}.png").exists():
            resumen["saltadas"].append(rid)
        else:
            pendientes.append(prompt)

    if not pendientes:
        return resumen

    try:
        api_key = clave()
    except ErrorNutriOS as e:
        resumen["motivo"] = str(e)
        return resumen

    hechas, _, fallidas = generar(pendientes, api_key, modelo=modelo, pausa=pausa)
    resumen["hechas"] = hechas
    resumen["fallidas"] = fallidas
    return resumen


def objetivos(args) -> list[Path]:
    if args.solo:
        rutas = [DIR_PROMPTS / f"{i}.txt" for i in args.solo]
        faltan = [r.stem for r in rutas if not r.exists()]
        if faltan:
            raise ErrorNutriOS(
                f"No hay prompt para: {', '.join(faltan)}.\n"
                "    Genera antes los prompts con:  python motor/fotos.py --todas"
            )
        return rutas
    if args.paciente:
        ruta_plan = DIR_PACIENTES / args.paciente / "plan.json"
        if not ruta_plan.exists():
            raise ErrorNutriOS(f"No existe {ruta_plan}.")
        plan = json.loads(ruta_plan.read_text(encoding="utf-8"))
        return [
            p for p in (DIR_PROMPTS / f"{rid}.txt" for rid in plan.get("recetas_usadas", []))
            if p.exists()
        ]
    return sorted(DIR_PROMPTS.glob("*.txt"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera las fotografías de las recetas.")
    ap.add_argument("paciente", nargs="?", help="carpeta de paciente")
    ap.add_argument("--todas", action="store_true", help="toda la biblioteca")
    ap.add_argument("--solo", nargs="+", metavar="ID", help="ids concretos de receta")
    ap.add_argument("--rehacer", action="store_true", help="regenera imágenes ya existentes")
    ap.add_argument("--modelo", default=MODELO_POR_DEFECTO)
    ap.add_argument("--pausa", type=float, default=1.5, help="segundos entre llamadas")
    args = ap.parse_args()

    if not (args.paciente or args.todas or args.solo):
        ap.error("indica una carpeta de paciente, --todas o --solo")

    try:
        api_key = clave()
        rutas = objetivos(args)
    except ErrorNutriOS as e:
        print(f"\n✗ {e}\n", file=sys.stderr)
        return 1

    if not rutas:
        print("\nNo hay prompts que procesar. Ejecuta antes:  python motor/fotos.py --todas\n")
        return 0

    print(f"\nModelo: {args.modelo} · proporción {PROPORCION} · recorte A4 por el borde inferior\n")

    hechas, saltadas, fallidas = generar(
        rutas, api_key, modelo=args.modelo, pausa=args.pausa, rehacer=args.rehacer
    )

    print()
    print(f"✓ {len(hechas)} imagen(es) nueva(s) · {len(saltadas)} ya existían · {len(fallidas)} fallo(s)")
    if hechas:
        print(f"  → {DIR_IMAGENES}")
        print("  El recetario las embebe solas en el próximo render.")
    if fallidas:
        print("\n  Fallos (reintenta más tarde, no se pierde nada):")
        for rid, err in fallidas:
            print(f"    {rid}: {err}")
    if saltadas and not args.rehacer:
        print(f"\n  Se saltaron {len(saltadas)} que ya tenían imagen. Usa --rehacer para regenerarlas.")
    return 1 if fallidas else 0


if __name__ == "__main__":
    raise SystemExit(main())
