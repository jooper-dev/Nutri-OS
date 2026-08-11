# Estado del proyecto — Nutri-OS

*Documento de traspaso. Léelo entero antes de tocar nada. Recoge decisiones ya tomadas y sus razones, para que no haya que rediscutirlas.*

Última actualización: agosto 2026, tras el benchmark Thiago.

---

## 1. Qué es esto y para quién

Sistema de generación de planes alimentarios pediátricos para **GrowKids**, la consulta de la Nut. Patricia López (Paty), nutricionista pediátrica en Trujillo, Perú.

El problema que resuelve: cada plan personalizado le costaba horas de trabajo manual. El objetivo no es automatizar su criterio clínico, es quitarle el trabajo mecánico que hay alrededor.

**Dos personas usan el repositorio, y hacen cosas distintas:**

- **Danny** (desarrollador) construye. Trabaja en Claude Code, hace commits, toca protocolos y motor.
- **Paty** (nutricionista) opera. Trabaja en Claude Cowork, nunca ve una terminal, procesa pacientes.

Si estás leyendo esto en una sesión de desarrollo, eres el primer caso.

---

## 2. El principio que sostiene todo

| Va a un modelo | Va a código |
|---|---|
| Leer el caso clínico | Contar frecuencias |
| Escribir y auditar recetas | Filtrar por alergias, edad y textura |
| Redactar la voz de la marca | Validar el plan |
| Describir el plato para la foto | Armar el prompt de imagen |
| — | Maquetar los PDF |

**Nunca cuentes tú.** Si te descubres verificando "¿hay tres menestras esta semana?", estás haciendo el trabajo del validador y lo vas a hacer peor. Ejecuta el script.

La versión anterior de este proyecto falló exactamente por lo contrario: cinco fases encadenadas donde un modelo contaba, se auditaba a sí mismo y maquetaba. Producía planes que parecían bien y no lo estaban.

---

## 3. Anatomía

```
CLAUDE.md          orquestador: las fases y dónde pararse
GUIA_PATY.md       manual de uso, sin nada técnico
ESTADO.md          este archivo

prompts/           PC_CLINICO (F1) · P1_RECETAS v4.3 (F3)
protocolos/        un .yaml por tipo de plan — estructura y frecuencias
reglas_exclusion/  restricciones por edad, con evidencia
biblioteca/        una receta por archivo; crece con el uso
  prompts_imagen/  prompt de foto por receta (generado)
  imagenes/        la foto de cada receta (una vez y para siempre)
datos/             alimentos base · biblioteca de fotografía · consultas.csv
motor/             revisar · ensamblar · validar · fotos · generar_imagenes
                   render · registrar · metricas · migrar_textura · correr
pacientes/         casos reales — FUERA de git
salidas/           metricas.html
```

**Fases:** F1 lectura clínica (modelo) → F2 ensamblaje (código) → F3 recetas nuevas (modelo, contexto limpio por receta) → F3b fotografía → F4 validación (código) → **F5 Puerta de Paty (humano)** → F6 render (código) → F7 registro.

---

## 4. Decisiones tomadas — no las revisites sin motivo nuevo

**Los PDF se generan en local con WeasyPrint, no en Canva ni Google Slides.** Un plan de 4 semanas son ~1.200 etiquetas de texto; reemplazarlas una por una es frágil venga de donde venga. Efecto secundario importante: el sistema ya no usa Google Workspace para nada, así que no hay OAuth ni tokens que caduquen ni credenciales que filtrar.

**La biblioteca de recetas es un caché, no un catálogo cerrado.** No se digitaliza nada por adelantado. Cuando falta una receta, P1 la crea y se guarda; la siguiente paciente que la necesite la tiene gratis. A los pocos meses la mayoría de los planes salen de recetas ya validadas.

**Las frecuencias del protocolo se garantizan por construcción, no se verifican después.** El ensamblador reserva primero las ranuras que las reglas exigen y solo después rellena. Un plan que viola una frecuencia es un bug del motor, no un descuido.

**El validador es independiente y determinista.** Relee protocolo y ficha por su cuenta y recuenta desde cero. Sustituye a la antigua "self-QA" donde un modelo se auditaba a sí mismo.

**La Puerta de Paty no se salta.** El plan se detiene siempre antes de renderizar. `render.py` se niega a trabajar si el validador marcó BLOQUEADO, pero el visto bueno clínico lo da ella.

**Un tipo de plan nuevo es un archivo .yaml nuevo en `protocolos/`, nunca un parche al ensamblador.**

**Las fotos de receta se generan una sola vez en la vida de la receta.** Esto no reemplaza el flujo de Canva de los recetarios que Paty vende: son productos distintos con listón distinto. Aquí se trata del anexo personalizado de cada paciente.

**Las claves de API viven solo en `.env`** (ignorado por git) o en variables de entorno. Nunca en un archivo del proyecto, nunca en un chat. El repositorio ya se filtró una vez por esto.

---

## 5. Reglas que no se rompen

- `pacientes/` nunca se sube a git. Son historiales clínicos de menores.
- `plan.json` no se edita a mano. Si algo está mal, se corrige en el protocolo, en la biblioteca o en la ficha, y se vuelve a ensamblar. Editar la salida destruye la única garantía que da el sistema.
- Las recetas no se inventan dentro del plan. Pasan por P1, con su auditoría de seguridad pediátrica, y aterrizan en `biblioteca/` antes de aparecer en un menú.
- **Si una alergia de la ficha no coincide con ninguna etiqueta del catálogo, se etiqueta el catálogo. Nunca se borra la alergia de la ficha para que el validador calle.**
- Cuando un script falla, se muestra el error tal cual. Los mensajes están escritos para leerse enteros.

