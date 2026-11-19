"""Base de dados artigo de lei -> questões, a partir dos gabaritos comentados.

Lê q/leg/questoes.json (gerado por gerar_leg.py) e procura, em cada comentário, as citações
de artigos ("Lei nº 8.069/1990, art. 98, caput", "art. 136, I, do ECA", "arts. 205 e 206 da CF").
A lei de cada artigo é a citada junto dele; sem isso, a última lei citada antes no comentário;
sem isso, a lei principal da questão.

As questões sem gabarito comentado têm análise feita à mão em q/leg/analises.json (lei, artigo,
alternativa, explicação e, quando a questão reproduz o artigo, o texto da questão e o texto legal
para o destaque das diferenças); entram na base com papel "Análise própria".

Saída (não acessa a internet):
  q/leg/artigos.json   [{lei, nome, arquivo, art, questoes: [{codigo, papel, detalhe, trecho}]}]
  q/leg/artigos.md     a mesma base, legível: lei > artigo > questões com o trecho do comentário

Uso:  python q/leg/artigos.py
"""
import json
import re
from pathlib import Path

PASTA = Path(__file__).resolve().parent

# (id, nome, arquivo em legislacao/md ou None, regex das formas de citação)
LEIS = [
    ("ECA", "ECA — Lei nº 8.069/1990", "lei8069-eca.md",
     r"Lei n[ºo°]\s*8\.069(?:/1990|/90)?|\bECA\b|Estatuto da Criança e do Adolescente"),
    ("LDB", "LDB — Lei nº 9.394/1996", "lei9394-ldb.md",
     r"Lei n[ºo°]\s*9\.394(?:/1996|/96)?|\bLDB(?:EN)?\b|Lei de Diretrizes e Bases"),
    ("LBI", "LBI — Lei nº 13.146/2015", "lei13146-lbi.md",
     r"Lei n[ºo°]\s*13\.146(?:/2015)?|\bLBI\b|Estatuto da Pessoa com Deficiência|Lei Brasileira de Inclusão"),
    ("LGPD", "LGPD — Lei nº 13.709/2018", "lei13709-lgpd-compilada.md",
     r"Lei n[ºo°]\s*13\.709(?:/2018)?|\bLGPD\b|Lei Geral de Proteção de Dados"),
    ("EIR", "Estatuto da Igualdade Racial — Lei nº 12.288/2010", "lei12288-estatuto-igualdade-racial.md",
     r"Lei n[ºo°]\s*12\.288(?:/2010)?|Estatuto da Igualdade Racial"),
    ("CF", "Constituição Federal de 1988", "cf88.md",
     r"Constituição(?: Federal)?(?: de 1988)?|\bCF(?:/88|/1988)?\b"),
    ("PNED", "Lei nº 14.533/2023 — Educação Digital", "lei14533-educacao-digital.md", r"Lei n[ºo°]\s*14\.533(?:/2023)?"),
    ("SINASE", "Lei nº 12.594/2012 — SINASE", None, r"Lei n[ºo°]\s*12\.594(?:/2012)?|Lei do SINASE|\bSINASE\b"),
    ("L13431", "Lei nº 13.431/2017 — Escuta protegida", None, r"Lei n[ºo°]\s*13\.431(?:/2017)?"),
    ("L14176", "Lei nº 14.176/2021", None, r"Lei n[ºo°]\s*14\.176(?:/2021)?"),
    ("D5296", "Decreto nº 5.296/2004 — Acessibilidade", None, r"Decreto n[ºo°]\s*5\.296(?:/2004)?"),
    ("LOM", "Lei Orgânica municipal", None, r"Lei Orgânica(?: de [A-ZÀ-Ú][\wÀ-ú ]+?)?(?= |,|\.|$)"),
    ("OUTRA", "Outra norma", None,
     r"Lei Complementar n[ºo°]\s*[\d.]+/\d{4}|Lei n[ºo°]\s*[\d.]+/\d{4}|Decreto n[ºo°]\s*[\d.]+/\d{4}|Resolução CNE/CEB n[ºo°]\s*\d+/\d{4}"),
]
RE_LEI = re.compile("|".join(f"(?P<{i}>{r})" for i, _, _, r in LEIS))
NOME = {i: n for i, n, _, _ in LEIS}
ARQ = {i: a for i, _, a, _ in LEIS}
# lei principal de cada seção da apostila (ver _secao_leg em apostilas/gerar_orientador.py)
PADRAO = {"Criança e do Adolescente": "ECA", "Pessoa com Deficiência": "LBI", "13.709": "LGPD",
          "12.288": "EIR", "9.394": "LDB", "BNCC": "LDB", "Direito Constitucional": "CF"}

