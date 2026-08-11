"""
Utilidades compartidas del motor Nutri-OS.

Todo lo que lee archivos del repositorio pasa por aquí, para que exista
un solo sitio donde cambiar formatos.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def consola_utf8() -> None:
    """Deja la salida en UTF-8 para que un ✓ no tumbe un script entero.

    En Windows, cuando la salida va a un archivo o a una tubería —o la consola
    está en cp1252—, Python elige esa codificación y cualquier símbolo de los
    que usa el sistema (✓ ✗ ⚠ · → —) lanza UnicodeEncodeError.

    No es un problema estético. `ensamblar.py` guarda plan.json ANTES de
    imprimir su resumen: el plan salía correcto, el script moría en el `print`
    siguiente, y quien lo ejecutaba veía una traza roja y daba por hecho que el
    sistema había fallado.

    `errors="replace"` es la red por debajo: si ni siquiera se puede pasar a
    UTF-8, es preferible un símbolo sustituido por '?' que una traza.

    Se llama al importar este módulo, que es lo primero que hace cualquier
    script del motor. Es un efecto de importación deliberado: la alternativa
    era repetir estas seis líneas en los diez puntos de entrada.
    """
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


consola_utf8()

RAIZ = Path(__file__).resolve().parent.parent

DIR_PROTOCOLOS = RAIZ / "protocolos"
DIR_BIBLIOTECA = RAIZ / "biblioteca"
DIR_DATOS = RAIZ / "datos"
DIR_PACIENTES = RAIZ / "pacientes"
DIR_SALIDAS = RAIZ / "salidas"
DIR_REGLAS = RAIZ / "reglas_exclusion"

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Componentes exentos del filtro de `texturas_excluidas`.
#
# `texturas_excluidas` describe cómo COME el niño, no cómo bebe ni de qué está
# hecho por dentro un plato. Aplicarla a estos tres componentes es aplicarla
# donde no corresponde, y el daño no era cosmético: a un paciente que no tolera
# lo húmedo el filtro le quitaba el agua —que tiene textura `liquida`— y las
# tres grasas, es decir, la bebida y toda la densidad calórica del plan, que en
# un caso de bajo peso es justamente lo que hay que subir.
#
#   bebida          nadie con aversión textural deja de beber agua.
#   grasa           el aceite y la palta no se comen solos: son ingrediente.
#   ensalada_grasa  ídem. La textura que decide si el plato se come o termina
#                   en arcada es la del plato terminado, no la del aceite.
#
# Va como lista explícita y no como excepción dentro del filtro para que se vea
# al abrir el archivo: exonerar un componente del filtro de textura es una
# decisión clínica, y tiene que poder discutirse leyendo esta línea.
COMPONENTES_SIN_FILTRO_TEXTURA = {"bebida", "grasa", "ensalada_grasa"}

# Componentes que NO exigen variedad: pueden repetirse sin límite y no cuentan
# para la comprobación de suficiencia de la biblioteca.
#
# El motor confundía dos cosas distintas bajo una sola condición ("¿es receta o
# alimento base?"). Que el arroz vaya a diario y que el agua vaya dos veces al
# día es normal: son fondo de plato y bebida, y nadie espera variedad ahí. Que
# el snack de media mañana sea el mismo las 14 veces de la quincena no lo es —
# y en selectividad severa no es solo aburrido, es contraproducente: la
# monotonía impuesta encoge el repertorio que el plan tendría que ampliar.
#
#   fondo de plato, guarnición y bebida
#       carbohidrato · base_energetica · grasa · ensalada_grasa · bebida
#   el plato en sí
#       base · acompanante · crujiente · cereal · proteina · proteina_hierro ·
#       menestra · fruta · fruta_vitc · verdura
#
# `ensalada_grasa` está en la primera lista por su papel, no por su nombre:
# cumple exactamente el de `grasa` —vehículo de grasa que acompaña al plato—,
# hasta el punto de que escolar_eliminacion_4 sustituye una por la otra. Pedir
# que "ensalada con palta" no se repita más de dos veces por semana no protege
# a nadie; solo hace imposible un protocolo que la pide a diario.
#
# Solo la primera lista vive aquí, porque es la excepción. Todo lo demás exige
# variedad, incluido lo que no aparezca en ninguna de las dos: si mañana se
# añade un componente y nadie se acuerda de clasificarlo, el sistema pecará de
# exigente y lo dirá, que es el lado correcto por el que equivocarse.
COMPONENTES_SIN_EXIGENCIA_DE_VARIEDAD = {
    "carbohidrato",
    "base_energetica",
    "grasa",
    "ensalada_grasa",
    "bebida",
}


class ErrorNutriOS(Exception):
    """Fallo controlado del motor. Se imprime limpio, sin traza."""


# ---------------------------------------------------------------------------
# Front-matter
# ---------------------------------------------------------------------------

_FM = re.compile(r"\A\s*---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def leer_front_matter(ruta: Path) -> tuple[dict, str]:
    """Devuelve (metadatos, cuerpo) de un .md con front-matter YAML."""
    texto = ruta.read_text(encoding="utf-8")
    m = _FM.match(texto)
    if not m:
        raise ErrorNutriOS(
            f"{ruta.name}: no tiene front-matter YAML delimitado por '---'."
        )
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise ErrorNutriOS(f"{ruta.name}: front-matter mal formado — {e}") from e
    if not isinstance(meta, dict):
        raise ErrorNutriOS(f"{ruta.name}: el front-matter no es un diccionario.")
    return meta, m.group(2)


def normalizar(s: str) -> str:
    """Minúsculas, sin tildes, sin espacios. Para comparar ids y familias."""
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.strip().lower().replace(" ", "_")


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


@dataclass
class Opcion:
    """Una cosa que puede ocupar una ranura del plan: receta o alimento base."""

    id: str
    nombre: str
    componente: str
    edad_min_meses: int
    alergenos: list[str] = field(default_factory=list)
    familia: str = ""
    momento: list[str] = field(default_factory=list)
    aporta: list[str] = field(default_factory=list)
    textura: str = ""
    es_receta: bool = False
    validada_en_cocina: bool = False
    ruta: str = ""

    def responde_a(self, clave: str) -> bool:
        """¿Este alimento responde a una clave del protocolo? Familia o id.

        El protocolo nombra alimentos en dos niveles, y los dos son legítimos:

          {tuberculo: 4}   el cajón — "cuatro tubérculos por semana", y que el
                           catálogo decida cuál según el paciente y su región.
          {camote: 2}      el alimento — cuando hay una razón clínica para ESE
                           alimento y no para su cajón.

        Sin el segundo nivel, escribir un protocolo obligaría a elegir entre
        abrirlo a la región o conservar el criterio clínico fino. Con los dos,
        una misma rotación puede mezclarlos: {camote: 2, tuberculo: 2, grano: resto}.
        """
        if not clave:
            return True
        c = normalizar(clave)
        return c == normalizar(self.familia) or c == normalizar(self.id)

    def apta_para(self, ficha: dict) -> tuple[bool, str]:
        """¿Puede esta opción entrar en el plan de este paciente?"""
        if self.edad_min_meses > ficha["edad_meses"]:
            return False, f"edad mínima {self.edad_min_meses} m"
        alergias = {normalizar(a) for a in ficha.get("alergias") or []}
        choque = alergias & {normalizar(a) for a in self.alergenos}
        if choque:
            return False, f"alérgeno: {', '.join(sorted(choque))}"
        rechazos = {normalizar(r) for r in ficha.get("rechazos") or []}
        if normalizar(self.id) in rechazos or normalizar(self.familia) in rechazos:
            return False, "rechazo declarado"
        for r in rechazos:
            if r and r in normalizar(self.nombre):
                return False, "rechazo declarado"

        # La aversión a una textura no es una manía: en selectividad severa y en
        # disfagia decide si el plato se come o si termina en arcada. Se filtra
        # igual que un rechazo, pero por su propio campo, porque el nombre del
        # alimento nunca la delata ("compota de pera" no dice "aguado").
        excluidas = {normalizar(t) for t in ficha.get("texturas_excluidas") or []}
        if (
            excluidas
            and self.componente not in COMPONENTES_SIN_FILTRO_TEXTURA
            and normalizar(self.textura) in excluidas
        ):
            return False, f"textura {self.textura}"
        return True, ""


# ---------------------------------------------------------------------------
# Cargadores
# ---------------------------------------------------------------------------


def cargar_protocolo(id_protocolo: str) -> dict:
    ruta = DIR_PROTOCOLOS / f"{id_protocolo}.yaml"
    if not ruta.exists():
        disponibles = sorted(p.stem for p in DIR_PROTOCOLOS.glob("*.yaml"))
        raise ErrorNutriOS(
            f"No existe el protocolo '{id_protocolo}'. Disponibles: {', '.join(disponibles)}"
        )
    try:
        return yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ErrorNutriOS(
            f"El protocolo '{id_protocolo}.yaml' tiene YAML mal formado.\n"
            f"    Detalle: {e}"
        ) from e


def cargar_alimentos_base() -> list[Opcion]:
    ruta = DIR_DATOS / "alimentos_base.yaml"
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    opciones: list[Opcion] = []
    for componente, lista in datos.items():
        for a in lista or []:
            opciones.append(
                Opcion(
                    id=a["id"],
                    nombre=a["nombre"],
                    componente=componente,
                    edad_min_meses=int(a.get("edad_min_meses", 0)),
                    alergenos=a.get("alergenos") or [],
                    familia=a.get("familia") or a["id"],
                    aporta=a.get("aporta") or [],
                    textura=str(a.get("textura") or ""),
                    es_receta=False,
                    ruta=str(ruta.relative_to(RAIZ)),
                )
            )
    return opciones


def cargar_biblioteca() -> tuple[list[Opcion], list[str]]:
    """Lee /biblioteca/*.md. Devuelve (opciones, avisos)."""
    opciones: list[Opcion] = []
    avisos: list[str] = []
    obligatorios = ("id", "titulo", "edad_min_meses", "componente")

    for ruta in sorted(DIR_BIBLIOTECA.glob("*.md")):
        if ruta.name.startswith("_"):
            continue
        try:
            meta, _ = leer_front_matter(ruta)
        except ErrorNutriOS as e:
            avisos.append(str(e))
            continue

        faltan = [c for c in obligatorios if meta.get(c) in (None, "")]
        if faltan:
            avisos.append(f"{ruta.name}: faltan campos {', '.join(faltan)} — se omite.")
            continue

        opciones.append(
            Opcion(
                id=str(meta["id"]),
                nombre=str(meta["titulo"]),
                componente=str(meta["componente"]),
                edad_min_meses=int(meta["edad_min_meses"]),
                alergenos=meta.get("alergenos_presentes") or [],
                familia=str(meta.get("familia") or ""),
                momento=meta.get("momento") or [],
                aporta=meta.get("aporta") or [],
                textura=str(meta.get("textura") or ""),
                es_receta=True,
                validada_en_cocina=bool(meta.get("validada_en_cocina", False)),
                ruta=str(ruta.relative_to(RAIZ)),
            )
        )
    return opciones, avisos


def cargar_ficha(carpeta_paciente: Path) -> dict:
    ruta = carpeta_paciente / "ficha.md"
    if not ruta.exists():
        raise ErrorNutriOS(
            f"No existe {ruta}. Ejecuta primero la Fase 1 (prompts/PC_CLINICO.md)."
        )
    meta, cuerpo = leer_front_matter(ruta)

    obligatorios = ["paciente", "edad_meses", "semanas_plan", "protocolo_sugerido", "porciones"]
    faltan = [c for c in obligatorios if meta.get(c) in (None, "")]
    if faltan:
        raise ErrorNutriOS(f"ficha.md: faltan campos obligatorios: {', '.join(faltan)}")

    if meta.get("bloqueantes"):
        raise ErrorNutriOS(
            "La ficha declara bloqueantes; el pipeline se detiene:\n  - "
            + "\n  - ".join(meta["bloqueantes"])
        )

    meta["_cuerpo"] = cuerpo
    return meta


def guardar_json(ruta: Path, datos: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
