from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
SPREADSHEET_TEXT_NODE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"

COMPETENCY_CODES = [
    "U1",
    "U2",
    "U3",
    "U4",
    "LIC1",
    "LIC2",
    "LIC3",
    "LIC4",
    "LIC5",
    "LCC1",
    "LCC2",
    "TIC1",
    "TIC2",
    "TIC3",
    "TIC4",
    "TIC5",
    "TCC1",
    "TCC2",
    "TCC3",
]
MAX_MATRIX_ROWS = 300


@dataclass(frozen=True)
class MatrixCompetency:
    code: str
    group: str
    description: str
    sort_order: int


@dataclass(frozen=True)
class MatrixCourse:
    code: str
    title: str
    semester: str
    sort_order: int
    competency_indexes: list[int]


@dataclass(frozen=True)
class CurriculumMatrix:
    competencies: list[MatrixCompetency]
    courses: list[MatrixCourse]


def _cell_ref_to_position(ref: str) -> tuple[int, int]:
    match = re.match(r"([A-Z]+)(\d+)", ref)
    if not match:
        return 1, 1
    col = 0
    for char in match.group(1):
        col = col * 26 + ord(char) - 64
    return int(match.group(2)), col


def _sheet_cells(zipped: zipfile.ZipFile, sheet_path: str) -> dict[tuple[int, int], str]:
    shared_strings: list[str] = []
    if "xl/sharedStrings.xml" in zipped.namelist():
        root = ET.fromstring(zipped.read("xl/sharedStrings.xml"))
        for item in root.findall("a:si", NS):
            text = "".join(
                node.text or ""
                for node in item.iter(SPREADSHEET_TEXT_NODE)
            )
            shared_strings.append(text)

    root = ET.fromstring(zipped.read(sheet_path))
    cells: dict[tuple[int, int], str] = {}
    for cell in root.findall(".//a:sheetData/a:row/a:c", NS):
        row, col = _cell_ref_to_position(cell.attrib.get("r", "A1"))
        kind = cell.attrib.get("t")
        value_node = cell.find("a:v", NS)
        inline_node = cell.find("a:is", NS)
        value = ""

        if kind == "s" and value_node is not None:
            index = int(value_node.text or "0")
            value = shared_strings[index] if index < len(shared_strings) else ""
        elif kind == "inlineStr" and inline_node is not None:
            value = "".join(
                node.text or ""
                for node in inline_node.iter(SPREADSHEET_TEXT_NODE)
            )
        elif value_node is not None:
            value = value_node.text or ""

        if value:
            cells[(row, col)] = value.strip()
    return cells


def load_matrix_from_xlsx(path: Path) -> CurriculumMatrix:
    """Carga y parsea una matriz curricular desde un archivo XLSX.

    Extrae las competencias (hoja columnas), cursos (filas) y la tributación
    (celdas con X) para construir una representación en modelo de dominio.

    Args:
        path: Ruta al archivo .xlsx.

    Returns:
        Objeto CurriculumMatrix con competencias y cursos.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ValueError: Si el XLSX no contiene hojas.
    """
    if not path.exists():
        raise FileNotFoundError(f"No existe la matriz curricular: {path}")

    with zipfile.ZipFile(path) as zipped:
        workbook = ET.fromstring(zipped.read("xl/workbook.xml"))
        rels = ET.fromstring(zipped.read("xl/_rels/workbook.xml.rels"))
        relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        first_sheet = workbook.find("a:sheets/a:sheet", NS)
        if first_sheet is None:
            raise ValueError("El archivo XLSX no contiene hojas.")
        rel_id = first_sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        target = relmap[rel_id]
        sheet_path = target if target.startswith("xl/") else f"xl/{target}"
        cells = _sheet_cells(zipped, sheet_path)

    competencies: list[MatrixCompetency] = []
    active_group = ""
    for col in range(4, 23):
        group = cells.get((1, col))
        if group:
            active_group = group.title()
        description = cells.get((2, col), "")
        if description:
            index = len(competencies)
            code = COMPETENCY_CODES[index] if index < len(COMPETENCY_CODES) else f"C{index + 1}"
            competencies.append(
                MatrixCompetency(
                    code=code,
                    group=active_group,
                    description=description,
                    sort_order=index,
                )
            )

    courses: list[MatrixCourse] = []
    row = 3
    while row < MAX_MATRIX_ROWS:
        code = cells.get((row, 1), "")
        title = cells.get((row, 2), "")
        semester = cells.get((row, 3), "")
        if not any(cells.get((row, col), "") for col in range(1, 23)):
            break
        if title:
            indexes = []
            for index, col in enumerate(range(4, 4 + len(competencies))):
                if cells.get((row, col), "").upper() == "X":
                    indexes.append(index)
            courses.append(
                MatrixCourse(
                    code=code,
                    title=title,
                    semester=semester,
                    sort_order=len(courses),
                    competency_indexes=indexes,
                )
            )
        row += 1

    return CurriculumMatrix(competencies=competencies, courses=courses)
