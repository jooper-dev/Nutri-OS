"""
Atajo — Nutri-OS

Ensambla y valida en un solo paso. No renderiza, pero no porque haga falta un
permiso: el render es un comando aparte y este atajo deja el plan listo para él.
Si el validador marca BLOQUEADO, se detiene y no hay nada que renderizar.

La revisión de Paty va DESPUÉS, sobre los PDF terminados: ella no lee markdown,
y pedirle que apruebe un reporte que no puede leer no era una puerta, era un
trámite.

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

    # Los destacados van primero y aparte. Lo que hundió el primer caso real no
    # fue que faltara el aviso de selectividad: fue que habría salido en la línea
    # 40 de una lista de 60, entre notas sobre claves de protocolo sin implementar.
    for d in r.destacados:
        print(f"  ‼ {d}")
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
    print("  Siguiente paso — generar los PDF para que Paty los revise:")
    print(f"     python motor/render.py {args.paciente}")
    print(f"     python motor/render.py {args.paciente} --caras   (letra mayor)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
