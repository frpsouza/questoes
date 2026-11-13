"""Extrai os metadados das questões das páginas do Qconcursos salvas no navegador.

Lê q/page-*.html (lista de questões filtrada, salva com Ctrl+S, já logado)
e grava q/questoes.json com, para cada questão: código, URL, disciplina,
assuntos, ano, banca, órgão e provas. Não acessa a internet.

Uso:  python q/extrair_metadados.py
"""
import html
import json
import re
from pathlib import Path

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "questoes.json"
BASE = "https://elite.qconcursos.com"


def texto(fragmento: str) -> list[str]:
    """HTML -> lista de pedaços de texto (um por nó de texto)."""
    f = re.sub(r"<(script|style|svg)\b[^>]*>.*?</\1>", "", fragmento, flags=re.S)
    f = f.replace("<!-- -->", "")
    pedacos = [html.unescape(p).strip() for p in re.split(r"<[^>]+>", f)]
    return [p for p in pedacos if p]


def campo(pedacos: list[str], rotulo: str) -> str | None:
    """Valor que segue o rótulo (ex.: 'Ano:'), no primeiro bloco de metadados."""
    for i, p in enumerate(pedacos):
        if p == rotulo and i + 1 < len(pedacos):
            return pedacos[i + 1]
    return None


def provas(pedacos: list[str]) -> list[str]:
    """Todas as provas listadas após 'Provas:' até o próximo rótulo."""
    i = next((i for i, p in enumerate(pedacos) if p in ("Provas:", "Prova:")), None)
    if i is None:
        return []
    out = []
    for p in pedacos[i + 1:]:
        if p in ("Ano:", "Banca:", "Órgão:", "Provas:", "Prova:", "Texto associado") or p.endswith("…"):
            break
        if p != ",":
            out.append(p)
    return out


def agrupar(pedacos: list[str], n: int) -> list[str]:
    """Junta os pedaços em exatamente n assuntos.

    Regras dos nomes do Qconcursos com vírgula: o grupo começa por um pedaço com ":"
    ("Acentuação Gráfica: Proparoxítonas") e termina em "… e X" ou "...". Entre as
    divisões possíveis, escolhe a que menos viola a regra do fim do grupo."""
    if len(pedacos) <= n:
        return pedacos
    melhor = (float("inf"), pedacos)

    def busca(i, grupos, custo):
        nonlocal melhor
        if custo >= melhor[0]:
            return
        if i == len(pedacos):
            if len(grupos) == n:
                melhor = (custo, [", ".join(g) for g in grupos])
            return
        if len(grupos) >= n:
            return
        for j in range(i + 1, len(pedacos) + 1):
            g = pedacos[i:j]
            if len(g) > 1 and (":" not in g[0] or any(":" in x for x in g[1:])):
                break
            c = 0 if len(g) == 1 or " e " in g[-1] or g[-1].endswith("...") else 1
            busca(j, grupos + [g], custo + c)

    busca(0, [], 0)
    return melhor[1]


def extrair(arquivo: Path) -> list[dict]:
    h = arquivo.read_text(encoding="utf-8")
    cartoes = re.split(r'data-e2e="question-item"', h)[1:]
    res = []
    for c in cartoes:
        m = re.search(r'<a href="(/questoes-de-concursos/questoes/[0-9a-f-]+)"[^>]*>Q(?:<!-- -->)?(\d{7})</a>', c)
        if not m:
            continue
        # breadcrumb: disciplina e assuntos
        bc = re.search(r'<nav data-slot="breadcrumb".*?</nav>', c, flags=re.S)
        itens = [p for p in texto(bc.group(0)) if p != ","] if bc else []
        p = texto(c)
        # a linha completa ("Português > A, B, C") inclui os assuntos recolhidos no botão "+N assuntos"
        completo = next((x for x in p if itens and x.startswith(itens[0] + " > ")), None)
        assuntos = [x for x in itens[1:] if not re.fullmatch(r"\d+ assuntos?", x)]
        if completo:
            resto = completo[len(itens[0]) + 3:]
            for a in assuntos:
                if resto.startswith(a):
                    resto = resto[len(a):].lstrip(", ")
            # assuntos ocultos: o botão diz quantos são ("2 assuntos"). Nomes podem ter vírgula
            # ("Acentuação Gráfica: Proparoxítonas, Paroxítonas, Oxítonas e Hiatos"), então separa
            # por ", " e junta os pedaços que seguem um nome com ":" até bater a contagem.
            cont = [re.fullmatch(r"(\d+) assuntos?", x) for x in itens]
            n = next((int(c_.group(1)) for c_ in cont if c_), None)
            pedacos = [x for x in re.split(r", (?=[A-ZÀ-Ú])", resto) if x]
            assuntos += agrupar(pedacos, n) if n else pedacos
        res.append({
            "codigo": f"Q{m.group(2)}",
            "url": BASE + m.group(1),
            "disciplina": itens[0] if itens else None,
            "assuntos": assuntos,
            "assuntos_texto": completo,
            "ano": int(a) if (a := campo(p, "Ano:")) and a.isdigit() else a,
            "banca": campo(p, "Banca:"),
            "orgao": campo(p, "Órgão:"),
            "provas": provas(p),
            "pagina": arquivo.name,
        })
    return res


def main():
    todas, vistos = [], set()
    for arq in sorted(PASTA.glob("page-*.html")):
        qs = extrair(arq)
        print(f"{arq.name}: {len(qs)} questões")
        for q in qs:
            if q["codigo"] not in vistos:
                vistos.add(q["codigo"])
                todas.append(q)
    SAIDA.write_text(json.dumps(todas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(todas)} questões únicas -> {SAIDA}")


if __name__ == "__main__":
    main()