NUM = r"\d{1,3}(?:\.\d{3})?(?:\s*[º°o](?![a-zà-ú]))?(?:-[A-Z]{1,2}\b)?"
# "art. 98", "arts. 205 e 206", "arts. 58 a 60", "arts. 4º, 5º e 6º"
RE_ART = re.compile(rf"\b[Aa]rts?\.\s*(?P<nums>{NUM}(?:\s*(?:,|e|a|ao)\s*{NUM})*)")
# complemento do dispositivo logo após o número: ", caput", ", I", ", § 2º", ", parágrafo único, X", ", inciso IV"
RE_DET = re.compile(r"^((?:,?\s*(?:caput|§\s*\d+\s*[º°]?|parágrafo único|inciso\s+[IVXLC]+|[IVXLC]+\b|alínea\s+“?[a-z]”?|[a-z]\)))+)")
RE_LIGA = re.compile(r"^,?\s*(?:d[aoe]s?|na|no|desta|dessa|da mesma)\s+")


def numero(s: str) -> str:
    s = re.sub(r"\s+", "", s).replace("°", "º")
    m = re.match(r"(\d{1,3}(?:\.\d{3})?)º?o?(-[A-Z]{1,2})?$", s)
    return (m.group(1).replace(".", "") + (m.group(2) or "")) if m else s


def expandir(nums: str) -> list[str]:
    partes = re.split(r"\s*(,|\be\b|\ba\b|\bao\b)\s*", nums)
    vals, ops = partes[0::2], partes[1::2]
    out = [numero(vals[0])]
    for op, v in zip(ops, vals[1:]):
        v = numero(v)
        if op in ("a", "ao") and out[-1].isdigit() and v.isdigit() and 0 < int(v) - int(out[-1]) <= 6:
            out += [str(n) for n in range(int(out[-1]) + 1, int(v) + 1)]
        else:
            out.append(v)
    return [x for x in out if re.match(r"\d", x)]


def lei_padrao(q) -> str:
    alvo = q["disciplina"] + " " + " ".join(q["assuntos"])
    if "Lei Orgânica" in q["enunciado"]:
        return "LOM"
    return next((v for k, v in PADRAO.items() if k in alvo), "LDB")


def segmentos(q):
    """(papel, texto) de cada parágrafo do comentário."""
    papel = "Fundamento decisivo"
    for par in re.split(r"\n\s*\n", q["comentario"]):
        t = par.strip()
        if not t:
            continue
        m = re.match(r"\*\*([A-E])\) (Certa|Errada|Correta|Incorreta)\.\*\*\s*", t)
        if m:
            yield f"Alternativa {m.group(1)} ({m.group(2).lower()})", t[m.end():]
            continue
        h = re.match(r"#{1,6}\s*(.+)", t)
        if h:
            papel = {"Análise das alternativas": "Análise", "Pegadinha da questão": "Pegadinha",
                     "Dica para questões semelhantes": "Dica"}.get(h.group(1).strip(), h.group(1).strip())
            continue
        if t.startswith("**Tema central:**"):
            continue
        if papel == "Dica":
            for li in re.split(r"(?m)^- ", t):
                if li.strip():
                    yield "Dica", li.strip()
        else:
            yield papel, re.sub(r"^\*\*Fundamento decisivo:\*\*\s*", "", t)


