"""
Respaldo — Nutri-OS

Comprime `pacientes/` y `datos/consultas.csv` a una ruta fuera del repositorio.

Existe porque todo el trabajo clínico vive en una sola máquina y no tiene copia.
`pacientes/` está en `.gitignore` —y tiene que seguir estando: son historiales de
menores—, así que git no lo respalda y nunca lo va a respaldar. Ahora ahí dentro
hay el historial de un paciente real, con su anamnesis, sus medidas y su plan.

Un disco que se rompe se lleva eso por delante, y no se puede volver a pedir: la
consulta ya pasó.

    python motor/respaldar.py D:/Respaldos/NutriOS
    python motor/respaldar.py "E:/Copia" --nota control-septiembre

Deja `nutrios_AAAA-MM-DD_HHMM.zip` con todo dentro, dice qué guardó y dónde, y
**se niega con un mensaje claro si la ruta no existe**: crear la carpeta por su
cuenta sería la forma más fácil de escribir el respaldo en un pendrive que no
está conectado y creer que quedó guardado.

Usa solo la librería estándar. Un respaldo que depende de un paquete instalado
es un respaldo que falla el día que se reinstala el equipo.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from comun import DIR_DATOS, DIR_PACIENTES, RAIZ, ErrorNutriOS


def _legible(n: int) -> str:
    tam = float(n)
    for unidad in ("B", "KB", "MB", "GB"):
        if tam < 1024:
            return f"{tam:.0f} {unidad}" if unidad == "B" else f"{tam:.1f} {unidad}"
        tam /= 1024
    return f"{tam:.1f} TB"


def respaldar(destino: Path, nota: str = "") -> tuple[Path, list[str], int]:
    """Comprime y devuelve (archivo, qué entró, bytes originales)."""
    if not destino.exists():
        raise ErrorNutriOS(
            f"La ruta de respaldo no existe: {destino}\n"
            f"    No la creo yo a propósito. Si esa ruta es un disco externo o una "
            f"carpeta de nube que hoy no está montada, crearla haría aparecer una "
            f"carpeta vacía en el disco local, el respaldo se escribiría ahí, y "
            f"parecería que quedó guardado.\n"
            f"    Comprueba que la unidad esté conectada, o crea la carpeta a mano y "
            f"vuelve a ejecutar."
        )
    if not destino.is_dir():
        raise ErrorNutriOS(
            f"La ruta de respaldo existe pero no es una carpeta: {destino}\n"
            f"    Indica una carpeta, no un archivo."
        )

    try:
        if destino.resolve().is_relative_to(RAIZ):
            raise ErrorNutriOS(
                f"La ruta de respaldo está dentro del propio repositorio: {destino}\n"
                f"    Un respaldo ahí no protege de nada: se pierde con el mismo disco, "
                f"y encima mete datos clínicos de menores donde git puede verlos.\n"
                f"    Elige una ruta fuera de {RAIZ} — un disco externo o una carpeta "
                f"sincronizada."
            )
    except (OSError, ValueError):
        pass

    fuentes: list[tuple[Path, str]] = []
    if DIR_PACIENTES.exists():
        for ruta in sorted(DIR_PACIENTES.rglob("*")):
            if ruta.is_file() and ruta.name != ".gitkeep":
                fuentes.append((ruta, str(ruta.relative_to(RAIZ)).replace("\\", "/")))

    consultas = DIR_DATOS / "consultas.csv"
    if consultas.exists():
        fuentes.append((consultas, "datos/consultas.csv"))

    if not fuentes:
        raise ErrorNutriOS(
            "No hay nada que respaldar: pacientes/ está vacía y no existe "
            "datos/consultas.csv.\n"
            "    Si esperabas que hubiera algo, comprueba que estás en el repositorio "
            "correcto antes de dar el respaldo por hecho."
        )

    sufijo = f"_{re.sub(r'[^A-Za-z0-9-]+', '-', nota).strip('-')}" if nota else ""
    archivo = destino / f"nutrios_{datetime.now():%Y-%m-%d_%H%M}{sufijo}.zip"

    crudos = 0
    try:
        with zipfile.ZipFile(archivo, "w", zipfile.ZIP_DEFLATED) as z:
            for ruta, interno in fuentes:
                z.write(ruta, interno)
                crudos += ruta.stat().st_size
    except (OSError, PermissionError) as e:
        raise ErrorNutriOS(
            f"No se pudo escribir el respaldo en {archivo}: {e}\n"
            f"    Comprueba que haya espacio y permiso de escritura en esa ruta."
        ) from e

    carpetas = sorted(
        {
            p.relative_to(RAIZ).parts[1]
            for p, _ in fuentes
            if p.is_relative_to(DIR_PACIENTES)
        }
    )
    return archivo, carpetas, crudos


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Respalda pacientes/ y datos/consultas.csv fuera del repositorio."
    )
    ap.add_argument("destino", help="carpeta de destino; tiene que existir ya")
    ap.add_argument("--nota", default="", help="sufijo para el nombre del archivo")
    args = ap.parse_args()

    try:
        archivo, carpetas, crudos = respaldar(Path(args.destino).expanduser(), args.nota)
    except ErrorNutriOS as e:
        print(f"\n✗ {e}\n", file=sys.stderr)
        return 1

    comprimido = archivo.stat().st_size
    print("✓ Respaldo guardado")
    print(f"  → {archivo}")
    print(f"  {_legible(crudos)} en disco · {_legible(comprimido)} comprimido")
    print(f"  {len(carpetas)} carpeta(s) de paciente: {', '.join(carpetas) or '(ninguna)'}")
    print("  Incluye datos/consultas.csv si existía.")
    print()
    print("  Son datos clínicos de menores: guarda ese archivo donde guardarías una")
    print("  historia clínica en papel, y no lo subas a ningún sitio público.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
