# IA4CAST - Sistema de pronostico de demanda

Aplicacion de escritorio Windows para pronostico de demanda retail con
clasificacion ABC-XYZ + SBC y intervalos de confianza por quantile regression.

---

## Estructura del proyecto

```
ia4cast_app/
├── main.py                    Punto de entrada de la app
├── IA4CAST.spec               Spec de PyInstaller
├── setup.iss                  Script de Inno Setup
├── requirements.txt           Dependencias de produccion
├── config/
│   └── default.yaml           Plantilla de config.yaml
├── ia4cast/
│   ├── __init__.py
│   ├── core/                  Logica de negocio (sin UI)
│   │   ├── config.py          Configuracion + logging + carpetas
│   │   ├── security.py        Cifrado Fernet
│   │   ├── data_loader.py     Lectura Excel/CSV/ODS + stub PostgreSQL
│   │   ├── classification.py  ABC-XYZ + SBC + anomalias
│   │   ├── forecasting.py     Motor con 3 rutas + IC quantile
│   │   ├── metrics.py         WAPE, MASE, sMAPE, bias
│   │   ├── alerts.py          Alertas seccion 5.3 manual
│   │   ├── comparison.py      Comparativa pronostico vs anos anteriores
│   │   └── forecast_store.py  Guardar/cargar pronosticos
│   ├── ui/                    Interfaz PySide6
│   │   ├── styles.py          Hoja QSS corporativa
│   │   ├── widgets.py         Widgets reutilizables
│   │   ├── workers.py         Workers asincronos
│   │   ├── sesion.py          Estado compartido
│   │   ├── ventana_principal.py
│   │   ├── pagina_carga.py
│   │   ├── pagina_dashboard.py
│   │   ├── pagina_pronostico.py
│   │   └── pagina_resultados.py
│   └── resources/             Iconos (icono.ico)
└── docs/                      Manuales (se incluyen en el instalador)
```

---

## 1. Desarrollo - ejecutar desde codigo fuente

Requisitos: Python 3.11 o 3.12 en Windows (64 bits).

```cmd
:: Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate

:: Instalar dependencias
pip install -r requirements.txt

:: Ejecutar
python main.py
```

Al primer arranque la app crea automaticamente:
- `%APPDATA%\IA4CAST\config.yaml`
- `%APPDATA%\IA4CAST\keys\fernet.key`  (permisos 0o600)
- `%APPDATA%\IA4CAST\logs\`
- `%APPDATA%\IA4CAST\cache\`
- `%APPDATA%\IA4CAST\pronosticos_guardados\`

---

## 2. Empaquetado a `.exe` con PyInstaller

Sigue la seccion 3.1.1 del manual de administracion.

```cmd
:: Con el venv activado:
pyinstaller IA4CAST.spec --clean --noconfirm
```

Tarda 3-8 minutos. El resultado queda en `dist\IA4CAST.exe`.

> Si falla por algun import dinamico, anade el modulo a `hiddenimports`
> en `IA4CAST.spec` y vuelve a empaquetar.

### Verificar el .exe

```cmd
dist\IA4CAST.exe
```

Comprueba que abre la ventana, carga un Excel y genera un pronostico
sin errores.

---

## 3. Instalador con Inno Setup

Sigue la seccion 3.1.2 del manual.

1. Descarga e instala Inno Setup 6: https://jrsoftware.org/isdl.php
2. Abre `setup.iss` con Inno Setup Compiler.
3. Compilar (F9). Genera `installer\IA4CAST_Setup_v1.0.exe`.

### Pruebas del instalador

1. Copia `IA4CAST_Setup_v1.0.exe` a una maquina limpia.
2. Click derecho -> "Ejecutar como administrador".
3. Seguir el asistente.
4. Comprobar que:
   - Se crea acceso directo en el escritorio y menu Inicio.
   - Al abrir la app, se crea `%APPDATA%\IA4CAST\` con la estructura.
   - Se puede cargar un Excel y generar un pronostico.
5. Desinstalar desde Panel de Control y verificar que el `.exe` se elimina.
   (Los datos del usuario en `%APPDATA%` se preservan).

---

## 4. Activar PostgreSQL (opcional)

Por defecto la conexion a PostgreSQL viene como **stub** (estructura lista
pero no se usa). Para activarla:

1. Editar `%APPDATA%\IA4CAST\config.yaml`:
   ```yaml
   base_dades:
     habilitat: true
     amfitrio: dwh.empresa.local
     port: 5432
     bd: vendes_produccio
     usuari: ia4cast_ro
     contrasenya_xifrada: ''   # Se rellena despues
   ```
2. Generar la contrasenya cifrada con la utilidad cifradora (de momento se
   puede hacer desde un Python interactivo):
   ```python
   from ia4cast.core.security import cifrar_texto
   print(cifrar_texto('TU_CONTRASENYA'))
   ```
   Pegar el resultado en `contrasenya_xifrada`.
3. Descomentar la implementacion real en `ia4cast/core/data_loader.py`
   (esta marcada con un comentario explicativo).

Crear el usuario PostgreSQL con permisos minimos segun la seccion 6.3.1
del manual.

---

## 5. Conformidad con el manual

| Seccion del manual | Implementacion |
|---|---|
| 3.4 Estructura config.yaml | `core/config.py` + `config/default.yaml` |
| 4.1 3 rutas de modelos | `core/forecasting.py` (regular/intermitente/long-tail) |
| 5.1 Logging con rotacion | `core/config.py` `TimedRotatingFileHandler` |
| 5.3 Alertas y umbrales | `core/alerts.py` |
| 6.2 Esquema de datos | `core/data_loader.py` `COLUMNAS_REQUERIDAS` |
| 6.3 Conexion PostgreSQL | `core/data_loader.py` `_leer_postgresql` (stub) |
| 7.2 Cifrado Fernet | `core/security.py` |
| 7.4.1 Acceso restringido | App de escritorio nativa, sin servidor de red |

---

## 6. Resolucion de problemas

### El `.exe` no arranca o se cierra al instante

Causas habituales:
- `LightGBM` no encuentra su DLL: verifica que `collect_dynamic_libs('lightgbm')`
  se ejecuta sin errores en el spec.
- `numba` no encuentra cache writable: revisa permisos en `%APPDATA%`.

Para diagnosticar, edita el spec poniendo `console=True` y vuelve a empaquetar.
Asi veras los errores en consola al ejecutar.

### "Faltan columnas requeridas"

El fichero de entrada debe tener exactamente las columnas:
`Order Date`, `Category`, `Sub-Category`, `Product ID`, `Product Name`,
`Quantity`. Cualquier otra columna se ignora.

### Los nombres de productos salen como `gAAAAA...`

Estan cifrados (correcto). En la UI se descifran automaticamente para
mostrarse al usuario. Si quieres exportar en claro, usa el boton
"Exportar tabla" desde la pagina Resultados (descifra antes de exportar).

### El pronostico tarda mucho

- Para catalogos > 5.000 productos en una maquina con 8 GB de RAM
  el procesamiento puede tomar varios minutos. Cierra otras aplicaciones.
- Para catalogos > 20.000 productos consulta la seccion 5.5.1 del manual
  (procesamiento por lotes).
