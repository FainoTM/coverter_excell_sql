import os
import re
import csv
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd


@dataclass
class ConverterConfig:
    encoding_sample: str = "latin-1"
    encoding_output_schema: str = "latin-1"
    encoding_output_data: str = "ISO-8859-1"
    n_sample: int = 1000
    max_varchar: int = 1024
    table_prefix: str = ""


class SqlValueFormatter:
    _virg_dec_re = re.compile(
        r"""
        ^[+-]?
        \d{1,3}
        (?:\.\d{3})*
        ,\d+
        $
        """,
        re.VERBOSE,
    )

    @staticmethod
    def sql_literal(val) -> str:
        if pd.isna(val) or (isinstance(val, str) and val.strip() == ""):
            return "NULL"

        if isinstance(val, (int, np.integer)):
            return str(int(val))

        if isinstance(val, (float, np.floating)):
            return str(val)

        s = str(val).strip()

        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", s):
            return f"'{datetime.strptime(s, '%d/%m/%Y'):%Y-%m-%d}'"

        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return f"'{s}'"

        if SqlValueFormatter._virg_dec_re.fullmatch(s):
            return s.replace(".", "").replace(",", ".")

        if re.fullmatch(r"[+-]?\d+", s):
            return s

        return "'" + s.replace("'", "''") + "'"


