"""
╔══════════════════════════════════════════════════════╗
║   BioTrack — Processador de Dados v2.0               ║
║   Autor: BioTrack System                             ║
║   Uso:   python processar.py  OU  duplo clique       ║
╚══════════════════════════════════════════════════════╝
"""

import csv
import hashlib
import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path


# ══════════════════════════════════════════════════════
#   HASH DE SENHA
# ══════════════════════════════════════════════════════

def _hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()


# ══════════════════════════════════════════════════════
#   CONFIGURAÇÕES GLOBAIS
# ══════════════════════════════════════════════════════

PASTA_BASE = Path(__file__).parent.resolve()

CSV_FILE      = PASTA_BASE / "notas_dashboard.csv"
PROF_FILE     = PASTA_BASE / "professores.csv"
TEMPLATE_FILE = PASTA_BASE / "dashboard_template.html"
OUTPUT_FILE   = PASTA_BASE / "index.html"
LOG_FILE      = PASTA_BASE / "erros_processamento.log"

TAGS = [
    "BIO_ECO", "BIO_SATC", "BIO_CEL", "BIO_MQ",
    "BIO_EVO", "BIO_EMH", "BIO_ZOO", "BIO_BOT", "BIO_ANAFIS",
]

TIPOS_VALIDOS = {"avaliacao", "reforco"}

COLUNAS_BASE = [
    "ID_Aluno", "Nome_Completo", "Senha",
    "Turma", "Data_Avaliacao", "Tipo_Registro",
]

COLUNAS_NOTAS = [f"{tag}_{suf}" for tag in TAGS for suf in ("C", "E")]
COLUNAS_OBRIGATORIAS = COLUNAS_BASE + COLUNAS_NOTAS

MARCADOR_USERS = "/* ##BIOTRACK_USERS_DATA## */"
MARCADOR_PROFS = "/* ##BIOTRACK_PROFS_DATA## */"


# ══════════════════════════════════════════════════════
#   GERENCIAMENTO DE LOG
# ══════════════════════════════════════════════════════

_erros: list[str] = []


def registrar_erro(num_linha: int, mensagem: str) -> None:
    texto = f"[Linha {num_linha:>4}]  {mensagem}"
    _erros.append(texto)
    print(f"         ⚠️  {texto}")


def salvar_log() -> None:
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("╔══════════════════════════════════════════════╗\n")
        f.write("║  BioTrack — Relatório de Erros               ║\n")
        f.write("╚══════════════════════════════════════════════╝\n\n")
        f.write(f"Data/Hora     : {agora}\n")
        f.write(f"Arquivo       : {CSV_FILE}\n")
        f.write(f"Total de erros: {len(_erros)}\n")
        f.write("─" * 50 + "\n\n")
        if _erros:
            for erro in _erros:
                f.write(f"  {erro}\n")
        else:
            f.write("  ✅ Nenhum erro encontrado.\n")


# ══════════════════════════════════════════════════════
#   VALIDAÇÃO
# ══════════════════════════════════════════════════════

def validar_cabecalho(fieldnames: list[str]) -> tuple[bool, list[str]]:
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in fieldnames]
    return (len(faltando) == 0), faltando


def _parsear_data(data_str: str) -> datetime | None:
    """
    Tenta parsear uma string de data nos formatos suportados.
    Aceita YYYY-MM-DD e DD/MM/YYYY (Excel BR) entre outros.
    """
    FORMATOS = [
        "%Y-%m-%d",  # 2026-02-10  ← padrão original
        "%d/%m/%Y",  # 10/02/2026  ← Excel Brasil
        "%d-%m-%Y",  # 10-02-2026  ← variação com hífen
        "%Y/%m/%d",  # 2026/02/10  ← variação com barra
        "%d/%m/%y",  # 10/02/26    ← Excel com ano curto
    ]
    for fmt in FORMATOS:
        try:
            return datetime.strptime(data_str.strip(), fmt)
        except ValueError:
            continue
    return None


