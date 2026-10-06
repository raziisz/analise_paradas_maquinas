"""Análise reproduzível do Projeto Integrador — Paradas de Máquinas.

O pipeline segue o roteiro do projeto e os materiais de EDA dos documentos em
``.docs``: diagnóstico, estatística, limpeza/validação e visualização.

Uso: python analise_paradas_maquinas.py

Dependências: numpy, pandas, matplotlib, seaborn e plotly.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
import logging
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns


@dataclass(frozen=True)
class Configuracao:
    """Caminhos e regras de negócio usadas em todo o pipeline."""

    base_dir: Path = Path(__file__).resolve().parent
    nome_csv: str = "projeto_integrador_paradas_maquinas.csv"
    nome_relatorio: str = "respostas_projeto_integrador.txt"
    nome_resultados: str = "resultados"
    nome_log: str = "analise_paradas_maquinas.log"
    duracao_turno_min: float = 480.0
    janela_media_movel: int = 5

    @property
    def arquivo_csv(self) -> Path:
        return self.base_dir / self.nome_csv

    @property
    def arquivo_relatorio(self) -> Path:
        return self.base_dir / self.nome_relatorio

    @property
    def pasta_resultados(self) -> Path:
        return self.base_dir / self.nome_resultados

    @property
    def arquivo_log(self) -> Path:
        return self.pasta_resultados / self.nome_log


CONFIG = Configuracao()
LOGGER = logging.getLogger("projeto_integrador.paradas_maquinas")

COLUNAS_NUMERICAS = [
    "horas_desde_manutencao", "temperatura_ambiente_c", "umidade_relativa_pct",
    "temperatura_motor_c", "vibracao_mm_s", "pecas_montadas", "qtd_paradas",
    "tempo_parado_min",
]
COLUNAS_INDICADOR = COLUNAS_NUMERICAS + ["disponibilidade"]
CHAVE_REGISTRO = ["data", "turno", "linha", "maquina"]
LIMITES_FISICOS = {
    "horas_desde_manutencao": (0, None),
    "umidade_relativa_pct": (0, 100),
    "vibracao_mm_s": (0, None),
    "pecas_montadas": (0, None),
    "qtd_paradas": (0, None),
    "tempo_parado_min": (0, CONFIG.duracao_turno_min),
}


def configurar_logger(configuracao: Configuracao) -> logging.Logger:
    """Configura log no console e em arquivo UTF-8, sem duplicar handlers."""
    configuracao.pasta_resultados.mkdir(parents=True, exist_ok=True)
    for handler in LOGGER.handlers[:]:
        handler.close()
        LOGGER.removeHandler(handler)

    LOGGER.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    arquivo = logging.FileHandler(configuracao.arquivo_log, mode="w", encoding="utf-8")
    console = logging.StreamHandler()
    arquivo.setFormatter(formato)
    console.setFormatter(formato)
    LOGGER.addHandler(arquivo)
    LOGGER.addHandler(console)
    LOGGER.info("=" * 100)
    LOGGER.info("ANALISE DE PARADAS DE MAQUINAS | inicio")
    LOGGER.info("arquivo_log=%s", configuracao.arquivo_log)
    return LOGGER


def registrar_tabela_log(titulo: str, tabela: pd.DataFrame, colunas: list[str]) -> None:
    """Registra uma tabela alinhada no log para facilitar leitura e apresentação."""
    if tabela.empty:
        LOGGER.info("\n[%s]\nsem registros", titulo)
        return

    visualizacao = tabela.loc[:, [coluna for coluna in colunas if coluna in tabela.columns]].copy()
    for coluna in visualizacao.columns:
        if coluna in {
            "n", "registros", "qtd_paradas", "quantidade", "linha_csv",
            "registros_antes", "registros_depois", "removidos", "quantidade",
        }:
            visualizacao[coluna] = visualizacao[coluna].map(
                lambda valor: "-" if pd.isna(valor) else f"{float(valor):.0f}"
            )
        elif pd.api.types.is_numeric_dtype(visualizacao[coluna]):
            visualizacao[coluna] = visualizacao[coluna].map(
                lambda valor: "-" if pd.isna(valor) else f"{float(valor):.2f}"
            )

    LOGGER.info("\n[%s]\n%s", titulo, visualizacao.to_string(index=False))


def corrigir_mojibake(valor: object) -> object:
    """Corrige texto UTF-8 interpretado como Latin-1, quando necessário."""
    if pd.isna(valor):
        return pd.NA
    texto = str(valor).strip()
    for _ in range(2):
        if not any(marca in texto for marca in ("Ã", "Â", "â", "�")):
            break
        try:
            convertido = texto.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if convertido == texto:
            break
        texto = convertido
    return texto or pd.NA


def remover_acentos(valor: object) -> str:
    texto = "" if pd.isna(valor) else str(valor)
    return "".join(
        caractere for caractere in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caractere)
    )


def normalizar_categorias(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza categorias sem alterar o significado dos registros."""
    resultado = df.copy()
    for coluna in resultado.select_dtypes(include=["object", "string"]).columns:
        resultado[coluna] = resultado[coluna].map(corrigir_mojibake).astype("string")

    resultado["linha"] = resultado["linha"].str.strip().str.upper()
    turno = resultado["turno"].map(remover_acentos).str.strip().str.lower()
    resultado["turno"] = turno.replace(
        {"manha": "Manhã", "tarde": "Tarde", "noite": "Noite", "noturno": "Noite"}
    )

    maquina = resultado["maquina"].str.upper().str.replace(" ", "", regex=False)
    numero_maquina = maquina.str.extract(r"PNP-?0*([1-6])", expand=False)
    resultado["maquina"] = "PNP-" + numero_maquina.str.zfill(2)
    resultado.loc[numero_maquina.isna(), "maquina"] = maquina[numero_maquina.isna()]
    resultado["modelo_maquina"] = (
        resultado["modelo_maquina"].str.strip().str.lower().str.capitalize()
    )
    return resultado