---

## 6. El benchmark Thiago y lo que reveló

`pacientes/_BENCHMARK_Thiago/` es un caso sintético difícil a propósito: esofagitis eosinofílica con eliminación de cuatro alimentos, selectividad severa (nueve alimentos aceptados), aversión a texturas mixtas y húmedas, sospecha de alfa-gal sin documentar, familia amazónica recién mudada a la costa, abuela cocinando el almuerzo sin manejar la dieta, y datos contradictorios entre documentos.

**El sistema pasó 10 de 11 controles.** Se detuvo donde debía, detectó que el protocolo `escolar_6_11` era imposible para este paciente (exige huevo y yogurt, ambos eliminados), y creó `escolar_eliminacion_4.yaml` en su lugar. Detectó que la etiqueta `carne_mamifero` no existía en el catálogo y que por tanto la alergia no filtraba nada — y paró a preguntar en vez de arreglarlo solo.

**Reveló un agujero grande, ya tapado:** el sistema no tenía concepto de textura. Cuatro preparaciones húmedas ocupaban las 28 ranuras de media mañana y media tarde de un niño cuya madre dijo "nada aguado" como primera frase. El nombre de un plato nunca delata su textura: "compota de pera" no contiene la palabra "aguado". Se añadió el campo `textura` a alimentos y recetas y `texturas_excluidas` a la ficha. Al revalidar el plan viejo con el filtro nuevo salieron **86 errores**.

**Reveló otro agujero, aún abierto:** ver punto 7.1.

---

## 7. Pendientes, por prioridad

### 7.1 Catálogo regional — el más importante

`datos/alimentos_base.yaml` es costeño. Plátano bellaco, cocona, paiche, cecina, aguaje, tacacho, chonta, camu camu: nada existe. En el benchmark el plan salió con arroz y papa, comida que ese niño no come.

Le va a pasar con cada familia de la sierra y la selva, que en Trujillo son muchas. Hay que ampliar el catálogo con alimentos amazónicos y andinos, con su `textura`, `edad_min_meses`, `alergenos` y `aporta`. Consultar con Paty antes: la disponibilidad y el precio real en Trujillo condicionan qué vale la pena incluir.

### 7.2 Terminar el caso Thiago

Re-ensamblar con `texturas_excluidas` activo, crear con P1 los snacks secos que pida el motor, pasar la Puerta de Paty, renderizar con `--caras` y registrar. No se ha llegado nunca al PDF de este caso.

### 7.3 Reglas de protocolo declaradas pero no implementadas

El motor las ignora y el validador solo avisa:

- `max_recetas_nuevas_semana` (selectividad) — relevante clínicamente: en selectividad severa la novedad es el riesgo.
- `introduccion_progresiva`, `progresion_textura`, `exclusiones_duras` (protocolo de ablactancia).

### 7.4 Hoja para el cuidador secundario

El benchmark lo dejó claro: si el almuerzo lo cocina la abuela y no maneja la dieta, el 30 % de las calorías depende de alguien que no leyó el plan. Haría falta un tercer entregable corto, en lenguaje directo, con lo que esa persona necesita saber.

### 7.5 Probar la generación de imágenes de verdad

`motor/generar_imagenes.py` nunca se ha ejecutado con una clave real. La ruta HTTP está verificada (llega a la API y devuelve error de clave inválida correctamente), pero no se ha generado ninguna imagen ni comprobado cómo queda embebida en el recetario.

### 7.6 Higiene

- Fusionar la rama `codex/replace-with-zip` a `main`.
- Rotar la clave de Gemini: pasó por un chat.
- Confirmar que el cliente OAuth de Google del repositorio antiguo (`nutrios-492116`) fue eliminado. Borrar los archivos no bastaba, seguían en el historial de git.
- `plan.json` y `reporte_qa.md` se regeneran en cada corrida y ensucian `git status`. Valorar ignorarlos; `ficha.md` sí conviene conservarla.

---

## 8. Entorno

Windows. Python 3.12.

WeasyPrint necesita las bibliotecas nativas de GTK, que en Windows no vienen con el paquete de pip. Ya está resuelto en la máquina de Danny: MSYS2 en `C:\msys64`, `pacman -S mingw-w64-x86_64-pango`, y la variable de entorno `WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin`. Verificado: los PDF se generan.

Comprobación de salud del sistema, siempre lo primero:

```bash
python motor/revisar.py
```

---

## 9. Cómo se ve un ciclo completo

```bash
# Paty deja el material en pacientes/[Nombre]/fuente/
# F1: con prompts/PC_CLINICO.md → ficha.md

python motor/correr.py [Nombre]          # ensambla y valida, para en la Puerta
# si falla por biblioteca insuficiente → F3 con P1, contexto limpio por receta
python motor/fotos.py [Nombre]           # prompts de imagen
python motor/generar_imagenes.py [Nombre]

# Paty revisa reporte_qa.md y aprueba

python motor/render.py [Nombre] --caras
python motor/registrar.py [Nombre] --costo 189 --tipo primera_vez
python motor/metricas.py --html
```