def validar_linha(row: dict, num_linha: int) -> bool:
    """
    Valida todos os campos de uma linha do CSV.
    """
    linha_ok = True

    # Regra 1: campos obrigatórios não podem estar vazios
    for col in COLUNAS_BASE:
        valor = row.get(col, "").strip()
        if not valor:
            registrar_erro(num_linha, f"Campo obrigatório vazio → '{col}'")
            linha_ok = False

    if not linha_ok:
        return False

    # Regra 2: ID_Aluno sem espaços
    if " " in row["ID_Aluno"].strip():
        registrar_erro(
            num_linha,
            f"ID_Aluno '{row['ID_Aluno']}' não pode conter espaços.",
        )
        linha_ok = False

    # Regra 3: formato da data (aceita DD/MM/YYYY e YYYY-MM-DD)
    data_str = row["Data_Avaliacao"].strip()
    if _parsear_data(data_str) is None:
        registrar_erro(
            num_linha,
            f"Data inválida → '{data_str}'. "
            "Formatos aceitos: AAAA-MM-DD ou DD/MM/AAAA",
        )
        linha_ok = False

    # Regra 4: tipo de registro
    tipo = row["Tipo_Registro"].strip().lower()
    if tipo not in TIPOS_VALIDOS:
        registrar_erro(
            num_linha,
            f"Tipo_Registro inválido → '{row['Tipo_Registro']}'. "
            "Use: 'avaliacao' ou 'reforco'",
        )
        linha_ok = False

    # Regra 5: valores numéricos das notas
    for tag in TAGS:
        for sufixo in ("_C", "_E"):
            col = tag + sufixo
            raw = row.get(col, "").strip()
            if not raw:
                registrar_erro(num_linha, f"Campo de nota vazio → '{col}'")
                linha_ok = False
                continue
            try:
                valor = int(raw)
            except ValueError:
                registrar_erro(
                    num_linha,
                    f"'{col}' deve ser número inteiro → encontrado: '{raw}'",
                )
                linha_ok = False
                continue
            if valor < 0:
                registrar_erro(
                    num_linha,
                    f"'{col}' não pode ser negativo → encontrado: {valor}",
                )
                linha_ok = False

    return linha_ok


# ══════════════════════════════════════════════════════
#   DETECÇÃO DE ENCODING E SEPARADOR
# ══════════════════════════════════════════════════════

def detectar_encoding(caminho: Path) -> str:
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            with open(caminho, encoding=enc) as t:
                t.read()
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8-sig"


def detectar_separador(caminho: Path, encoding: str) -> str:
    with open(caminho, encoding=encoding) as f:
        primeira = f.readline()
    return ";" if primeira.count(";") > primeira.count(",") else ","


# ══════════════════════════════════════════════════════
#   LEITURA DO CSV DE ALUNOS
# ══════════════════════════════════════════════════════

def ler_csv() -> tuple[dict, int, int]:
    if not CSV_FILE.exists():
        print(f"\n   ❌  Arquivo '{CSV_FILE.name}' não encontrado!")
        print(f"       Esperado em: {CSV_FILE}")
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    alunos_raw: dict[str, list[dict]] = {}
    total_linhas = 0
    linhas_validas = 0

    arquivo_enc = detectar_encoding(CSV_FILE)
    separador   = detectar_separador(CSV_FILE, arquivo_enc)

    print(f"         ℹ️   Encoding detectado : {arquivo_enc}")
    print(f"         ℹ️   Separador detectado: "
          f"{'ponto e vírgula (;)' if separador == ';' else 'vírgula (,)'}")

    with open(CSV_FILE, newline="", encoding=arquivo_enc) as f:
        reader = csv.DictReader(f, delimiter=separador)

        if not reader.fieldnames:
            print("\n   ❌  Arquivo CSV vazio ou sem cabeçalho!")
            input("\nPressione Enter para fechar...")
            sys.exit(1)

        cabecalho_ok, faltando = validar_cabecalho(list(reader.fieldnames))
        if not cabecalho_ok:
            print("\n   ❌  Colunas faltando no cabeçalho do CSV:")
            for col in faltando:
                print(f"       • {col}")
            input("\nPressione Enter para fechar...")
            sys.exit(1)

        for num_linha, row in enumerate(reader, start=2):
            total_linhas += 1
            if validar_linha(row, num_linha):
                linhas_validas += 1
                aluno_id = row["ID_Aluno"].strip()
                if aluno_id not in alunos_raw:
                    alunos_raw[aluno_id] = []
                alunos_raw[aluno_id].append(row)

    return alunos_raw, linhas_validas, total_linhas


# ══════════════════════════════════════════════════════
#   LEITURA DO CSV DE PROFESSORES
# ══════════════════════════════════════════════════════

