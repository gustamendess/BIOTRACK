
"""
╔══════════════════════════════════════════════════════╗
║   BioTrack — Processador de Dados v1.0               ║
║   Autor: BioTrack System                             ║
║   Uso:   python processar.py  OU  duplo clique       ║
╚══════════════════════════════════════════════════════╝

FLUXO:
  1. Lê notas_dashboard.csv
  2. Valida cada linha
  3. Converte para JSON
  4. Injeta no dashboard_template.html
  5. Gera dashboard_final.html
  6. Abre no navegador automaticamente

DEPENDÊNCIAS: apenas bibliotecas nativas do Python 3
"""

import csv
import json
import os
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path


# ══════════════════════════════════════════════════════
#   CONFIGURAÇÕES GLOBAIS
# ══════════════════════════════════════════════════════

CSV_FILE      = "notas_dashboard.csv"
TEMPLATE_FILE = "dashboard_template.html"
OUTPUT_FILE   = "dashboard_final.html"
LOG_FILE      = "erros_processamento.log"

TAGS = [
    "BIO_ECO", "BIO_SATC", "BIO_CEL", "BIO_MQ",
    "BIO_EVO", "BIO_EMH", "BIO_ZOO", "BIO_BOT", "BIO_ANAFIS"
]

TIPOS_VALIDOS = {"avaliacao", "reforco"}

# Colunas obrigatórias (excluindo as de notas, validadas separadamente)
COLUNAS_BASE = [
    "ID_Aluno", "Nome_Completo", "Senha",
    "Turma", "Data_Avaliacao", "Tipo_Registro"
]

# Todas as colunas de notas esperadas
COLUNAS_NOTAS = [f"{tag}_{suf}" for tag in TAGS for suf in ("C", "E")]

# Lista completa de colunas obrigatórias
COLUNAS_OBRIGATORIAS = COLUNAS_BASE + COLUNAS_NOTAS


# ══════════════════════════════════════════════════════
#   GERENCIAMENTO DE LOG
# ══════════════════════════════════════════════════════

# Lista de erros acumulados durante o processamento
_erros: list[str] = []


def registrar_erro(num_linha: int, mensagem: str) -> None:
    """
    Registra um erro na lista interna e imprime no terminal.

    Args:
        num_linha: Número da linha do CSV onde ocorreu o erro.
        mensagem:  Descrição do erro encontrado.
    """
    texto = f"[Linha {num_linha:>4}]  {mensagem}"
    _erros.append(texto)
    print(f"         ⚠️  {texto}")


def salvar_log() -> None:
    """
    Persiste todos os erros registrados em erros_processamento.log.
    Sobrescreve o arquivo a cada execução.
    """
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("╔══════════════════════════════════════════════╗\n")
        f.write("║  BioTrack — Relatório de Erros               ║\n")
        f.write("╚══════════════════════════════════════════════╝\n\n")
        f.write(f"Data/Hora : {agora}\n")
        f.write(f"Arquivo   : {CSV_FILE}\n")
        f.write(f"Total de erros: {len(_erros)}\n")
        f.write("─" * 50 + "\n\n")

        if _erros:
            for erro in _erros:
                f.write(f"  {erro}\n")
        else:
            f.write("  ✅ Nenhum erro encontrado. Todas as linhas são válidas!\n")


# ══════════════════════════════════════════════════════
#   VALIDAÇÃO
# ══════════════════════════════════════════════════════

def validar_cabecalho(fieldnames: list[str]) -> tuple[bool, list[str]]:
    """
    Verifica se o cabeçalho do CSV contém todas as colunas obrigatórias.

    Args:
        fieldnames: Lista de nomes de colunas encontrados no CSV.

    Returns:
        Tupla (ok, colunas_faltando).
    """
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in fieldnames]
    return (len(faltando) == 0), faltando