def citacoes(q):
    """[(lei, art, detalhe, papel, trecho)] — uma por artigo citado em cada parágrafo."""
    padrao = lei_padrao(q)
    ultima = None   # lei citada por último no comentário (vale para "o art. 24" logo adiante)
    res = []
    for papel, texto in segmentos(q):
        # citações literais da lei ("Art. 17. O direito…") não contam como citação do comentarista
        t = re.sub(r"“[^”]*”|\"[^\"]*\"", lambda m: " " * len(m.group(0)), texto)
        leis = [(m.start(), m.end(), m.lastgroup) for m in RE_LEI.finditer(t)]
        ultima_par = None
        for m in RE_ART.finditer(t):
            resto = t[m.end():]
            d = RE_DET.match(resto)
            det = d.group(1).strip(" ,") if d else ""
            depois = resto[d.end() if d else 0:]
            lei = None
            lg = RE_LIGA.match(depois)
            if lg:   # "art. 136, I, do ECA"
                ml = RE_LEI.match(depois[lg.end():])
                if ml:
                    lei = ml.lastgroup
                elif "mesma" in lg.group(0):
                    lei = ultima
            if lei is None:
                antes = [l for l in leis if l[1] <= m.start()]
                if antes and m.start() - antes[-1][1] <= 25:      # "Lei nº 8.069/1990, art. 98"
                    lei = antes[-1][2]
                elif ultima_par:                                   # mesmo parágrafo: segue a lei do artigo anterior
                    lei = ultima_par
                else:                                              # lei citada antes no parágrafo ou no comentário
                    lei = antes[-1][2] if antes else (ultima or padrao)
            ultima_par = lei
            for n in expandir(m.group("nums")):
                res.append((lei, n, det, papel, texto))
            ultima = lei
        if leis and not list(RE_ART.finditer(t)):
            ultima = leis[-1][2]
    return res


def chave_art(a: str):
    n, _, suf = a.partition("-")
    return (int(n), suf)


def main():
    qs = json.loads((PASTA / "questoes.json").read_text(encoding="utf-8"))
    base = {}
    # questões sem gabarito comentado, analisadas à mão (q/leg/analises.json): cada item já traz lei e artigo
    an_path = PASTA / "analises.json"
    analises = json.loads(an_path.read_text(encoding="utf-8")) if an_path.exists() else []
    for a in analises:
        for it in a["itens"]:
            e = base.setdefault((it["lei"], it["art"]), {"lei": it["lei"], "nome": NOME[it["lei"]], "arquivo": ARQ[it["lei"]],
                                                         "art": it["art"], "questoes": []})
            e["questoes"].append({"codigo": a["codigo"], "papel": "Análise própria", "detalhe": it["detalhe"],
                                  "trecho": f"{it['alt']}: {it['veredito']}. {it['explicacao']}",
                                  "questao": it.get("questao", ""), "lei_texto": it.get("lei_texto", ""),
                                  "alteracao": a.get("alteracao", ""), "recente": a.get("recente", False)})
    analisadas = {a["codigo"] for a in analises}
    for q in qs:
        if q["codigo"] in analisadas:
            continue
        vistos = set()
        for lei, art, det, papel, trecho in citacoes(q):
            if (lei, art, papel, trecho) in vistos:
                continue
            vistos.add((lei, art, papel, trecho))
            e = base.setdefault((lei, art), {"lei": lei, "nome": NOME[lei], "arquivo": ARQ[lei], "art": art, "questoes": []})
            e["questoes"].append({"codigo": q["codigo"], "papel": papel, "detalhe": det, "trecho": trecho})
    ordem = {i: n for n, (i, *_) in enumerate(LEIS)}
    lista = sorted(base.values(), key=lambda e: (ordem[e["lei"]], chave_art(e["art"])))
    (PASTA / "artigos.json").write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")

    l = ["# Artigos de lei cobrados nas questões da Legalle (gabaritos comentados)", "",
         f"{len(lista)} artigos · {len(qs)} questões. Gerado por `q/leg/artigos.py` a partir de `q/leg/questoes.json`.", ""]
    lei_atual = None
    for e in lista:
        if e["lei"] != lei_atual:
            lei_atual = e["lei"]
            l += [f"## {e['nome']}", ""]
        cods = sorted({x["codigo"] for x in e["questoes"]})
        l += [f"### Art. {e['art']} — {len(cods)} {'questão' if len(cods) == 1 else 'questões'}", ""]
        for x in e["questoes"]:
            det = f" ({x['detalhe']})" if x["detalhe"] else ""
            l += [f"- **[{x['codigo']}](md/{x['codigo']}.md)** · {x['papel']}{det}: {x['trecho']}", ""]
    (PASTA / "artigos.md").write_text("\n".join(l), encoding="utf-8")
    sem = [q["codigo"] for q in qs if q["comentario"] and not citacoes(q)]
    print(f"{len(lista)} artigos; {len(analises)} questões com análise própria; questões sem artigo citado: {', '.join(sem) or '—'}")


if __name__ == "__main__":
    main()