def converter_numero(serie: pd.Series) -> pd.Series:
    """Converte números com ponto ou vírgula decimal."""
    texto = serie.astype("string").str.strip().replace({"": pd.NA, "<NA>": pd.NA, "nan": pd.NA})
    possui_dois_separadores = texto.str.contains(",", na=False) & texto.str.contains(".", regex=False, na=False)
    texto.loc[possui_dois_separadores] = (
        texto.loc[possui_dois_separadores]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(texto.str.replace(",", ".", regex=False), errors="coerce")


def converter_data(serie: pd.Series) -> pd.Series:
    """Aceita os formatos ISO e dia/mês/ano encontrados na base."""
    resultado = pd.to_datetime(serie, format="%Y-%m-%d", errors="coerce")
    faltantes = resultado.isna()
    resultado.loc[faltantes] = pd.to_datetime(
        serie.loc[faltantes], format="%d/%m/%Y", errors="coerce"
    )
    return resultado


def carregar_base(caminho: Path = CONFIG.arquivo_csv) -> pd.DataFrame:
    """Lê como texto primeiro para preservar evidências de qualidade."""
    df = pd.read_csv(caminho, dtype="string", keep_default_na=False, na_values=[""])
    df.insert(0, "linha_csv", np.arange(2, len(df) + 2))
    df["data_original"] = df["data"]
    df = normalizar_categorias(df)
    df["data"] = converter_data(df["data"])
    for coluna in COLUNAS_NUMERICAS:
        df[coluna] = converter_numero(df[coluna])
    df["disponibilidade"] = (
        (CONFIG.duracao_turno_min - df["tempo_parado_min"])
        / CONFIG.duracao_turno_min * 100
    )
    LOGGER.info("carregamento | arquivo=%s | linhas=%d | colunas=%d", caminho.name, len(df), len(df.columns) - 3)
    LOGGER.info("periodo | inicio=%s | fim=%s", df["data"].min().date(), df["data"].max().date())
    LOGGER.info(
        "disponibilidade_bruta | media=%.2f | mediana=%.2f | minimo=%.2f | maximo=%.2f",
        df["disponibilidade"].mean(), df["disponibilidade"].median(),
        df["disponibilidade"].min(), df["disponibilidade"].max(),
    )
    return df


def diagnosticar_qualidade(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Produz ocorrências inválidas e um resumo auditável da qualidade."""
    problemas: list[dict[str, object]] = []
    invalidas = pd.Series(False, index=df.index)

    for campo, quantidade in df.isna().sum().items():
        problemas.append({"problema": "ausentes", "campo": campo, "quantidade": int(quantidade)})
        if quantidade:
            LOGGER.info("ausentes | campo=%s | quantidade=%d", campo, quantidade)
    colunas_dados = [
        coluna for coluna in df.columns
        if coluna not in {"linha_csv", "data_original", "disponibilidade"}
    ]
    duplicados_exatos = int(df.duplicated(subset=colunas_dados, keep="first").sum())
    duplicados_chave = int(df.duplicated(CHAVE_REGISTRO, keep="first").sum())
    problemas.extend([
        {"problema": "duplicados_exatos", "campo": "todas_as_colunas", "quantidade": duplicados_exatos},
        {"problema": "duplicados_chave", "campo": " × ".join(CHAVE_REGISTRO), "quantidade": duplicados_chave},
    ])
    LOGGER.info("duplicados | exatos=%d | chave=%d", duplicados_exatos, duplicados_chave)

    registros_invalidos: list[dict[str, object]] = []
    data_invalida = df["data"].isna()
    invalidas |= data_invalida
    for _, linha in df.loc[data_invalida].iterrows():
        registros_invalidos.append({
            "linha_csv": linha["linha_csv"], "campo": "data", "valor": linha["data_original"]
        })

    for coluna, (minimo, maximo) in LIMITES_FISICOS.items():
        serie = df[coluna]
        mascara = serie.notna()
        if minimo is not None:
            mascara &= serie < minimo
        if maximo is not None:
            mascara |= serie.notna() & (serie > maximo)
        mascara = mascara.fillna(False)
        invalidas |= mascara
        for _, linha in df.loc[mascara].iterrows():
            registros_invalidos.append({
                "linha_csv": linha["linha_csv"], "campo": coluna, "valor": linha[coluna]
            })

    invalidos_df = pd.DataFrame(registros_invalidos, columns=["linha_csv", "campo", "valor"])
    problemas.append({
        "problema": "valores_invalidos", "campo": "limites_fisicos", "quantidade": int(invalidas.sum())
    })
    for campo, quantidade in invalidos_df["campo"].value_counts().items():
        LOGGER.info("invalidos | campo=%s | ocorrencias=%d", campo, quantidade)
    LOGGER.info("diagnostico_concluido | registros_invalidos=%d", int(invalidas.sum()))
    return invalidos_df, pd.DataFrame(problemas)


def limpar_base(df: pd.DataFrame, invalidos: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove apenas impossíveis e duplicidades de chave, registrando tudo."""
    indices_invalidos = set(invalidos["linha_csv"].tolist())
    removidos: list[dict[str, object]] = []
    manter = ~df["linha_csv"].isin(indices_invalidos)
    for _, linha in df.loc[~manter].iterrows():
        removidos.append({"linha_csv": linha["linha_csv"], "motivo": "valor inválido"})

    candidatos = df.loc[manter].copy()
    repetidos = candidatos.duplicated(CHAVE_REGISTRO, keep="first")
    for _, linha in candidatos.loc[repetidos].iterrows():
        removidos.append({"linha_csv": linha["linha_csv"], "motivo": "duplicado de chave"})
    limpos = candidatos.loc[~repetidos].copy()
    LOGGER.info(
        "limpeza | antes=%d | depois=%d | removidos_invalidos=%d | removidos_duplicados=%d",
        len(df), len(limpos), int((~manter).sum()), int(repetidos.sum()),
    )
    return limpos, pd.DataFrame(removidos, columns=["linha_csv", "motivo"])


def resumo_disponibilidade(df: pd.DataFrame, grupos: str | list[str]) -> pd.DataFrame:
    """Calcula média, mediana, extremos, desvio, quartis e IQR."""
    agrupado = df.groupby(grupos, dropna=False, observed=False)["disponibilidade"]
    resumo = agrupado.agg(
        n="count", media="mean", mediana="median", minimo="min",
        maximo="max", desvio_padrao="std"
    )
    resumo["q1"] = agrupado.quantile(0.25)
    resumo["q3"] = agrupado.quantile(0.75)
    resumo["iqr"] = resumo["q3"] - resumo["q1"]
    return resumo.reset_index()


def calcular_estatisticas(df: pd.DataFrame, pasta: Path) -> dict[str, pd.DataFrame]:
    """Gera tabelas estatísticas, correlações e falhas."""
    tabelas: dict[str, pd.DataFrame] = {}
    eixos = {
        "linha": "resumo_disponibilidade_por_linha.csv",
        "maquina": "resumo_disponibilidade_por_maquina.csv",
        "turno": "resumo_disponibilidade_por_turno.csv",
        "linha_turno": "resumo_disponibilidade_linha_turno.csv",
        "maquina_turno": "resumo_disponibilidade_maquina_turno.csv",
    }
    for nome, arquivo in eixos.items():
        tabela = resumo_disponibilidade(df, nome.split("_"))
        tabela.to_csv(pasta / arquivo, index=False, encoding="utf-8-sig")
        tabelas[nome] = tabela
        LOGGER.info("estatisticas | tabela=%s | grupos=%d", nome, len(tabela))
        registrar_tabela_log(
            f"ESTATISTICAS DE DISPONIBILIDADE | {nome}",
            tabela,
            nome.split("_") + ["n", "media", "mediana", "minimo", "maximo", "desvio_padrao", "q1", "q3", "iqr"],
        )

    estatisticas = df[COLUNAS_INDICADOR].describe(percentiles=[0.25, 0.50, 0.75]).T
    estatisticas = estatisticas.rename(columns={
        "count": "n", "mean": "media", "std": "desvio_padrao", "min": "minimo",
        "25%": "q1", "50%": "mediana", "75%": "q3", "max": "maximo",
    })
    estatisticas["mediana"] = df[COLUNAS_INDICADOR].median()
    estatisticas["iqr"] = estatisticas["q3"] - estatisticas["q1"]
    estatisticas = estatisticas.reset_index(names="variavel")
    estatisticas.to_csv(pasta / "estatisticas_descritivas_numericas.csv", index=False, encoding="utf-8-sig")
    tabelas["estatisticas"] = estatisticas
    registrar_tabela_log(
        "ESTATISTICAS NUMERICAS",
        estatisticas,
        ["variavel", "n", "media", "mediana", "minimo", "maximo", "desvio_padrao", "q1", "q3", "iqr"],
    )

    matriz = df[COLUNAS_INDICADOR].corr(numeric_only=True)
    matriz.to_csv(pasta / "matriz_correlacao.csv", encoding="utf-8-sig")
    tabelas["correlacoes"] = matriz
    matriz["tempo_parado_min"].drop("tempo_parado_min").rename("correlacao_pearson").to_csv(
        pasta / "correlacoes_com_tempo_parado.csv", encoding="utf-8-sig"
    )
    tabela_correlacao = (
        matriz["tempo_parado_min"]
        .drop("tempo_parado_min")
        .rename("correlacao_pearson")
        .reset_index()
        .rename(columns={"index": "variavel"})
    )
    registrar_tabela_log(
        "CORRELACOES COM TEMPO PARADO",
        tabela_correlacao,
        ["variavel", "correlacao_pearson"],
    )

    falhas = (
        df.groupby("tipo_falha_principal", dropna=False, observed=False)
        .agg(registros=("tipo_falha_principal", "size"), qtd_paradas=("qtd_paradas", "sum"),
             tempo_parado_min=("tempo_parado_min", "sum"), disponibilidade_media=("disponibilidade", "mean"))
        .sort_values("tempo_parado_min", ascending=False).reset_index()
    )
    falhas.to_csv(pasta / "tempo_parado_por_tipo_falha.csv", index=False, encoding="utf-8-sig")
    tabelas["falhas"] = falhas
    registrar_tabela_log(
        "TEMPO PARADO POR TIPO DE FALHA",
        falhas,
        ["tipo_falha_principal", "registros", "qtd_paradas", "tempo_parado_min", "disponibilidade_media"],
    )
    return tabelas


def calcular_serie_temporal(df: pd.DataFrame, pasta: Path) -> tuple[pd.DataFrame, float | None]:
    diario = (
        df.groupby(["data", "linha"], as_index=False, observed=False)
        .agg(disponibilidade_media=("disponibilidade", "mean"),
             tempo_parado_total_min=("tempo_parado_min", "sum"), registros=("disponibilidade", "count"))
        .sort_values(["linha", "data"])
    )
    diario["media_movel_5"] = diario.groupby("linha", observed=False)["disponibilidade_media"].transform(
        lambda serie: serie.rolling(CONFIG.janela_media_movel, min_periods=1).mean()
    )
    diario.to_csv(pasta / "serie_diaria_por_linha.csv", index=False, encoding="utf-8-sig")

    datas = sorted(df["data"].dropna().dt.date.unique())
    if len(datas) < 2:
        return diario, None
    corte = datas[(len(datas) - 1) // 2]
    primeira = df.loc[df["data"].dt.date <= corte, "disponibilidade"].mean()
    segunda = df.loc[df["data"].dt.date > corte, "disponibilidade"].mean()
    registrar_tabela_log(
        "RESUMO TEMPORAL",
        pd.DataFrame([{
            "corte": corte,
            "media_primeira_metade": primeira,
            "media_segunda_metade": segunda,
            "diferenca_pontos_percentuais": segunda - primeira,
        }]),
        ["corte", "media_primeira_metade", "media_segunda_metade", "diferenca_pontos_percentuais"],
    )
    LOGGER.info(
        "periodo_metades | corte=%s | primeira_metade=%.2f | segunda_metade=%.2f | diferenca=%.2f",
        corte, primeira, segunda, segunda - primeira,
    )
    return diario, float(segunda - primeira)


def identificar_outliers(df: pd.DataFrame, pasta: Path) -> pd.DataFrame:
    """Sinaliza outliers por IQR sem removê-los automaticamente."""
    q1, q3 = df["disponibilidade"].quantile([0.25, 0.75])
    iqr = q3 - q1
    inferior, superior = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = df.loc[(df["disponibilidade"] < inferior) | (df["disponibilidade"] > superior)].copy()
    outliers["limite_inferior_iqr"] = inferior
    outliers["limite_superior_iqr"] = superior
    outliers.to_csv(pasta / "outliers_disponibilidade.csv", index=False, encoding="utf-8-sig")
    registrar_tabela_log(
        "RESUMO DE OUTLIERS POR IQR",
        pd.DataFrame([{
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "limite_inferior": inferior,
            "limite_superior": superior,
            "quantidade": len(outliers),
        }]),
        ["q1", "q3", "iqr", "limite_inferior", "limite_superior", "quantidade"],
    )
    LOGGER.info(
        "outliers_iqr | q1=%.2f | q3=%.2f | iqr=%.2f | limite_inferior=%.2f | limite_superior=%.2f | quantidade=%d",
        q1, q3, iqr, inferior, superior, len(outliers),
    )
    return outliers


def salvar_figura(figura: plt.Figure, pasta: Path, nome: str) -> str:
    figura.tight_layout()
    figura.savefig(pasta / nome, dpi=150, bbox_inches="tight")
    plt.close(figura)
    return nome


def gerar_graficos(df: pd.DataFrame, pasta: Path) -> list[str]:
    """Gera gráficos orientados por perguntas da Unidade 4."""
    sns.set_theme(style="whitegrid", context="notebook")
    arquivos: list[str] = []

    diario = (
        df.groupby(["data", "linha"], as_index=False, observed=False)["disponibilidade"]
        .mean().sort_values(["linha", "data"])
    )
    diario["media_movel"] = diario.groupby("linha", observed=False)["disponibilidade"].transform(
        lambda serie: serie.rolling(CONFIG.janela_media_movel, min_periods=1).mean()
    )
    fig, ax = plt.subplots(figsize=(11, 5))
    for linha, grupo in diario.groupby("linha", observed=False):
        ax.plot(grupo["data"], grupo["disponibilidade"], alpha=0.25)
        ax.plot(grupo["data"], grupo["media_movel"], linewidth=2, label=linha)
    ax.axhline(90, color="black", linestyle="--", linewidth=1, label="Referência 90%")
    ax.set(title="Disponibilidade ao longo do tempo por linha", xlabel="Data", ylabel="Disponibilidade (%)")
    ax.legend(title="Linha")
    fig.autofmt_xdate()
    arquivo = salvar_figura(fig, pasta, "01_disponibilidade_tempo_linha.png")
    arquivos.append(arquivo)
    LOGGER.info("grafico | arquivo=%s | pergunta=quando_e_qual_linha", arquivo)

    matriz = df.pivot_table(index="maquina", columns="turno", values="disponibilidade", aggfunc="mean").astype(float)
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.heatmap(matriz, annot=True, fmt=".1f", cmap="RdYlGn", vmin=0, vmax=100, ax=ax)
    ax.set(title="Disponibilidade média por máquina × turno", xlabel="Turno", ylabel="Máquina")
    arquivo = salvar_figura(fig, pasta, "02_heatmap_maquina_turno.png")
    arquivos.append(arquivo)
    LOGGER.info("grafico | arquivo=%s | pergunta=onde_se_concentra", arquivo)

    falhas = df.groupby("tipo_falha_principal", observed=False)["tempo_parado_min"].sum().sort_values(ascending=False)
    acumulado = falhas.cumsum() / falhas.sum() * 100
    fig, ax1 = plt.subplots(figsize=(11, 5))
    falhas.plot(kind="bar", ax=ax1, color="#2166ac")
    ax1.set(title="Pareto do tempo parado por tipo de falha", xlabel="Tipo de falha", ylabel="Minutos parados")
    ax1.tick_params(axis="x", rotation=45)
    ax2 = ax1.twinx()
    ax2.plot(np.arange(len(acumulado)), acumulado.to_numpy(), color="#b2182b", marker="o")
    ax2.set_ylabel("Percentual acumulado (%)")
    ax2.set_ylim(0, 105)
    arquivo = salvar_figura(fig, pasta, "03_pareto_tipo_falha.png")
    arquivos.append(arquivo)
    LOGGER.info("grafico | arquivo=%s | pergunta=qual_falha_domina", arquivo)

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.boxplot(data=df, x="linha", y="vibracao_mm_s", ax=ax)
    ax.set(title="Distribuição da vibração por linha", xlabel="Linha", ylabel="Vibração (mm/s)")
    arquivo = salvar_figura(fig, pasta, "04_boxplot_vibracao_linha.png")
    arquivos.append(arquivo)
    LOGGER.info("grafico | arquivo=%s | pergunta=distribuicao_da_vibracao", arquivo)

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.scatterplot(data=df, x="vibracao_mm_s", y="tempo_parado_min", hue="linha", alpha=0.65, ax=ax)
    ax.set(title="Vibração × tempo parado", xlabel="Vibração (mm/s)", ylabel="Tempo parado (min)")
    arquivo = salvar_figura(fig, pasta, "05_dispersao_vibracao_tempo_parado.png")
    arquivos.append(arquivo)
    LOGGER.info("grafico | arquivo=%s | pergunta=associacao_vibracao_parada", arquivo)

    try:
        import plotly.express as px
        figura = px.scatter(df, x="vibracao_mm_s", y="tempo_parado_min", color="linha",
                            hover_data=["data", "turno", "maquina", "tipo_falha_principal"],
                            title="Exploração interativa: vibração × tempo parado")
        figura.write_html(pasta / "06_interativo_vibracao_tempo_parado.html")
        arquivos.append("06_interativo_vibracao_tempo_parado.html")
        LOGGER.info("grafico | arquivo=06_interativo_vibracao_tempo_parado.html | tipo=plotly")
    except ImportError:
        LOGGER.warning("grafico_interativo | plotly_nao_instalado")
        pass
    return arquivos


def formato_numero(valor: object, casas: int = 2) -> str:
    if pd.isna(valor):
        return "NA"
    return f"{float(valor):.{casas}f}".replace(".", ",")


def formato_percentual(valor: object, casas: int = 2) -> str:
    return formato_numero(valor, casas) + "%"


def linhas_resumo(tabela: pd.DataFrame) -> str:
    linhas = []
    for _, registro in tabela.iterrows():
        grupos = [str(registro[coluna]) for coluna in ("linha", "maquina", "turno") if coluna in tabela.columns]
        linhas.append(
            f"- {' × '.join(grupos)}: n={int(registro['n'])}, média={formato_percentual(registro['media'])}, "
            f"mediana={formato_percentual(registro['mediana'])}, desvio={formato_numero(registro['desvio_padrao'])}, "
            f"mínimo={formato_percentual(registro['minimo'])}, máximo={formato_percentual(registro['maximo'])}, "
            f"Q1={formato_percentual(registro['q1'])}, Q3={formato_percentual(registro['q3'])}, "
            f"IQR={formato_numero(registro['iqr'])} p.p."
        )
    return "\n".join(linhas)


def exportar_base(df: pd.DataFrame, caminho: Path) -> None:
    exportacao = df.copy()
    exportacao["data"] = exportacao["data"].dt.strftime("%Y-%m-%d")
    exportacao.to_csv(caminho, index=False, encoding="utf-8-sig")


def gerar_relatorio(bruto: pd.DataFrame, limpo: pd.DataFrame, invalidos: pd.DataFrame,
                    removidos: pd.DataFrame, qualidade: pd.DataFrame,
                    tabelas: dict[str, pd.DataFrame], tabelas_iniciais: dict[str, pd.DataFrame],
                    delta_periodo: float | None,
                    graficos: list[str], caminho: Path) -> None:
    por_linha, por_maquina = tabelas["linha"], tabelas["maquina"]
    por_turno, por_linha_turno = tabelas["turno"], tabelas["linha_turno"]
    inicial_linha = tabelas_iniciais["linha"]
    inicial_maquina = tabelas_iniciais["maquina"]
    inicial_turno = tabelas_iniciais["turno"]
    inicial_linha_turno = tabelas_iniciais["linha_turno"]
    falhas = tabelas["falhas"]
    correlacoes = tabelas["correlacoes"]["tempo_parado_min"].drop("tempo_parado_min")
    pior_maquina = por_maquina.loc[por_maquina["media"].idxmin()]
    pior_linha = por_linha.loc[por_linha["media"].idxmin()]
    pior_turno = por_turno.loc[por_turno["media"].idxmin()]
    pior_combinacao = por_linha_turno.loc[por_linha_turno["media"].idxmin()]
    principal_falha = falhas.iloc[0]
    ausentes = ", ".join(
        f"{r['campo']}={int(r['quantidade'])}" for _, r in qualidade[qualidade["problema"] == "ausentes"].iterrows()
        if r["quantidade"] > 0
    ) or "nenhum"
    datas = bruto["data"].dropna()
    graficos_texto = "\n".join(f"- {nome}" for nome in graficos)

    texto = f"""PROJETO INTEGRADOR — PARADAS DE MÁQUINAS
Respostas baseadas no Roteiro_Projeto_Integrador_Paradas_Maquinas.docx.
Conhecimentos aplicados: materiais em .docs/ sobre Pandas, NumPy, EDA, visualização e pipeline auditável.

A análise separa evidência, interpretação, hipótese e limitação. Associação não prova causalidade.

1. UNIDADE 1 — PRIMEIRO DIAGNÓSTICO

Base: {len(bruto)} registros × 14 colunas.
Período: {datas.min().date() if not datas.empty else 'NA'} a {datas.max().date() if not datas.empty else 'NA'}.
Indicador: disponibilidade (%) = (480 − tempo parado) ÷ 480 × 100.
Disponibilidade bruta: média={formato_percentual(bruto['disponibilidade'].mean())}, mediana={formato_percentual(bruto['disponibilidade'].median())}, mínimo={formato_percentual(bruto['disponibilidade'].min())}, máximo={formato_percentual(bruto['disponibilidade'].max())}.

Por linha, antes da limpeza:
{linhas_resumo(inicial_linha)}

Por máquina, antes da limpeza:
{linhas_resumo(inicial_maquina)}

Por turno, antes da limpeza:
{linhas_resumo(inicial_turno)}

Por linha × turno, antes da limpeza:
{linhas_resumo(inicial_linha_turno)}

Pontos de atenção: menor média por máquina em {pior_maquina['maquina']}; menor linha em {pior_linha['linha']}; menor turno em {pior_turno['turno']}; menor combinação em {pior_combinacao['linha']} × {pior_combinacao['turno']}.
Falha com maior tempo acumulado: {principal_falha['tipo_falha_principal']} ({formato_numero(principal_falha['tempo_parado_min'], 0)} min).
Ausentes: {ausentes}. Duplicados e limites inválidos foram diagnosticados antes da limpeza.

H1 — desgaste/manutenção: mais horas desde a manutenção estão associadas a mais tempo parado.
H2 — concentração operacional: a perda está concentrada em linha, máquina ou turno específicos.
H3 — condição do equipamento: vibração e/ou temperatura do motor acompanham o aumento do tempo parado.

Pergunta investigativa: onde e quando a disponibilidade caiu, qual grupo concentra a perda e qual hipótese é mais compatível após a validação?

2. UNIDADE 2 — ESTATÍSTICA E HIPÓTESES

As tabelas calculam média, mediana, mínimo, máximo, desvio padrão, Q1, Q3 e IQR.
Variação entre metades cronológicas: {formato_numero(delta_periodo)} pontos percentuais.
Correlações de Pearson com tempo parado: manutenção={formato_numero(correlacoes.get('horas_desde_manutencao'), 3)}, vibração={formato_numero(correlacoes.get('vibracao_mm_s'), 3)}, temperatura do motor={formato_numero(correlacoes.get('temperatura_motor_c'), 3)}.

H1, H2 e H3 ganham força como hipóteses associativas; ainda é necessário controlar por máquina, tempo e sequência da falha.

3. UNIDADE 3 — LIMPEZA E VALIDAÇÃO

Pipeline: preservar a base bruta; corrigir texto; converter datas/números; validar limites físicos; remover valores impossíveis e duplicidades de chave; não imputar sensores; recalcular indicadores.
Antes × depois: {len(bruto)} → {len(limpo)} registros; {len(removidos)} removidos; disponibilidade média {formato_percentual(bruto['disponibilidade'].mean())} → {formato_percentual(limpo['disponibilidade'].mean())}.
Outliers foram apenas sinalizados por IQR, pois ponto extremo não é automaticamente erro.

Após a limpeza, H1 permanece associativa, H2 permanece como explicação de concentração e H3 permanece compatível com os sensores, sem prova de causa.

4. UNIDADE 4 — EDA, VISUALIZAÇÃO E CONCLUSÃO

Visualizações geradas:
{graficos_texto}

Leitura em camadas:
- Evidência: {pior_maquina['maquina']} tem a menor disponibilidade média; {principal_falha['tipo_falha_principal']} concentra o maior tempo parado.
- Interpretação: a perda não é uniforme e há grupos/tipos de falha prioritários.
- Hipótese: concentração operacional combinada com desgaste ou condição do equipamento.
- Limitação: faltam timestamps detalhados, sequência sensor-falha e registros completos de intervenção; associação não implica causalidade.

Respostas finais:
1. O que aconteceu? A disponibilidade variou entre grupos, com diferença de {formato_numero(delta_periodo)} p.p. entre as metades cronológicas.
2. Onde aconteceu? Principalmente em {pior_maquina['maquina']}, {pior_linha['linha']} e {pior_combinacao['linha']} × {pior_combinacao['turno']}.
3. Quando começou? A série diária e a média móvel do gráfico 01 mostram a tendência; a comparação de metades não define uma data causal.
4. Evidências: estatísticas descritivas, IQR, heatmap, Pareto, boxplot, correlações e dispersão.
5. Explicação mais plausível: concentração operacional combinada com possível desgaste/condição de equipamento, ainda como hipótese.
6. Próximas ações: inspecionar {pior_maquina['maquina']} e {principal_falha['tipo_falha_principal']}; acompanhar manutenção/vibração/temperatura com limites de engenharia; coletar timestamps e intervenções.

Mensagem central: A disponibilidade se concentra em {pior_maquina['maquina']} e {pior_linha['linha']}; manutenção e condição do equipamento são hipóteses plausíveis a confirmar com dados temporais.

Storyboard: (1) problema com série temporal; (2) investigação com heatmap/Pareto e validação antes × depois; (3) resolução com dispersão, limitações e ações.
"""
    caminho.write_text(texto, encoding="utf-8")


def executar(configuracao: Configuracao = CONFIG) -> None:
    configurar_logger(configuracao)
    LOGGER.info("etapa=carregamento")
    bruto = carregar_base(configuracao.arquivo_csv)
    LOGGER.info("etapa=diagnostico_qualidade")
    invalidos, qualidade = diagnosticar_qualidade(bruto)
    registrar_tabela_log(
        "DIAGNOSTICO DE QUALIDADE",
        qualidade,
        ["problema", "campo", "quantidade"],
    )
    registrar_tabela_log(
        "REGISTROS INVALIDOS",
        invalidos,
        ["linha_csv", "campo", "valor"],
    )
    LOGGER.info("etapa=limpeza_validacao")
    limpo, removidos = limpar_base(bruto, invalidos)
    registrar_tabela_log(
        "RESUMO DA LIMPEZA",
        pd.DataFrame([{
            "registros_antes": len(bruto),
            "registros_depois": len(limpo),
            "removidos": len(removidos),
            "media_antes": bruto["disponibilidade"].mean(),
            "media_depois": limpo["disponibilidade"].mean(),
        }]),
        ["registros_antes", "registros_depois", "removidos", "media_antes", "media_depois"],
    )
    tabelas_iniciais = {
        eixo: resumo_disponibilidade(bruto, eixo.split("_"))
        for eixo in ("linha", "maquina", "turno", "linha_turno")
    }
    exportar_base(bruto, configuracao.pasta_resultados / "base_bruta_normalizada.csv")
    exportar_base(limpo, configuracao.pasta_resultados / "base_tratada.csv")
    invalidos.to_csv(configuracao.pasta_resultados / "diagnostico_invalidos.csv", index=False, encoding="utf-8-sig")
    removidos.to_csv(configuracao.pasta_resultados / "removidos.csv", index=False, encoding="utf-8-sig")
    qualidade.to_csv(configuracao.pasta_resultados / "diagnostico_qualidade.csv", index=False, encoding="utf-8-sig")
    LOGGER.info("etapa=estatistica_descritiva")
    tabelas = calcular_estatisticas(limpo, configuracao.pasta_resultados)
    LOGGER.info("etapa=analise_temporal")
    _, delta_periodo = calcular_serie_temporal(limpo, configuracao.pasta_resultados)
    LOGGER.info("etapa=outliers")
    identificar_outliers(limpo, configuracao.pasta_resultados)
    LOGGER.info("etapa=visualizacao")
    graficos = gerar_graficos(limpo, configuracao.pasta_resultados)
    LOGGER.info("etapa=relatorio")
    gerar_relatorio(
        bruto, limpo, invalidos, removidos, qualidade, tabelas, tabelas_iniciais,
        delta_periodo, graficos, configuracao.arquivo_relatorio
    )
    print(f"Relatório: {configuracao.arquivo_relatorio}")
    print(f"Registros: {len(bruto)} -> {len(limpo)}")
    print(f"Resultados: {configuracao.pasta_resultados}")
    LOGGER.info("fim | status=sucesso | registros_brutos=%d | registros_tratados=%d", len(bruto), len(limpo))


if __name__ == "__main__":
    executar()