def validar_linha(row: dict, num_linha: int) -> bool:
    """
    Valida todos os campos de uma linha do CSV.
    Registra cada problema encontrado via registrar_erro().

    Regras aplicadas:
      1. Campos obrigatórios não podem estar vazios.
      2. ID_Aluno não pode conter espaços.
      3. Data_Avaliacao deve estar no formato YYYY-MM-DD.
      4. Tipo_Registro deve ser 'avaliacao' ou 'reforco'.
      5. Todos os campos _C e _E devem ser inteiros >= 0.

    Args:
        row:       Dicionário com os dados da linha.
        num_linha: Número da linha no arquivo (para log).

    Returns:
        True se a linha é completamente válida, False caso contrário.
    """
    linha_ok = True

    # ── Regra 1: campos obrigatórios vazios ──────────────────────
    for col in COLUNAS_BASE:
        valor = row.get(col, "").strip()
        if not valor:
            registrar_erro(num_linha, f"Campo obrigatório vazio → '{col}'")
            linha_ok = False

    # Interrompe validação avançada se campos base estão faltando
    if not linha_ok:
        return False

    # ── Regra 2: ID_Aluno sem espaços ────────────────────────────
    if " " in row["ID_Aluno"].strip():
        registrar_erro(
            num_linha,
            f"ID_Aluno '{row['ID_Aluno']}' não pode conter espaços. "
            "Use underscore (_) ou hífen (-)."
        )
        linha_ok = False

    # ── Regra 3: formato da data ─────────────────────────────────
    data_str = row["Data_Avaliacao"].strip()
    try:
        datetime.strptime(data_str, "%Y-%m-%d")
    except ValueError:
        registrar_erro(
            num_linha,
            f"Data inválida → '{data_str}'. "
            "Use o formato AAAA-MM-DD (ex: 2026-01-15)"
        )
        linha_ok = False

    # ── Regra 4: tipo de registro ────────────────────────────────
    tipo = row["Tipo_Registro"].strip().lower()
    if tipo not in TIPOS_VALIDOS:
        registrar_erro(
            num_linha,
            f"Tipo_Registro inválido → '{row['Tipo_Registro']}'. "
            "Use: 'avaliacao' ou 'reforco'"
        )
        linha_ok = False

    # ── Regra 5: valores numéricos das notas ─────────────────────
    for tag in TAGS:
        for sufixo in ("_C", "_E"):
            col = tag + sufixo
            raw = row.get(col, "").strip()

            # Campo vazio
            if not raw:
                registrar_erro(num_linha, f"Campo de nota vazio → '{col}'")
                linha_ok = False
                continue

            # Deve ser inteiro
            try:
                valor = int(raw)
            except ValueError:
                registrar_erro(
                    num_linha,
                    f"'{col}' deve ser número inteiro → encontrado: '{raw}'"
                )
                linha_ok = False
                continue

            # Não pode ser negativo
            if valor < 0:
                registrar_erro(
                    num_linha,
                    f"'{col}' não pode ser negativo → encontrado: {valor}"
                )
                linha_ok = False

    return linha_ok


# ══════════════════════════════════════════════════════
#   LEITURA DO CSV
# ══════════════════════════════════════════════════════

def ler_csv() -> tuple[dict, int, int]:

    if not Path(CSV_FILE).exists():
        print(f"\n   ❌  Arquivo '{CSV_FILE}' não encontrado!")
        print(f"       Certifique-se de que ele está na mesma pasta que este script.")
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    alunos_raw: dict[str, list[dict]] = {}
    total_linhas   = 0
    linhas_validas = 0

    # ── Detecta encoding ─────────────────────────────────────────
    encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
    arquivo_enc = "utf-8-sig"

    for enc in encodings:
        try:
            with open(CSV_FILE, encoding=enc) as teste:
                teste.read()
            arquivo_enc = enc
            break
        except UnicodeDecodeError:
            continue

    print(f"         ℹ️   Encoding detectado: {arquivo_enc}")

    # ── Detecta separador (vírgula ou ponto e vírgula) ────────────
    with open(CSV_FILE, encoding=arquivo_enc) as f:
        primeira_linha = f.readline()

    qtd_virgula     = primeira_linha.count(",")
    qtd_ponto_virg  = primeira_linha.count(";")

    if qtd_ponto_virg > qtd_virgula:
        separador = ";"
        print("         ℹ️   Separador detectado: ponto e vírgula (;)  ← padrão Excel BR")
    else:
        separador = ","
        print("         ℹ️   Separador detectado: vírgula (,)")

    # ── Lê o CSV com o separador correto ─────────────────────────
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
            print("\n       Verifique o cabeçalho e tente novamente.")
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
#   CONVERSÃO PARA O FORMATO DO DASHBOARD
# ══════════════════════════════════════════════════════

