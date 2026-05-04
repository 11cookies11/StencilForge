"""Fix feature texts to be under 200 chars for Windows Store."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "dist-msix" / "listingData-9PPS554SNTGV-1152921505700952133.csv"


def main() -> None:
    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # All features must be <= 200 chars per language
    features = {
        305: {  # FDM 3D Printer Optimization
            4: (
                "FDM 3D Printer Optimization  "
                "FDM profile presets with auto thickness management. "
                "PCB top/bottom/dual paste support. "
                "Smart aperture via solder volume calculator. "
                "QFN grouped slots and corner bridges."
            ),
            5: (
                "FDM 3D 打印机专属优化  "
                "FDM 预设自动管理钢网厚度。PCB 正反面焊膏支持。"
                "智能开口优化与焊锡体积计算。"
                "QFN 分组槽与拐角桥接。"
            ),
            6: (
                "FDM-3D-Drucker-Optimierung  "
                "FDM-Profilvorgaben mit auto. Dickenverwaltung. "
                "Pastenunterstuetzung fuer beide Seiten. "
                "Aperturoptimierung mit Lotvolumenrechner. "
                "QFN-Schlitzkompensation."
            ),
            7: (
                "FDM 3Dプリンター専用最適化  "
                "FDMプロファイルプリセットで厚みを自動管理。"
                "PCB両面ペースト対応。"
                "はんだ量計算器によるスマート開口最適化。"
                "QFNグループスロットとコーナーブリッジ。"
            ),
            8: (
                "Optimizacion para Impresora 3D FDM  "
                "Perfiles FDM con gestion automatica de grosor. "
                "Soporte de pasta en ambas caras. "
                "Calculadora de volumen para optimizacion. "
                "Ranuras QFN agrupadas y puentes."
            ),
        },
        306: {  # PCB Stencil Generation
            4: (
                "PCB Stencil Generation  "
                "One-click Gerber-to-STL from folder or ZIP. "
                "Auto-detects paste layers, outlines, and drill files. "
                "Solid or holes-only output. Readable generation report."
            ),
            5: (
                "PCB 钢网生成  "
                "从文件夹或 ZIP 一键 Gerber 转 STL。"
                "自动识别焊膏层、板框层与钻孔文件。"
                "实体/仅开孔输出，可读生成报告。"
            ),
            6: (
                "PCB-Schablonengenerierung  "
                "Ein-Klick-Gerber-zu-STL aus Ordner oder ZIP. "
                "Auto-Erkennung von Pasten-, Kontur- und Bohrdateien. "
                "Volumen- oder Nur-Oeffnungen-Modus."
            ),
            7: (
                "PCB ステンシル生成  "
                "フォルダ/ZIPからGerberをワンクリックでSTLに変換。"
                "ペースト層・外形・ドリルファイルを自動検出。"
                "ソリッド/開口のみの出力モード。"
            ),
            8: (
                "Generacion de plantillas PCB  "
                "Conversion Gerber a STL con un clic desde carpeta o ZIP. "
                "Deteccion automatica de capas y taladros. "
                "Modo solido o solo aperturas."
            ),
        },
        307: {  # Aperture Rules & Volume Calculator
            4: (
                "Aperture Rules & Volume Calculator  "
                "Pad-level aperture adjustment by priority. "
                "Solder volume calculator from pad geometry. "
                "Smart optimization: area > volume > aperture > rule. "
                "JSON import/export."
            ),
            5: (
                "开口规则与焊锡体积计算器  "
                "焊盘级开口规则，按优先级与具体度排序。"
                "焊锡体积计算：焊盘 x 厚度 x 转印系数。"
                "智能优化：面积 -> 体积 -> 开口 -> 规则。"
                "JSON 导入导出。"
            ),
            6: (
                "Aperturregeln & Volumenrechner  "
                "Pad-Aperturregeln nach Prioritaet/Spezifitaet. "
                "Lotvolumenrechner aus Pad-Geometrie. "
                "Optimierung: Flaeche -> Volumen -> Apertur -> Regel. "
                "JSON-Import/Export."
            ),
            7: (
                "開口ルールとはんだ量計算器  "
                "パッド単位の開口調整ルール（優先度/具体度順）。"
                "はんだ量計算：パッド x 厚み x 転写率。"
                "スマート最適化：面積->体積->開口->ルール。"
                "JSONインポート/エクスポート。"
            ),
            8: (
                "Reglas de Apertura y Calculadora  "
                "Reglas de apertura por pad por prioridad. "
                "Calculadora desde geometria del pad. "
                "Optimizacion: area -> volumen -> apertura -> regla. "
                "Importacion/exportacion JSON."
            ),
        },
        308: {  # Generation Parameters
            4: (
                "Generation Parameters  "
                "Thickness, paste offset, mask opening scale, board margins. "
                "Arc steps and curve resolution tuning. "
                "Basic/advanced config sections. "
                "Printer profile switching (generic / FDM)."
            ),
            5: (
                "生成参数配置  "
                "钢网厚度、焊膏偏移、阻焊系数、板框边距。"
                "圆弧步数与曲线分辨率调节。"
                "基础/高级配置分层。"
                "打印机类型切换（通用 / FDM）。"
            ),
            6: (
                "Parameterkonfiguration  "
                "Dicke, Pastenversatz, Maskenskalierung, Raender. "
                "Bogenschritte und Kurvenaufloesung. "
                "Basis-/Erweiterte-Einstellungen. "
                "Druckerprofil-Umschaltung (generisch / FDM)."
            ),
            7: (
                "生成パラメータ設定  "
                "厚み、ペーストオフセット、マスクスケール、マージン。"
                "円弧ステップと曲線解像度の調整。"
                "基本/高度設定の分離。"
                "プリンタープロファイル切替（汎用/FDM）。"
            ),
            8: (
                "Parametros de generacion  "
                "Grosor, offset de pasta, escala de mascara, margenes. "
                "Pasos de arco y resolucion de curva. "
                "Configuracion basica/avanzada. "
                "Perfiles de impresora (generico / FDM)."
            ),
        },
        309: {  # Positioning Structure
            4: (
                "Positioning Structure Design  "
                "Optional PCB locator with step or wall modes. "
                "Adjustable height, width, clearance, and open side. "
                "Parametric step dimensions for precise alignment."
            ),
            5: (
                "定位结构设计  "
                "可选PCB定位结构，台阶或外框模式。"
                "可调高度、宽度、间隙与开口方向。"
                "台阶尺寸参数化，精确对位。"
            ),
            6: (
                "Positionierungsstrukturen  "
                "Optionale PCB-Positionierung (Stufen- oder Wandmodus). "
                "Einstellbare Hoehe, Breite, Abstand, Oeffnungsrichtung."
            ),
            7: (
                "位置決め構造設計  "
                "段差型/外枠型のPCB位置決め（オプション）。"
                "高さ・幅・クリアランス・開口方向を調整可能。"
            ),
            8: (
                "Estructuras de posicionamiento  "
                "Posicionador PCB opcional (modo escalonado o pared). "
                "Altura, ancho, holgura y direccion ajustables."
            ),
        },
        310: {  # Desktop Experience
            4: (
                "Desktop Application Experience  "
                "Window auto-adapts to screen size on startup. "
                "Built-in STL 3D preview window. "
                "Path memory and default output pre-fill. "
                "Generation log for troubleshooting."
            ),
            5: (
                "桌面应用体验  "
                "启动窗口自适应屏幕尺寸。内置STL 3D预览窗口。"
                "路径记忆与默认输出预填。生成日志便于排错。"
            ),
            6: (
                "Desktop-Anwendungserlebnis  "
                "Automatische Fenstergroessenanpassung. "
                "Integrierte STL-3D-Vorschau. "
                "Pfadspeicherung und Standard-Ausgabepfad."
            ),
            7: (
                "デスクトップアプリ体験  "
                "起動時に画面サイズへ自動適応。"
                "内蔵STL 3Dプレビューウィンドウ。"
                "パス記憶と既定出力先の事前入力。"
            ),
            8: (
                "Experiencia de aplicacion de escritorio  "
                "Ventana adaptable al tamano de pantalla. "
                "Vista previa STL 3D integrada. "
                "Memoria de rutas y salida pre-rellenada."
            ),
        },
        311: {  # i18n
            4: (
                "Multilingual Support (i18n)  "
                "Complete UI in 5 languages: zh-CN, English, Japanese, German, Spanish. "
                "Switch language in-app. CLI via --locale flag."
            ),
            5: (
                "多语言支持（i18n）  "
                "简体中文、英语、日语、德语、西班牙语5语言完整UI。"
                "应用内切换语言，CLI通过--locale切换。"
            ),
            6: (
                "Mehrsprachigkeit (i18n)  "
                "UI in 5 Sprachen: Chinesisch, Englisch, Japanisch, Deutsch, Spanisch. "
                "Sprachwechsel in der App und per --locale in der CLI."
            ),
            7: (
                "多言語対応（i18n）  "
                "5言語対応（中国語・英語・日本語・ドイツ語・スペイン語）。"
                "アプリ内で切替、CLIは--localeで切替。"
            ),
            8: (
                "Soporte multilenguaje (i18n)  "
                "UI en 5 idiomas: chino, ingles, japones, aleman, espanol. "
                "Cambio en la app y CLI via --locale."
            ),
        },
    }

    for row_idx, texts in features.items():
        for col, text in texts.items():
            rows[row_idx][col] = text

    # Verify all under 200 chars
    for row_idx in range(305, 312):
        for col in [4, 5, 6, 7, 8]:
            text = rows[row_idx][col]
            lang = ["", "", "", "", "en", "zh", "de", "ja", "es"][col]
            if len(text) > 200:
                print(f"  OVER LIMIT: {rows[row_idx][0]} {lang}: {len(text)} chars")
                print(f"    -> {text[:80]}...")
            elif len(text) > 195:
                print(f"  CLOSE: {rows[row_idx][0]} {lang}: {len(text)} chars")

    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerows(rows)

    print("Done. Verify no OVER LIMIT lines above.")


if __name__ == "__main__":
    main()
