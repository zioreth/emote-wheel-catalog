# Emote Wheel — catálogo revisado

Este repositorio aloja **solo las adiciones al catálogo integrado** de Emote Wheel. No contiene claves de GW2 ni ruedas personales.

## Funcionamiento

- **Discover emotes** consulta la API pública y la tabla de emotes de la wiki a las 13:17 UTC (08:17 Colombia), o manualmente desde Actions. GitHub puede retrasar ejecuciones programadas.
- Una novedad abre un pull request en `catalog/<comando>` y menciona a `zioreth` (variable de repositorio `REVIEWER`, o propietario por defecto).
- La propuesta no se publica sola. Corrige sus datos, añade el ícono si falta y cambia `Reviewed` a `true`.
- Ejecuta **Validate** manualmente seleccionando la rama propuesta. Los PR creados mediante GITHUB_TOKEN pueden no lanzar por sí solos los workflows; un cambio humano también puede lanzar la validación.
- Fusiona el PR aprobado en `main`. **Publish approved catalog** valida el conjunto y publica `catalog.json` en `published`.
- El mod consulta el archivo cada 12 horas y conserva los datos en su almacenamiento local. Las novedades se aplican al cerrar el editor y la rueda.

URL pública: https://raw.githubusercontent.com/zioreth/emote-wheel-catalog/published/catalog.json

## Recibir avisos

Los PR y las incidencias mencionan al revisor. En GitHub, configura las notificaciones de menciones por correo en Settings → Notifications. Para seguir todo el repositorio también puedes usar Watch → Custom → Pull requests e Issues. La entrega al correo depende de esas preferencias; el proceso no necesita tu contraseña de correo. No se ha configurado Discord.

Un fallo de búsqueda abre una sola incidencia de salud; no repite mensajes mientras permanezca abierta. Al recuperarse las fuentes se cierra automáticamente. Los fallos de publicación también generan una incidencia. Si GitHub Actions no puede ejecutarse (por ejemplo, workflows desactivados), no puede avisar de su propia ausencia: revisa Actions cuando haya inactividad prolongada. GitHub puede desactivar tareas programadas de repositorios públicos tras 60 días sin actividad.

## Revisar una propuesta

1. Comprueba las fuentes enlazadas y que el comando ejecuta realmente un emote publicado.
2. Completa `Name` (español), `English`, y opcionalmente `German` / `French`; ajusta `Category`, `Unlock` y `UnlockItem`.
3. Revisa el ícono y sus condiciones de uso. Si falta, prepara un PNG de 16–256 px, máximo aproximado de 135 KB, y ejecuta:

   `python scripts/catalog.py icon entries/comando.json icono.png`

4. Conserva los enlaces de atribución en `Sources`; pon `Reviewed: true`.
5. Ejecuta Validate y fusiona si pasa. Para descartar, cierra el PR: no se volverá a proponer ese comando mientras exista ese PR cerrado. Para reconsiderarlo, reabre el PR.

Un dato encontrado en una página no es una instrucción: no se ejecuta código de las fuentes ni comandos de prueba en GW2. No se publican traducciones generadas ni imágenes nuevas automáticamente.

## Validación local

```
python -m unittest discover -s tests -v
python scripts/catalog.py discover
python scripts/catalog.py validate
```

Sin `--live`, Discover solo muestra un informe. `--live` requiere GITHUB_TOKEN y GITHUB_REPOSITORY; nunca imprime el token. No pongas credenciales en archivos ni incidencias.

El esquema 1 solo agrega entradas. No permite eliminar o editar entradas ya publicadas: eso requiere una migración coordinada del cliente. Esta regla evita romper ruedas guardadas y mantiene consistente su caché. No añadas comandos que ya estén en baseline.json.

## Operación

- Workflow permissions: read por defecto; cada workflow declara solo los permisos de escritura que necesita.
- Habilitar la opción que permite a GitHub Actions crear pull requests.
- `main` contiene las entradas revisadas; `published/catalog.json` es el único archivo que consume el mod.
- Los íconos van dentro del JSON en base64 para que datos y arte se publiquen juntos. Límite del catálogo: 2 MiB y 250 adiciones.
- Ante un error o un catálogo incompleto, no se reemplaza el último catálogo válido.

Fuentes: https://api.guildwars2.com/v2/emotes?ids=all y https://wiki.guildwars2.com/wiki/Emote