def _calcular_pct(correct: int, wrong: int) -> int:
    """
    Calcula o percentual de acerto de forma segura.

    Args:
        correct: Número de acertos.
        wrong:   Número de erros.

    Returns:
        Percentual inteiro de 0 a 100.
    """
    total = correct + wrong
    if total == 0:
        return 0
    return round((correct / total) * 100)


def _formatar_label(data_str: str, tipo: str) -> str:
    """
    Gera o rótulo para o eixo X do gráfico de evolução.

    Formato: 'Aval.\\nJan/26'  ou  'Reforço\\nJan/26'

    Args:
        data_str: Data no formato YYYY-MM-DD.
        tipo:     'avaliacao' ou 'reforco'.

    Returns:
        String de rótulo formatada.
    """
    # Meses em português abreviados
    meses_pt = {
        1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr",
        5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago",
        9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
    }

    data_obj  = datetime.strptime(data_str, "%Y-%m-%d")
    mes_abrev = meses_pt[data_obj.month]
    ano_curto = data_obj.strftime("%y")

    prefixo = "Reforço" if tipo == "reforco" else "Aval."
    return f"{prefixo}\n{mes_abrev}/{ano_curto}"


def construir_users(alunos_raw: dict) -> dict:
    """
    Converte o dicionário de linhas brutas do CSV para o formato
    esperado pelo JavaScript do dashboard.

    Estrutura gerada:
    {
      "ANA001": {
        "password": "bio123",
        "name": "Ana Silva",
        "performance": {
          "BIO_ECO": {"correct": 24, "wrong": 6},
          ...
        },
        "evolution": [
          {"label": "Aval.\\nJan/26", "scores": {"BIO_ECO": 80, ...}},
          ...
        ]
      }
    }

    Args:
        alunos_raw: Saída da função ler_csv().

    Returns:
        Dicionário USERS pronto para serialização JSON.
    """
    users = {}

    for aluno_id, registros in alunos_raw.items():

        # ── Ordena cronologicamente ───────────────────────────────
        registros_ord = sorted(registros, key=lambda r: r["Data_Avaliacao"].strip())

        # ── Dados do aluno (usa o registro mais recente) ──────────
        ultimo = registros_ord[-1]
        nome   = ultimo["Nome_Completo"].strip()
        senha  = ultimo["Senha"].strip()

        # ── Performance: snapshot mais recente ───────────────────
        performance = {}
        for tag in TAGS:
            performance[tag] = {
                "correct": int(ultimo[f"{tag}_C"].strip()),
                "wrong":   int(ultimo[f"{tag}_E"].strip()),
            }

        # ── Evolution: histórico completo ─────────────────────────
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
            "password":    senha,
            "name":        nome,
            "performance": performance,
            "evolution":   evolution,
        }

    return users


# ══════════════════════════════════════════════════════
#   GERAÇÃO DO HTML FINAL
# ══════════════════════════════════════════════════════

MARCADOR = "/* ##BIOTRACK_USERS_DATA## */"


def gerar_html(users: dict) -> None:
    """
    Lê o dashboard_template.html, substitui o marcador pelo
    bloco USERS gerado e salva como dashboard_final.html.

    Args:
        users: Dicionário USERS construído por construir_users().

    Raises:
        SystemExit se o template não existir ou o marcador não for encontrado.
    """
    if not Path(TEMPLATE_FILE).exists():
        print(f"\n   ❌  Template '{TEMPLATE_FILE}' não encontrado!")
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    if MARCADOR not in html:
        print(f"\n   ❌  Marcador '{MARCADOR}' não encontrado no template!")
        print("       Verifique se o dashboard_template.html está correto.")
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    # Serializa o JSON com indentação legível
    users_json  = json.dumps(users, ensure_ascii=False, indent=2)
    novo_bloco  = f"const USERS = {users_json};"

    html_final = html.replace(MARCADOR, novo_bloco)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_final)


