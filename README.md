# Projeto Integrador — Paradas de Máquinas

Análise de dados das paradas de máquinas usando NumPy, Pandas, Matplotlib, Seaborn e Plotly.

## 1. Pré-requisitos

- Python 3.10 ou superior;
- acesso ao terminal PowerShell, CMD ou Bash;
- arquivo `projeto_integrador_paradas_maquinas.csv` na raiz do projeto.

## 2. Instalação das dependências

Abra o terminal na pasta do projeto:

```powershell
cd "C:\Users\Pichau\OneDrive\Documentos\projetos\paradas_maquinas"
```

Crie um ambiente virtual:

```powershell
python -m venv .venv
```

Ative o ambiente virtual no PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

No CMD, use:

```cmd
.venv\Scripts\activate.bat
```

Instale as bibliotecas:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

As dependências instaladas são:

- NumPy: operações numéricas;
- Pandas: leitura, tratamento, agrupamento e estatística;
- Matplotlib e Seaborn: gráficos estáticos;
- Plotly: gráfico interativo em HTML;
- python-docx: dependência disponível para uso futuro com documentos Word.

## 3. Executar a análise

Com o ambiente virtual ativado:

```powershell
python analise_paradas_maquinas.py
```

O script executa o pipeline completo:

1. carrega e padroniza o CSV;
2. calcula a disponibilidade;
3. diagnostica ausentes, duplicidades e valores inválidos;
4. limpa e valida os registros;
5. calcula média, mediana, mínimo, máximo, desvio padrão, quartis e IQR;
6. calcula correlações e analisa a evolução temporal;
7. identifica outliers sem removê-los automaticamente;
8. gera gráficos estáticos e interativos;
9. cria o relatório textual com as respostas do roteiro;
10. registra todas as etapas em log.

## 4. Atualizar o roteiro DOCX

Depois de executar a análise, atualize o roteiro com as respostas geradas:

```powershell
python preencher_roteiro_docx.py
```

Esse comando insere uma seção de respostas no final de `Roteiro_Projeto_Integrador_Paradas_Maquinas.docx`.

O arquivo original é preservado até que o comando seja executado. O script pode ser executado novamente para atualizar a seção de respostas.

## 5. Onde ficam os resultados

O relatório principal fica na raiz:

```text
respostas_projeto_integrador.txt
```

Os demais resultados ficam na pasta `resultados/`:

```text
resultados/
├── base_bruta_normalizada.csv
├── base_tratada.csv
├── diagnostico_qualidade.csv
├── diagnostico_invalidos.csv
├── removidos.csv
├── estatisticas_descritivas_numericas.csv
├── resumo_disponibilidade_por_linha.csv
├── resumo_disponibilidade_por_maquina.csv
├── resumo_disponibilidade_por_turno.csv
├── resumo_disponibilidade_linha_turno.csv
├── resumo_disponibilidade_maquina_turno.csv
├── correlacoes_com_tempo_parado.csv
├── matriz_correlacao.csv
├── tempo_parado_por_tipo_falha.csv
├── serie_diaria_por_linha.csv
├── outliers_disponibilidade.csv
├── 01_disponibilidade_tempo_linha.png
├── 02_heatmap_maquina_turno.png
├── 03_pareto_tipo_falha.png
├── 04_boxplot_vibracao_linha.png
├── 05_dispersao_vibracao_tempo_parado.png
├── 06_interativo_vibracao_tempo_parado.html
└── analise_paradas_maquinas.log
```

## 6. Conferir o log

O log mostra os valores calculados em cada etapa. Por exemplo:

```text
estatistica | tabela=linha | grupo=L2 | n=431 | media=86.43 | mediana=91.88 | minimo=16.67 | maximo=100.00 | desvio_padrao=17.19 | q1=82.71 | q3=100.00 | iqr=17.29
```

O log também informa registros ausentes, duplicidades, valores inválidos, correlações, outliers e gráficos criados.

## 7. Git

O arquivo `.gitignore` ignora materiais locais, ambientes virtuais, caches Python e a pasta `resultados/`, pois ela é gerada automaticamente pelo script.

Os arquivos principais do projeto permanecem disponíveis para versionamento:

- `analise_paradas_maquinas.py`;
- `preencher_roteiro_docx.py`;
- `requirements.txt`;
- `README.md`;
- dataset e relatório textual.