def ler_professores() -> dict:
    professores = {}

    if not PROF_FILE.exists():
        print(f"         ℹ️   '{PROF_FILE.name}' não encontrado "
              "— painel do professor desativado.")
        return professores

    enc_prof = detectar_encoding(PROF_FILE)
    sep_prof = detectar_separador(PROF_FILE, enc_prof)

    print(f"         ℹ️   Encoding professores : {enc_prof}")
    print(f"         ℹ️   Separador professores: "
          f"{'ponto e vírgula (;)' if sep_prof == ';' else 'vírgula (,)'}")

    colunas_prof = ["ID_Prof", "Nome_Completo", "Senha", "Disciplina"]

    with open(PROF_FILE, newline="", encoding=enc_prof) as f:
        reader = csv.DictReader(f, delimiter=sep_prof)

        if not reader.fieldnames:
            print("         ⚠️   professores.csv está vazio ou sem cabeçalho.")
            return professores

        faltando_prof = [c for c in colunas_prof if c not in reader.fieldnames]
        if faltando_prof:
            print("         ⚠️   Colunas faltando em professores.csv:")
            for col in faltando_prof:
                print(f"              • {col}")
            print("         ⚠️   Painel do professor desativado.")
            return professores

        for num, row in enumerate(reader, start=2):
            pid  = row.get("ID_Prof", "").strip()
            nome = row.get("Nome_Completo", "").strip()
            pwd  = row.get("Senha", "").strip()
            disc = row.get("Disciplina", "Biologia").strip()

            if not pid or not nome or not pwd:
                print(f"         ⚠️   [Linha {num}] Professor ignorado "
                      "— ID, Nome ou Senha vazio.")
                continue

            if pid in professores:
                print(f"         ⚠️   [Linha {num}] ID '{pid}' duplicado — ignorado.")
                continue

            professores[pid] = {
                "password":   _hash_senha(pwd),
                "name":       nome,
                "disciplina": disc,
            }

    return professores


# ══════════════════════════════════════════════════════
#   CONVERSÃO PARA O FORMATO DO DASHBOARD
# ══════════════════════════════════════════════════════

def _calcular_pct(correct: int, wrong: int) -> int:
    total = correct + wrong
    if total == 0:
        return 0
    return round((correct / total) * 100)


def _formatar_label(data_str: str, tipo: str) -> str:
    meses_pt = {
        1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr",
        5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago",
        9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
    }

    data_obj = _parsear_data(data_str)

    if data_obj is None:
        return f"{'Reforço' if tipo == 'reforco' else 'Aval.'}\n??/???"

    mes_abrev = meses_pt[data_obj.month]
    ano_curto = data_obj.strftime("%y")
    prefixo   = "Reforço" if tipo == "reforco" else "Aval."
    return f"{prefixo}\n{mes_abrev}/{ano_curto}"


def construir_users(alunos_raw: dict) -> dict:
    users = {}

    for aluno_id, registros in alunos_raw.items():

        # Ordena cronologicamente pelo objeto datetime (não pela string)
        registros_ord = sorted(
            registros,
            key=lambda r: _parsear_data(r["Data_Avaliacao"].strip()) or datetime.min,
        )

        # Dados cadastrais do registro mais recente
        ultimo = registros_ord[-1]
        nome   = ultimo["Nome_Completo"].strip()
        senha  = ultimo["Senha"].strip()

        # Performance: snapshot do registro mais recente
        performance = {}
        for tag in TAGS:
            performance[tag] = {
                "correct": int(ultimo[f"{tag}_C"].strip()),
                "wrong":   int(ultimo[f"{tag}_E"].strip()),
            }

        # Evolution: histórico completo ordenado
        evolution = []
        for reg in registros_ord:
            data_str = reg["Data_Avaliacao"].strip()
            tipo     = reg["Tipo_Registro"].strip().lower()
            label    = _formatar_label(data_str, tipo)

            scores = {}
            for tag in TAGS:
                c = int(reg[f"{tag}_C"].strip())
                e = int(reg[f"{tag}_E"].strip())
                scores[tag] = _calcular_pct(c, e)

            evolution.append({"label": label, "scores": scores})

        users[aluno_id] = {
            "password":    _hash_senha(senha),
            "name":        nome,
            "turma":       ultimo["Turma"].strip(),
            "performance": performance,
            "evolution":   evolution,
        }

    return users


# ══════════════════════════════════════════════════════
#   GERAÇÃO DO HTML FINAL
# ══════════════════════════════════════════════════════