# ══════════════════════════════════════════════════════
#   INTERFACE DO TERMINAL
# ══════════════════════════════════════════════════════

def banner() -> None:
    """Exibe o cabeçalho visual no terminal."""
    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║   🧬  BioTrack — Processador de Dados  🧬   ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()


def separador() -> None:
    """Linha divisória para organizar o output."""
    print("  " + "─" * 46)


def passo(num: int, descricao: str) -> None:
    """
    Imprime o início de um passo numerado.

    Args:
        num:        Número do passo.
        descricao:  Texto descritivo.
    """
    print(f"\n  [{num}/5]  {descricao}")


# ══════════════════════════════════════════════════════
#   FUNÇÃO PRINCIPAL
# ══════════════════════════════════════════════════════

def main() -> None:
    """
    Orquestra todo o fluxo de processamento:

      1. Lê e valida o CSV
      2. Constrói o objeto USERS
      3. Gera o HTML final
      4. Salva o log de erros
      5. Abre o dashboard no navegador
    """
    banner()

    # ── Passo 1: Leitura e validação do CSV ───────────────────────
    passo(1, f"Lendo e validando  →  {CSV_FILE}")
    alunos_raw, linhas_validas, total_linhas = ler_csv()

    linhas_com_erro = total_linhas - linhas_validas
    print(f"         ✅  {linhas_validas} linha(s) válida(s) "
          f"de {total_linhas} total"
          + (f"  |  ⚠️  {linhas_com_erro} com erro" if linhas_com_erro else ""))

    if not alunos_raw:
        print("\n   ❌  Nenhum aluno válido encontrado no CSV!")
        print("       Verifique o arquivo e o log de erros.")
        salvar_log()
        input("\nPressione Enter para fechar...")
        sys.exit(1)

    # ── Passo 2: Conversão para formato do dashboard ──────────────
    passo(2, "Convertendo dados para o formato do dashboard...")
    users = construir_users(alunos_raw)
    print(f"         ✅  {len(users)} aluno(s) processado(s):")
    for aluno_id, dados in users.items():
        qtd_aval = len(dados["evolution"])
        print(f"              •  {aluno_id:<10}  →  {dados['name']}"
              f"  ({qtd_aval} avaliação/ões)")

    # ── Passo 3: Geração do HTML final ────────────────────────────
    passo(3, f"Gerando  →  {OUTPUT_FILE}")
    gerar_html(users)
    print(f"         ✅  {OUTPUT_FILE}  gerado com sucesso!")

    # ── Passo 4: Salvar log ───────────────────────────────────────
    passo(4, f"Salvando relatório  →  {LOG_FILE}")
    salvar_log()
    if _erros:
        print(f"         ⚠️   {len(_erros)} erro(s) registrado(s) → abra {LOG_FILE} para detalhes")
    else:
        print(f"         ✅  Sem erros! Log limpo salvo em {LOG_FILE}")

    # ── Passo 5: Abrir no navegador ───────────────────────────────
    passo(5, "Abrindo dashboard no navegador...")
    caminho_abs = Path(OUTPUT_FILE).resolve()
    webbrowser.open(caminho_abs.as_uri())
    print(f"         ✅  {caminho_abs.as_uri()}")

    # ── Resumo final ──────────────────────────────────────────────
    separador()
    print()
    print("  🎉  Processamento concluído com sucesso!")
    print()
    if linhas_com_erro:
        print(f"  ⚠️   {linhas_com_erro} linha(s) ignorada(s) por erro.")
        print(f"       Detalhes em: {LOG_FILE}")
        print()
    separador()
    print()
    input("  Pressione Enter para fechar...")


# ══════════════════════════════════════════════════════
#   ENTRY POINT
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    main()