class CsvSchemaInferer:
    def __init__(self, config: ConverterConfig):
        self.config = config

    def infer_type(self, series: pd.Series) -> str:
        s = series.dropna().astype(str).str.strip()

        if s.empty or (s == "").all():
            return "VARCHAR(50)"

        if s.str.fullmatch(r"[+-]?\d+").all():
            try:
                nums = pd.to_numeric(s, errors="raise")
                return "BIGINT" if nums.max() > 2_147_483_647 else "INTEGER"
            except ValueError:
                pass

        if s.str.fullmatch(r"[+-]?\d+([.,]\d+)?").all():
            return "DECIMAL(18,6)"

        if (
            s.str.fullmatch(r"\d{2}/\d{2}/\d{4}").all()
            or s.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
        ):
            return "DATE"

        length = min(((int(s.str.len().max()) // 10 + 1) * 10), self.config.max_varchar)
        return f"VARCHAR({length})"


class FileReader:
    def __init__(self, config: ConverterConfig):
        self.config = config

    @staticmethod
    def detect_delimiter(sample: bytes) -> str:
        line = sample.decode("latin-1", errors="ignore")
        return "|" if line.count("|") > line.count(";") else ";"

    def read_csv_file(self, file_path: str, nrows=None) -> pd.DataFrame:
        with open(file_path, "rb") as f:
            first_bytes = f.read(2048)

        delim = self.detect_delimiter(first_bytes)

        return pd.read_csv(
            file_path,
            sep=delim,
            encoding=self.config.encoding_sample,
            nrows=nrows,
            engine="python",
            quoting=csv.QUOTE_NONE if nrows else csv.QUOTE_MINIMAL,
            on_bad_lines="skip",
        )

    def read_excel_file(self, file_path: str, nrows=None) -> pd.DataFrame:
        return pd.read_excel(file_path, nrows=nrows)

    def read_csv_from_zip(self, zip_file: zipfile.ZipFile, file_name: str, nrows=None) -> pd.DataFrame:
        with zip_file.open(file_name) as f:
            first_bytes = f.read(2048)
            delim = self.detect_delimiter(first_bytes)
            f.seek(0)

            return pd.read_csv(
                f,
                sep=delim,
                encoding=self.config.encoding_sample,
                nrows=nrows,
                engine="python",
                quoting=csv.QUOTE_NONE if nrows else csv.QUOTE_MINIMAL,
                on_bad_lines="skip",
            )


class FirebirdMigrationGenerator:
    def __init__(self, config: ConverterConfig | None = None):
        self.config = config or ConverterConfig()
        self.reader = FileReader(self.config)
        self.inferer = CsvSchemaInferer(self.config)
        self.formatter = SqlValueFormatter()

    def generate(self, input_path: str) -> tuple[str, str]:
        base = os.path.splitext(os.path.basename(input_path))[0]
        schema_file = f"schema_{base}.sql"
        data_file = f"data_{base}.sql"

        schema_lines = self._build_schema_header(base)
        data_lines = self._build_data_header(base)

        tables = self._load_input_tables(input_path)

        for table_name, df_sample, df_full in tables:
            schema_lines.extend(self._generate_create_table(table_name, df_sample))
            data_lines.extend(self._generate_inserts(table_name, df_full))

        data_lines.append("SET TERM ; ^")

        self._write_file(schema_file, schema_lines, self.config.encoding_output_schema)
        self._write_file(data_file, data_lines, self.config.encoding_output_data)

        return schema_file, data_file

    def _load_input_tables(self, input_path: str):
        ext = os.path.splitext(input_path)[1].lower()
        base_name = self.config.table_prefix + os.path.splitext(os.path.basename(input_path))[0]

        if ext == ".zip":
            return self._load_from_zip(input_path)

        if ext == ".csv":
            df_sample = self.reader.read_csv_file(input_path, nrows=self.config.n_sample)
            df_full = self.reader.read_csv_file(input_path)
            return [(base_name, df_sample, df_full)]

        if ext in (".xlsx", ".xls"):
            df_sample = self.reader.read_excel_file(input_path, nrows=self.config.n_sample)
            df_full = self.reader.read_excel_file(input_path)
            return [(base_name, df_sample, df_full)]

        raise ValueError("Formato não suportado. Use .zip, .csv, .xlsx ou .xls")

    def _load_from_zip(self, zip_path: str):
        tables = []

        with zipfile.ZipFile(zip_path) as z:
            for info in z.infolist():
                if not info.filename.lower().endswith(".csv"):
                    continue

                table_name = self.config.table_prefix + os.path.splitext(
                    os.path.basename(info.filename)
                )[0]

                df_sample = self.reader.read_csv_from_zip(
                    z, info.filename, nrows=self.config.n_sample
                )
                df_full = self.reader.read_csv_from_zip(z, info.filename)

                tables.append((table_name, df_sample, df_full))

        return tables

    def _build_schema_header(self, base: str) -> list[str]:
        return [
            f"-- Schema gerado de {base}",
            f"-- {datetime.now():%Y-%m-%d %H:%M:%S}",
            ""
        ]

    def _build_data_header(self, base: str) -> list[str]:
        return [
            f"-- Inserts gerados de {base}",
            f"-- {datetime.now():%Y-%m-%d %H:%M:%S}",
            "",
            "SET AUTODDL OFF;",
            "",
            "SET TERM ^ ;",
            ""
        ]

    def _generate_create_table(self, table_name: str, df_sample: pd.DataFrame) -> list[str]:
        col_defs = [
            f'    "{col}" {self.inferer.infer_type(df_sample[col])}'
            for col in df_sample.columns
        ]

        create_stmt = f'CREATE TABLE "{table_name}" (\n' + ",\n".join(col_defs) + "\n);\n"
        return [create_stmt]

    def _generate_inserts(self, table_name: str, df: pd.DataFrame) -> list[str]:
        lines = []
        cols_sql = ", ".join(f'"{col}"' for col in df.columns)

        for _, row in df.iterrows():
            values = ", ".join(self.formatter.sql_literal(row[col]) for col in df.columns)
            lines.append(f'INSERT INTO "{table_name}" ({cols_sql}) VALUES ({values});')

        lines.append("COMMIT;")
        return lines

    def generate_strings(self, input_path: str) -> tuple[str, str]:
        base = os.path.splitext(os.path.basename(input_path))[0]

        schema_lines = self._build_schema_header(base)
        data_lines = self._build_data_header(base)

        tables = self._load_input_tables(input_path)

        for table_name, df_sample, df_full in tables:
            schema_lines.extend(self._generate_create_table(table_name, df_sample))
            data_lines.extend(self._generate_inserts(table_name, df_full))

        data_lines.append("SET TERM ; ^")

        schema_text = "\n".join(schema_lines)
        data_text = "\n".join(data_lines)

        return schema_text, data_text

    def generate_preview(self, input_path: str, max_chars: int = 4000) -> dict:
        schema_text, data_text = self.generate_strings(input_path)

        full_text = schema_text + "\n\n" + data_text

        return {
            "schema_preview": schema_text[:max_chars],
            "data_preview": data_text[:max_chars],
            "combined_preview": full_text[:max_chars],
            "truncated": len(full_text) > max_chars,
        }

    @staticmethod
    def _write_file(file_path: str, lines: list[str], encoding: str) -> None:
        with open(file_path, "w", encoding=encoding) as f:
            f.write("\n".join(lines))


class Application:
    def __init__(self):
        self.generator = FirebirdMigrationGenerator()

    def run(self, input_path: str) -> None:
        schema_file, data_file = self.generator.generate(input_path)
        print("Arquivos gerados:")
        print("  •", schema_file)
        print("  •", data_file)


def main():
    if len(sys.argv) != 2:
        print("Uso: python gera_firebird_migracao.py arquivo.zip|arquivo.csv|arquivo.xlsx")
        sys.exit(1)

    app = Application()
    app.run(sys.argv[1])


if __name__ == "__main__":
    main()