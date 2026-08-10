"""
Atajo — Nutri-OS

Ensambla y valida en un solo paso, y se detiene en la puerta de Paty.
No renderiza: eso requiere su visto bueno.

Uso:
    python motor/correr.py <nombre_carpeta_paciente> [--semilla N]
"""

from __future__ import annotations

import argparse
import sys

from comun import DIR_PACIENTES, ErrorNutriOS, guardar_json
from ensamblar import ensamblar
from validar import escribir_reporte, validar


def main() -> int:
    ap = argparse.ArgumentParser(description="Ensambla y valida el plan de un paciente.")
    ap.add_argument("paciente")
    ap.add_argument("--semilla", type=int, default=None)
    args = ap.parse_args()

    carpeta = DIR_PACIENTES / args.paciente

    try:
        plan = ensamblar(args.paciente, args.semilla)
        guardar_json(carpeta / "plan.json", plan)
        print(f"✓ Plan ensamblado — {plan['paciente']}, {len(plan['semanas'])} semana(s)")

        r, plan = validar(args.paciente)
        destino = escribir_reporte(carpeta, r, plan)
    except ErrorNutriOS as e:
        print(f"\n✗ {e}\n", file=sys.stderr)
        return 1

    for e in r.errores:
        print(f"  ✗ {e}")
    for a in r.avisos:
        print(f"  ⚠ {a}")

    print()
    if not r.ok:
        print(f"✗ BLOQUEADO — {len(r.errores)} error(es). No se renderiza.")
        print(f"  → {destino}")
        return 1

    print(f"✓ Plan válido, con {len(r.avisos)} aviso(s).")
    print(f"  → {destino}")
    print()
    print("  ⛔ PUERTA DE PATY: revisa el reporte antes de renderizar.")
    print(f"     Cuando dé el visto bueno:  python motor/render.py {args.paciente}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
