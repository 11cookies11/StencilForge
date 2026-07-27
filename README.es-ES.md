# StencilForge

<p align="left">
  <a href="https://github.com/11cookies11/StencilForge">
    <img alt="GitHub Repo" src="https://img.shields.io/badge/GitHub-11cookies11%2FStencilForge-181717?logo=github&logoColor=white">
  </a>
  <a href="https://github.com/11cookies11/StencilForge/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/github/license/11cookies11/StencilForge?color=2b6cb0">
  </a>
  <a href="https://github.com/11cookies11/StencilForge/stargazers">
    <img alt="Stars" src="https://img.shields.io/github/stars/11cookies11/StencilForge?style=flat">
  </a>
  <a href="https://github.com/11cookies11/StencilForge/issues">
    <img alt="Issues" src="https://img.shields.io/github/issues/11cookies11/StencilForge">
  </a>
  <a href="https://github.com/11cookies11/StencilForge/releases">
    <img alt="Release" src="https://img.shields.io/github/v/release/11cookies11/StencilForge">
  </a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="Vue" src="https://img.shields.io/badge/Vue-3-42b883?logo=vue.js&logoColor=white">
  <img alt="CadQuery" src="https://img.shields.io/badge/CadQuery-2.4-3b82f6">
  <img alt="VTK" src="https://img.shields.io/badge/VTK-9.3-8a2be2">
</p>

<p align="center">
  <img alt="StencilForge logo" src="assets/store/logo_1080x1080.png" width="220">
</p>

StencilForge es una herramienta de escritorio para generar modelos STL de stencils para PCB a partir de archivos Gerber.

## Descripción general

StencilForge convierte exportaciones Gerber y Excellon en modelos STL 3D para stencils de PCB y accesorios de locator. Soporta una interfaz de usuario (UI) de escritorio, procesamiento de geometría configurable y backends tanto de CadQuery como de Trimesh.

## Aspectos destacados

- Pipeline rápido de Gerber a STL
- Backend de CadQuery o Trimesh
- Recortes de stencil con offsets configurables
- Estructura de locator: escalón (step) o pared (wall)
- Ventana de vista previa VTK sin WebGL

## Galería

**Stencil impreso**
![Printed stencil](assets/images/实物照片.jpg)

**Pantalla principal de la UI**
![UI main screen](assets/images/菜单照片.png)

**Vista previa STL**
![STL preview](assets/images/预览照片.png)

## Inicio rápido

1. Crea un entorno virtual e instala las dependencias: `pip install -r requirements.txt`
2. Instala el paquete: `pip install -e .`
3. Actualiza `config/stencilforge.json` según sea necesario
4. Ejecuta:

```bash
stencilforge <gerber_dir> <output_stl>
```

## UI

Construye la UI:

```bash
cd ui-vue
npm install
npm run build
```

Lanza la UI de escritorio:

```bash
stencilforge-ui
```

## Parámetros de configuración

- `paste_patterns`: patrones de archivos de la capa de pasta
- `outline_patterns`: patrones de la capa de contorno de la placa (board outline)
- `thickness_mm`: grosor del stencil
- `paste_offset_mm`: offset de la apertura, los valores negativos reducen las aperturas
- `outline_margin_mm`: margen de contorno alternativo cuando no existe un archivo de contorno
- `output_mode`: `holes_only` o `solid_with_cutouts`
- `model_backend`: `trimesh` o `cadquery`
- `locator_enabled`: habilita la estructura del locator
- `locator_mode`: `step` o `wall`
- `locator_height_mm`: altura de la pared del locator
- `locator_width_mm`: ancho de la pared del locator
- `locator_clearance_mm`: espacio de holgura del locator
- `locator_step_height_mm`: altura del escalón del locator
- `locator_step_width_mm`: ancho del escalón del locator
- `locator_open_side`: lado abierto (`none/top/right/bottom/left`)
- `locator_open_width_mm`: ancho de la abertura
- `stl_linear_deflection`: deflexión lineal de STL en mm
- `stl_angular_deflection`: deflexión angular de STL en radianes
- `arc_steps`: número de pasos de aproximación de arco
- `curve_resolution`: resolución del buffer de círculo
- `qfn_regen_enabled`: habilita la regeneración de aperturas QFN
- `qfn_min_feature_mm`: tamaño mínimo de característica imprimible
- `qfn_confidence_threshold`: umbral de confianza para la regeneración de QFN
- `qfn_max_pad_width_mm`: ancho máximo de pad considerado para QFN

## Convenciones

- Registro de cambios: `CHANGELOG.md`
- Mensajes de commit y títulos de PR: Conventional Commits
- Documentación comunitaria: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`
- Plantillas de Issue y PR: `.github/`

## Licencia

GPL-3.0-only. Ver `LICENSE`.
