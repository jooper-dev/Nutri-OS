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
| F3b | Fotografía de cada receta nueva | prompt por código, imagen por modelo |
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
python motor/revisar.py     # comprueba entorno, protocolos, biblioteca y fichas
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
python motor/render.py Mateo             # horario apaisado, una hoja por semana
python motor/render.py Mateo --caras     # dos hojas por semana, letra más grande

# 6. Fotos de las recetas nuevas (opcional)
python motor/fotos.py Mateo              # escribe los prompts
export GEMINI_API_KEY="..."              # nunca dentro del repositorio
python motor/generar_imagenes.py Mateo   # genera y recorta las imágenes

# 7. Registro y métricas
python motor/registrar.py Mateo --costo 189 --tipo primera_vez
python motor/metricas.py --html          # panel en salidas/metricas.html
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
  prompts_imagen/  prompt de foto de cada receta (generado)
  imagenes/        la foto de cada receta (una vez y para siempre)
datos/             alimentos base · biblioteca de fotografía · registro de consultas
motor/             revisar · ensamblar · validar · fotos · generar_imagenes
                   render · registrar · metricas
pacientes/         casos reales (fuera de Git)
```

---

## Los dos entregables

**`Plan_[Paciente].pdf`** — A4 apaisado, formato horario: los días en columnas y
las comidas en filas, con sus horas. Pensado para imprimir y pegar en la nevera.
Una hoja por semana; con `--caras`, dos hojas por semana (lun–jue / vie–dom) y
letra mayor. En cobre van las preparaciones que tienen receta en el recetario.

**`Recetario_[Paciente].pdf`** — A4 vertical, una receta por página, solo las que
ese plan usa. La negrita de cantidades y verbos la aplica la hoja de estilo: no
hay que resaltar nada a mano. Si la receta tiene foto en `biblioteca/imagenes/`,
va a sangre en el tercio superior; si no la tiene, va una banda del color de
acento y la página se maqueta igual.

---

## Fotografía

Cada receta lleva en su front-matter la variante A–K de la biblioteca editorial
y su color de acento. `motor/fotos.py` rellena la plantilla correspondiente y
deja el prompt listo para pegar en el generador; la imagen se guarda como
`biblioteca/imagenes/[id].png` y **se genera una sola vez en la vida de la
receta**. A partir de ahí, cualquier paciente que la use la recibe con foto sin
coste adicional.

`motor/generar_imagenes.py` las genera con la API de Gemini (Nano Banana 2,
`gemini-3.1-flash-image` por defecto; cambiable con `--modelo`), recorta a A4
**por el borde inferior** —el tercio superior lo reservan los prompts— y
reintenta dos veces antes de anotar el fallo y seguir. **La clave se lee solo de
`GEMINI_API_KEY`**: nunca se escribe en el proyecto.

Esto no reemplaza el flujo de Canva de los recetarios que se venden: son
productos distintos. Aquí se trata del anexo personalizado de cada paciente.

---

## Casos de prueba

`pacientes/_BENCHMARK_Thiago/` es un caso sintético difícil a propósito:
esofagitis eosinofílica con dieta de eliminación de cuatro alimentos,
selectividad alimentaria severa, aversión a texturas mixtas, una alergia rara
fuera del vocabulario del sistema, familia amazónica recién mudada a la costa y
datos contradictorios entre documentos. Sirve para comprobar que el sistema se
detiene donde debe en lugar de producir un plan bonito y equivocado.

`pacientes/_BENCHMARK_Ariana/` es el segundo, y ataca zonas distintas: una
lactante prematura de 11 meses cronológicos y ~9 corregidos, con APLV, anemia
y estreñimiento, y una madre que pide un plan de un mes que cruza el primer
cumpleaños. No hay protocolo para esa edad. Comprueba que el sistema se
detenga en la selección de protocolo y no en F1, que es donde se detiene Thiago.

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
