"""Acrescenta as respostas geradas ao roteiro DOCX.

Usa apenas a biblioteca padrão para preservar o arquivo mesmo quando
python-docx não está disponível. O conteúdo respondido vem do relatório TXT
gerado por analise_paradas_maquinas.py.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


BASE = Path(__file__).resolve().parent
ARQUIVO_DOCX = BASE / "Roteiro_Projeto_Integrador_Paradas_Maquinas.docx"
ARQUIVO_RESPOSTAS = BASE / "respostas_projeto_integrador.txt"
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
Q = lambda nome: f"{{{NS_W}}}{nome}"

ET.register_namespace("w", NS_W)


def paragrafo(texto: str, estilo: str = "Normal") -> ET.Element:
    elemento = ET.Element(Q("p"))
    propriedades = ET.SubElement(elemento, Q("pPr"))
    estilo_elemento = ET.SubElement(propriedades, Q("pStyle"))
    estilo_elemento.set(Q("val"), estilo)
    run = ET.SubElement(elemento, Q("r"))
    texto_elemento = ET.SubElement(run, Q("t"))
    if texto[:1].isspace() or texto[-1:].isspace():
        texto_elemento.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    texto_elemento.text = texto
    return elemento


def quebra_de_pagina() -> ET.Element:
    elemento = ET.Element(Q("p"))
    run = ET.SubElement(elemento, Q("r"))
    ET.SubElement(run, Q("br"), {Q("type"): "page"})
    return elemento


def estilo_linha(linha: str) -> str:
    if linha.startswith(("PROJETO INTEGRADOR", "1. UNIDADE", "2. UNIDADE", "3. UNIDADE", "4. UNIDADE")):
        return "Heading1"
    if linha.startswith(("H1", "H2", "H3", "Respostas finais", "Mensagem central", "Storyboard")):
        return "Heading2"
    return "Normal"


def atualizar_docx() -> None:
    respostas = ARQUIVO_RESPOSTAS.read_text(encoding="utf-8").strip()
    with zipfile.ZipFile(ARQUIVO_DOCX, "r") as origem:
        document_xml = origem.read("word/document.xml")
        raiz = ET.fromstring(document_xml)
        corpo = raiz.find(Q("body"))
        if corpo is None:
            raise RuntimeError("document.xml não possui w:body")

        # Remove uma seção de respostas anterior, caso o script seja executado
        # novamente sobre o mesmo documento.
        marcadores = [
            "RESPOSTAS DA ANÁLISE DE PARADAS DE MÁQUINAS",
            "RESPOSTAS DA ANÁLISE DE PARADAS DE MÁQUINAS —",
        ]
        filhos = list(corpo)
        inicio = None
        for indice, filho in enumerate(filhos):
            texto = "".join(no.text or "" for no in filho.findall(f".//{Q('t')}"))
            if any(texto.startswith(marcador) for marcador in marcadores):
                inicio = indice
                break
        if inicio is not None:
            fim = len(filhos)
            for indice in range(inicio + 1, len(filhos)):
                if filhos[indice].tag == Q("sectPr"):
                    fim = indice
                    break
            for filho in filhos[inicio:fim]:
                corpo.remove(filho)

        secao = [
            quebra_de_pagina(),
            paragrafo("RESPOSTAS DA ANÁLISE DE PARADAS DE MÁQUINAS", "Heading1"),
            paragrafo("As respostas abaixo foram geradas a partir do dataset e inseridas no próprio roteiro.", "Normal"),
        ]
        secao.extend(paragrafo(linha, estilo_linha(linha)) for linha in respostas.splitlines())

        posicao = len(corpo)
        if posicao and corpo[posicao - 1].tag == Q("sectPr"):
            posicao -= 1
        for deslocamento, elemento in enumerate(secao):
            corpo.insert(posicao + deslocamento, elemento)

        novo_xml = ET.tostring(raiz, encoding="utf-8", xml_declaration=True)
        with tempfile.NamedTemporaryFile(prefix="roteiro_", suffix=".docx", dir=BASE, delete=False) as temporario:
            caminho_temporario = Path(temporario.name)

        try:
            with zipfile.ZipFile(caminho_temporario, "w", compression=zipfile.ZIP_DEFLATED) as destino:
                for item in origem.infolist():
                    conteudo = novo_xml if item.filename == "word/document.xml" else origem.read(item.filename)
                    destino.writestr(item, conteudo)
            # Fecha explicitamente o ZIP de origem antes de substituir o DOCX;
            # isso evita bloqueio de arquivo no Windows.
            origem.close()
            os.replace(caminho_temporario, ARQUIVO_DOCX)
        finally:
            caminho_temporario.unlink(missing_ok=True)


if __name__ == "__main__":
    atualizar_docx()
    print(f"Documento atualizado: {ARQUIVO_DOCX}")