def gerar_html(users: dict, professores: dict) -> None:
    if not TEMPLATE_FILE.exists():
        print(f"\n   ❌  Template '{TEMPLATE_FILE.name}' não encontrado!")
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    if MARCADOR_USERS not in html:
        print(f"\n   ❌  Marcador '{MARCADOR_USERS}' não encontrado no template!")
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    if MARCADOR_PROFS not in html:
        print(f"\n   ❌  Marcador '{MARCADOR_PROFS}' não encontrado no template!")
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    users_json = json.dumps(users,       ensure_ascii=False, indent=2)
    profs_json = json.dumps(professores, ensure_ascii=False, indent=2)

    html = html.replace(MARCADOR_USERS, f"const USERS = {users_json};")
    html = html.replace(MARCADOR_PROFS, f"const PROFESSORS = {profs_json};")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)


# ══════════════════════════════════════════════════════
#   INTERFACE DO TERMINAL
# ══════════════════════════════════════════════════════

def banner() -> None:
    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║   🧬  BioTrack — Processador de Dados v2.0  ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()


def separador() -> None:
    print("  " + "─" * 46)


def passo(num: int, total: int, descricao: str) -> None:
    print(f"\n  [{num}/{total}]  {descricao}")


# ══════════════════════════════════════════════════════
#   FUNÇÃO PRINCIPAL
# ══════════════════════════════════════════════════════

def main() -> None:
    banner()
    TOTAL_PASSOS = 6

    # Passo 1 — Leitura e validação do CSV
    passo(1, TOTAL_PASSOS, f"Lendo e validando  →  {CSV_FILE.name}")
    alunos_raw, linhas_validas, total_linhas = ler_csv()
    linhas_com_erro = total_linhas - linhas_validas
    print(
        f"         ✅  {linhas_validas} linha(s) válida(s) de {total_linhas} total"
        + (f"  |  ⚠️  {linhas_com_erro} com erro" if linhas_com_erro else "")
    )

    if not alunos_raw:
        print("\n   ❌  Nenhum aluno válido encontrado no CSV!")
        salvar_log()
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    # Passo 2 — Conversão dos alunos
    passo(2, TOTAL_PASSOS, "Convertendo dados dos alunos...")
    users = construir_users(alunos_raw)
    print(f"         ✅  {len(users)} aluno(s) processado(s):")
    for aluno_id, dados in users.items():
        print(f"              •  {aluno_id:<10}  →  {dados['name']}"
              f"  ({len(dados['evolution'])} avaliação/ões)")

    # Passo 3 — Leitura dos professores
    passo(3, TOTAL_PASSOS, f"Lendo professores  →  {PROF_FILE.name}")
    professores = ler_professores()
    if professores:
        print(f"         ✅  {len(professores)} professor(es) carregado(s):")
        for pid, dados in professores.items():
            print(f"              •  {pid:<10}  →  {dados['name']}"
                  f"  ({dados['disciplina']})")
    else:
        print("         ℹ️   Nenhum professor — painel do professor estará vazio.")

    # Passo 4 — Geração do HTML
    passo(4, TOTAL_PASSOS, f"Gerando  →  {OUTPUT_FILE.name}")
    gerar_html(users, professores)
    print(f"         ✅  {OUTPUT_FILE.name}  gerado com sucesso!")

    # Passo 5 — Salvar log
    passo(5, TOTAL_PASSOS, f"Salvando relatório  →  {LOG_FILE.name}")
    salvar_log()
    if _erros:
        print(f"         ⚠️   {len(_erros)} erro(s) → veja {LOG_FILE.name}")
    else:
        print("         ✅  Sem erros!")

    # Passo 6 — Abrir no navegador
    passo(6, TOTAL_PASSOS, "Abrindo dashboard no navegador...")
    caminho_abs = OUTPUT_FILE.resolve()
    webbrowser.open(caminho_abs.as_uri())
    print(f"         ✅  {caminho_abs.as_uri()}")

    print()
    separador()
    print()
    print("  🎉  Processamento concluído com sucesso!")
    print()
    print(f"       👥  Alunos      : {len(users)}")
    print(f"       👨‍🏫  Professores : {len(professores)}")
    if linhas_com_erro:
        print(f"       ⚠️   Ignoradas   : {linhas_com_erro}  →  veja {LOG_FILE.name}")
    print()
    separador()
    print()
    input("  Pressione Enter para fechar...")


# ══════════════════════════════════════════════════════
#   ENTRY POINT
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    main()