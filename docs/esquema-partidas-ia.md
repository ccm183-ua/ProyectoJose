# Esquema del fichero de partidas generado por IA

Contrato del fichero XML que Claude produce, con la skill de
`docs/skill-presupuestos/SKILL.md` y el paquete de contexto de
`scripts/export_context_pack.py`, para que la aplicación lo convierta en un
presupuesto. Ver `docs/superpowers/plans/2026-08-04-paquete-contexto-ia.md`
(Tarea 4) para el porqué de cada regla.

> Este documento define el contrato. El validador y el importador que lo
> apliquen son un plan aparte (ver "Fuera de alcance" en el plan citado). Se
> documenta ahora, antes de escribir el validador, para que la skill se
> redacte contra un contrato firme, no contra una intención vaga.

## Principio rector

**El esquema es la defensa, no la skill.** Una instrucción en un prompt se
puede ignorar o diluir en una conversación larga; un campo que no existe en
el esquema no se puede rellenar por mucho que el modelo "decida" hacerlo. Por
eso el fichero **no tiene elemento de precio**: no es una regla que Claude
deba recordar, es una imposibilidad estructural. El precio lo pone siempre
la aplicación, cruzando cada partida contra `patrones.csv` con el mismo
comparador estricto (`historical_comparator.py`) que ya decide `exact` /
`comparable` / `related` / `incompatible` para el resto de la aplicación.

## Ejemplo completo

```xml
<?xml version="1.0" encoding="UTF-8"?>
<presupuesto>
  <partida>
    <concepto>Reparacion de revoco de fachada con mortero R4</concepto>
    <unidad>m2</unidad>
    <cantidad estado="conocida">120</cantidad>
    <modulo>fachada</modulo>
    <nueva>false</nueva>
  </partida>
  <partida>
    <concepto>Sellado de junta estructural</concepto>
    <unidad>ml</unidad>
    <cantidad estado="pendiente"/>
    <modulo>fachada</modulo>
    <nueva>true</nueva>
  </partida>
</presupuesto>
```

## Elementos y atributos

| Elemento / atributo | Obligatorio | Contenido |
|---|---|---|
| `<presupuesto>` | sí (raíz) | Uno o más `<partida>`. |
| `<partida><concepto>` | sí | Texto libre: qué se hace. Frase corta, sin precio ni referencia a fuente. |
| `<partida><unidad>` | sí | Debe pertenecer a las unidades observadas en `repertorio.csv` (`m2`, `ml`, `ud`, `p.a.`...). |
| `<partida><cantidad>` | sí | Vacío si `estado="pendiente"`; numérico si `estado="conocida"`. |
| `<partida><cantidad estado="…">` | sí | `conocida` o `pendiente`. Sin tercer valor: no existe "estimada". |
| `<partida><modulo>` | sí | Debe pertenecer a los módulos de `vocabulario.md` (`fachada`, `alicatado`, `carpinteria`...). |
| `<partida><nueva>` | sí | `true` o `false`. |

No hay más elementos. En particular: **no hay `<precio>`, `<precio_unitario>`
ni `<importe>`** en ningún punto del esquema.

## Lo que el esquema impide por construcción

- **Precio inventado.** No existe el campo. Es la defensa principal, y no
  depende de que Claude obedezca ninguna instrucción.
- **Cantidad estimada disfrazada de dato real.** `estado` es obligatorio y
  cerrado a dos valores. Una cantidad "razonable pero no confirmada" no
  tiene dónde ir — tiene que declararse `pendiente`.
- **Partida nueva colada como habitual.** `nueva` es obligatorio en cada
  partida, no opcional con valor por defecto `false`. Si Claude lo omite,
  la partida se rechaza entera (ver tabla de abajo) en vez de asumir que es
  conocida.
- **Módulo o unidad inventados.** Ambos se validan contra listas cerradas
  que salen del propio paquete exportado (`vocabulario.md` y
  `repertorio.csv`), no de una lista mantenida aparte que se pueda
  desincronizar.

## Qué hará el validador ante cada violación

Documentado ahora para que la skill se escriba sabiendo exactamente qué
pasa con cada fallo, aunque el validador se implemente en un plan posterior.

| Violación | Efecto |
|---|---|
| `modulo` no está en `vocabulario.md` | Se rechaza esa partida, con el motivo. El resto del presupuesto se procesa igual. |
| `unidad` no está entre las unidades observadas | Se rechaza esa partida, con el motivo. |
| Falta el atributo `estado` en `cantidad` | Se rechaza esa partida: un estado ausente no se interpreta como "conocida" ni como "pendiente". |
| Falta el elemento `nueva` | Se rechaza esa partida: la ausencia no se interpreta como `false`. |
| `concepto` vacío | Se rechaza esa partida. |
| Aparece un elemento no previsto en este esquema (p. ej. `precio`) | Se rechaza **el fichero completo**: es la señal de que algo aguas arriba dejó de respetar el contrato, no un error de una partida suelta. |
| XML mal formado | Se rechaza el fichero completo, sin intentar recuperar partidas sueltas. |

El criterio general: un fallo de datos en una partida (módulo, unidad,
cantidad, `nueva`) descarta solo esa partida y dice por qué. Un fallo de
forma (un campo que no debería existir, XML inválido) descarta el fichero
entero, porque indica que el contrato en sí se ha roto, no un dato concreto.

## Definición formal (XSD)

Para que "el esquema" sea algo verificable y no solo esta prosa, la
estructura anterior en XSD:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">

  <xs:simpleType name="EstadoCantidad">
    <xs:restriction base="xs:string">
      <xs:enumeration value="conocida"/>
      <xs:enumeration value="pendiente"/>
    </xs:restriction>
  </xs:simpleType>

  <xs:complexType name="Cantidad">
    <xs:simpleContent>
      <xs:extension base="xs:decimal">
        <xs:attribute name="estado" type="EstadoCantidad" use="required"/>
      </xs:extension>
    </xs:simpleContent>
  </xs:complexType>

  <xs:complexType name="Partida">
    <xs:sequence>
      <xs:element name="concepto" type="xs:string" minOccurs="1"/>
      <xs:element name="unidad" type="xs:string" minOccurs="1"/>
      <xs:element name="cantidad" type="Cantidad" minOccurs="1"/>
      <xs:element name="modulo" type="xs:string" minOccurs="1"/>
      <xs:element name="nueva" type="xs:boolean" minOccurs="1"/>
    </xs:sequence>
  </xs:complexType>

  <xs:element name="presupuesto">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="partida" type="Partida" minOccurs="1" maxOccurs="unbounded"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>

</xs:schema>
```

Nótese que el XSD **no puede** expresar las dos reglas más importantes: que
`modulo` y `unidad` pertenezcan a las listas del paquete exportado (son
listas de datos, no de tipo) y que el fichero completo del paquete no tenga
más de una obsolescencia (`vocabulario.md`/`repertorio.csv` cambian con cada
exportación). Esas dos comprobaciones son responsabilidad del validador
contra el paquete vigente, no del XSD. El XSD cubre la forma; el paquete
cubre el vocabulario.

## Cuándo `cantidad estado="pendiente"`

La skill debe preferir preguntar en la conversación antes de generar el
fichero. `pendiente` es para cuando, tras preguntar, el dato sigue sin
estar disponible — no es la opción por defecto ni un atajo para no
preguntar. Una partida con `estado="pendiente"` llega al importador visible
y sin cantidad, nunca con una cifra puesta "para no dejarlo en blanco".
