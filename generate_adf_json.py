
import json
import re
import csv
from collections import Counter

def infer_type(values):
    is_int = all(re.match(r"^\\s*-?\\d+\\s*$", v) for v in values if v)
    is_float = all(re.match(r"^\\s*-?\\d+(\\.\\d+)?\\s*$", v) for v in values if v)
    if is_int:
        return "Int32"
    elif is_float:
        return "Double"
    return "String"

def detect_fixed_width_columns(file_path, sample_lines=20):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for _, line in zip(range(sample_lines), f)]

    positions = []
    for line in lines:
        pos = [0]
        for i in range(1, len(line)):
            if (line[i] != ' ' and line[i-1] == ' ') or (line[i] == ' ' and line[i-1] != ' '):
                pos.append(i)
        pos.append(len(line))
        positions.append(sorted(set(pos)))

    tupled_positions = [tuple(p) for p in positions]
    most_common = Counter(tupled_positions).most_common(1)[0][0]
    column_slices = [(most_common[i], most_common[i+1]) for i in range(len(most_common) - 1)]
    return column_slices

def apply_field_mapping(original_columns, mapping_csv_path):
    mapping = {}
    with open(mapping_csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            mapping[row['column_name']] = row['column_name_new']

    renamed_columns = []
    for i, col in enumerate(original_columns):
        default_name = f"col_{i+1}" if i < len(original_columns) - 1 else "description"
        new_name = mapping.get(default_name, default_name)
        renamed_columns.append((new_name, col['start'], col['width'], col['type']))
    return renamed_columns

def generate_adf_json(input_file_path, mapping_csv_path, output_json_path):
    column_slices = detect_fixed_width_columns(input_file_path)

    # Sample data lines for type inference
    with open(input_file_path, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for _, line in zip(range(20), f)]

    column_data = [[] for _ in column_slices]
    for line in lines:
        for i, (start, end) in enumerate(column_slices):
            column_data[i].append(line[start:end].strip())

    # Build column metadata with default names
    raw_columns = []
    for i, (start, end) in enumerate(column_slices):
        raw_columns.append({
            "start": start + 1,
            "width": 0 if i == len(column_slices) - 1 else end - start,
            "type": infer_type(column_data[i])
        })

    # Apply field name mapping
    renamed_columns = apply_field_mapping(raw_columns, mapping_csv_path)

    columns = [{
        "name": name,
        "start": start,
        "width": width,
        "type": col_type
    } for name, start, width, col_type in renamed_columns]

    adf_schema = {
        "typeProperties": {
            "columnDelimiter": "",
            "rowDelimiter": "\n",
            "fixedWidthSettings": {
                "columns": columns
            }
        }
    }

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(adf_schema, f, indent=2)

    return output_json_path
