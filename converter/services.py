#!/usr/bin/env python3

"""
"""
import pandas as pd, numpy as np, zipfile, sys, os, re, csv
from datetime import datetime

# ---------- Configurações ----------
DELIM        = ";"
ENCODING     = "UTF-8"
N_SAMPLE     = 1_000          # linhas-amostra para inferir tipos
MAX_VARCHAR  = 1024
TABLE_PREFIX = ""
# -----------------------------------


_virg_dec_re = re.compile(r"""
    ^[+-]?               # sinal opcional
    \d{1,3}              # um a três dígitos
    (?:\.\d{3})*         # grupos de milhar com ponto (opcional)
    ,\d+                 # vírgula + casas decimais
    $""", re.VERBOSE)


def infer_type(series: pd.Series) -> str:
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
    if s.str.fullmatch(r"\d{2}/\d{2}/\d{4}").all() or s.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        return "DATE"
    length = min(((int(s.str.len().max()) // 10 + 1) * 10), MAX_VARCHAR)
    return f"VARCHAR({length})"


def sql_literal(val):
    """Devolve string pronta para ser usada no VALUES (Firebird)."""
    # NULLs
    if pd.isna(val) or (isinstance(val, str) and val.strip() == ""):
        return "NULL"

    # Numéricos nativos
    if isinstance(val, (int, np.integer)):
        return str(int(val))
    if isinstance(val, (float, np.floating)):
        return str(val)          # já vem com ponto

    # Strings
    s = str(val).strip()

    # data dd/mm/yyyy  →  'YYYY-MM-DD'
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", s):
        return f"'{datetime.strptime(s, '%d/%m/%Y'):%Y-%m-%d}'"

    # data ISO yyyy-mm-dd – mantém
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return f"'{s}'"

    # decimal com vírgula (com ou sem milhares)
    if _virg_dec_re.fullmatch(s):
        num = s.replace(".", "").replace(",", ".")   # 1.234,56 → 1234.56
        return num                                   # sem aspas

    # inteiro em string
    if re.fullmatch(r"[+-]?\d+", s):
        return s

    # fallback: texto – escapa apóstrofos
    return "'" + s.replace("'", "''") + "'"


def detect_delimiter(sample: bytes) -> str:
    line = sample.decode('latin-1', errors="ignore")
    return '|' if line.count('|') > line.count(';') else ';'


# ---------- Main ----------
def main(zip_path: str):
    base = os.path.splitext(os.path.basename(zip_path))[0]
    schema_file = f"schema_{base}.sql"
    data_file   = f"data_{base}.sql"

    # Cabeçalhos
    schema_lines = [
        f"-- Schema gerado de {base}",
        f"-- {datetime.now():%Y-%m-%d %H:%M:%S}",
        ""
    ]
    data_lines = [
        f"-- Inserts gerados de {base}",
        f"-- {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "SET AUTODDL OFF;",
        "",
        "SET TERM ^ ;",
        ""
    ]

    # Percorre cada CSV dentro do .zip
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if not info.filename.lower().endswith(".csv"):
                continue

            table = TABLE_PREFIX + os.path.splitext(os.path.basename(info.filename))[0]

            # --- 1) SCHEMA -------------------------------------------------
            with z.open(info.filename) as f_sample:
                first_bytes = f_sample.read(2048)  # 1. buffer
                DELIM = detect_delimiter(first_bytes)
                f_sample.seek(0)

                df_sample = pd.read_csv(
                    f_sample, sep=DELIM, encoding="LATIN-1",
                    nrows=N_SAMPLE, engine="python",
                    quoting=csv.QUOTE_NONE, on_bad_lines="skip"
                )

            col_defs = [f'    "{c}" {infer_type(df_sample[c])}' for c in df_sample.columns]
            schema_lines.append(f'CREATE TABLE "{table}" (\n' + ",\n".join(col_defs) + "\n);\n")

            # --- 2) INSERTs ------------------------------------------------
            with z.open(info.filename) as f_full:
                first_bytes = f_full.read(2048)  # 1. buffer
                DELIM = detect_delimiter(first_bytes)
                f_full.seek(0)
                df = pd.read_csv(
                    f_full, sep=DELIM, encoding='latin-1',
                    engine="python", on_bad_lines="skip"
                )

            cols_sql = ", ".join(f'"{c}"' for c in df.columns)

            for _, row in df.iterrows():
                values = ", ".join(sql_literal(row[c]) for c in df.columns)
                data_lines.append(f'INSERT INTO "{table}" ({cols_sql}) VALUES ({values});')

            data_lines.append("COMMIT;")   # após cada tabela

    data_lines.append("SET TERM ; ^")

    # --- grava ---
    with open(schema_file, "w", encoding="latin-1") as f:
        f.write("\n".join(schema_lines))

    with open(data_file, "w", encoding="ISO-8859-1") as f:
        f.write("\n".join(data_lines))

    # resumo
    print("Arquivos gerados:")
    print("  •", schema_file)
    print("  •", data_file)

# ---------- Execução ----------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python gera_firebird_migracao.py URUPA.zip")
        sys.exit(1)
    main(sys.argv[1])
