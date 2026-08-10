# Nutri-OS

Sistema de generación de planes alimentarios pediátricos de **GrowKids**
(Nut. Patricia López).

Entrada: la carpeta de una paciente.
Salida: dos PDF listos para entregar — el plan de alimentación y el recetario
personalizado con solo las recetas que ese plan usa.

---

## Cómo funciona

| Fase | Qué hace | Quién |
|------|----------|-------|
| F1 | Lee el caso clínico y escribe `ficha.md` | modelo |
| F2 | Elige protocolo y detecta huecos de biblioteca | código |
| F3 | Genera las recetas que faltan | modelo (P1) |
| F4 | Ensambla el plan | **código** |
| F5 | Valida | **código** |
| F6 | Revisión y firma | **Paty** |
| F7 | Renderiza los PDF | **código** |
| F8 | Registra la consulta | código |

El reparto es el punto entero del sistema: **el modelo redacta y juzga; el código
cuenta y maqueta.** Contar menestras no es trabajo para un modelo de lenguaje, y
por eso las frecuencias del protocolo se garantizan al construir el plan, no se
revisan después.

---

## Instalación

```bash
pip install -r requirements.txt
```

WeasyPrint necesita algunas librerías de sistema. En Debian/Ubuntu:

```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2
```

---

## Uso

```bash
# 1. Crea la carpeta y mete el material de la consulta
mkdir -p pacientes/Mateo/fuente
#    (PDFs de laboratorio, fotos, notas, preferencias…)

# 2. F1 — en Cowork o Claude Code, con prompts/PC_CLINICO.md
#    Produce pacientes/Mateo/ficha.md

# 3. Ensambla y valida
python motor/correr.py Mateo

# 4. Paty revisa reporte_qa.md y da el visto bueno

# 5. PDF
python motor/render.py Mateo

# 6. Registro
python motor/registrar.py Mateo --costo 189
```

Hay un caso completo de ejemplo en `pacientes/_EJEMPLO_Mateo/` con datos
ficticios, para probar el sistema sin tocar información real.

---

## Estructura

```
prompts/           PC_CLINICO (F1) · P1_RECETAS (F3)
protocolos/        un .yaml por tipo de plan — estructura y frecuencias
reglas_exclusion/  restricciones por edad, con evidencia
biblioteca/        una receta por archivo, crece con el uso
datos/             alimentos base · registro de consultas
motor/             ensamblar · validar · render · registrar
pacientes/         casos reales (fuera de Git)
```

---

## Añadir un tipo de plan

Copia un archivo de `protocolos/`, cambia los datos y ya está. Ni una línea de
código, ni un prompt tocado. Ver `protocolos/_ESQUEMA.md`.

---

## Reglas que no se rompen

- **`pacientes/` nunca se sube a Git.** Son historiales clínicos de menores.
- **`plan.json` no se edita a mano.** Si algo está mal, se corrige en el protocolo,
  en la biblioteca o en la ficha, y se vuelve a ensamblar. Editar la salida
  destruye la única garantía que da el sistema.
- **La puerta de revisión no se salta.** El renderizador se niega a trabajar si el
  validador marcó BLOQUEADO, pero el visto bueno clínico lo da Paty, no el código.
- **Las recetas no se inventan dentro del plan.** Pasan por P1, con su auditoría
  de seguridad pediátrica, y aterrizan en la biblioteca antes de aparecer en un menú.

---

## Nota sobre el repositorio anterior

La versión previa dejó `.env` y `credentials.json` versionados y el repositorio
se hizo público. **Ese cliente OAuth de Google hay que eliminarlo y crear uno
nuevo**; borrar los archivos no basta, siguen en el historial de Git.

Esta versión ya no usa Google Workspace para nada: los PDF se generan en local.
No hay credenciales que filtrar.
