---
paciente: "Mateo R."
edad_meses: 84
edad_texto: "7 años"
fecha: 2026-08-10
sexo: M
peso_kg: 22.4
talla_cm: 121
zscore_pt: -0.4
zscore_te: -1.1
semanas_plan: 2
protocolo_sugerido: escolar_6_11
requerimiento_kcal: 1650
metodo_kcal: "IOM/DRI 2023 — EER niños 3–8 a, actividad moderada"

diagnosticos: [anemia]
diagnostico_texto: >
  Anemia ferropénica leve. Hb 10.8 g/dL.

alergias: [lacteos]
alergias_sospechadas: []
rechazos: [pescado]
favoritos: [pollo, palta]
antropometria_previa: []

# Caso de ejemplo: las «fuentes» son ficticias y están en fuentes_originales/.
# La procedencia se rellena igual, porque es obligatoria y porque el ejemplo
# tiene que enseñar el formato correcto.
procedencia:
  edad_meses: "derivado: f. nac. declarada en LEEME.txt"
  peso_kg: "LEEME.txt · p. 1 (caso de ejemplo)"
  talla_cm: "LEEME.txt · p. 1 (caso de ejemplo)"
  zscore_pt: "derivado: WHO 2007 peso/edad varones 84 m"
  zscore_te: "derivado: WHO 2007 talla/edad varones 84 m"
  requerimiento_kcal: "derivado: IOM/DRI EER niños 3–8 a, actividad moderada"
  diagnosticos: "LEEME.txt · p. 1 (caso de ejemplo)"
  alergias: "LEEME.txt · p. 1 (caso de ejemplo)"
datos_sin_fuente: []
parada_clinica_revisada: {}

porciones:
  cereal: "3 cdas"
  acompanante: "1 porción"
  carbohidrato: "4 cdas"
  proteina: "40 g en crudo"
  proteina_hierro: "30 g en crudo"
  menestra: "3 cdas"
  verdura: "½ taza"
  ensalada_grasa: "½ taza"
  fruta: "1 unidad pequeña"
  fruta_vitc: "1 unidad pequeña"
  grasa: "1 cdta"
  base: "1 porción"
  crujiente: "2 cdas"
  bebida: "½ taza"

bloqueantes: []
---

## Lectura del caso

Escolar de 7 años con anemia ferropénica leve confirmada por laboratorio. Peso adecuado
para la talla, con talla ligeramente por debajo de la mediana. Alergia a la proteína de
leche de vaca ya establecida. Rechaza el pescado de forma consistente.

## Estrategia nutricional

Priorizar hierro en cada almuerzo y cena, siempre acompañado de vitamina C en la misma
comida. Subir la frecuencia de menestras. Mantener densidad calórica con grasas saludables
de origen no lácteo.

## Cómo se derivaron las porciones

1650 kcal repartidas en cinco tiempos, traducidas a medidas caseras habituales para la edad.

--- NOTA PARA PATY ---

FICHA DE EJEMPLO — datos ficticios, creada para probar el motor. No corresponde a ninguna paciente real.
