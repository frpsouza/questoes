"""Gera q/md/Q#######.md a partir das páginas do Qconcursos salvas (q/page-*.html).

Cada arquivo traz os metadados (de q/questoes.json), o texto associado, o
enunciado e as alternativas. O gabarito e o comentário do professor não vêm
na lista de questões: ficam numa seção para completar depois.

Requer pandoc. Não acessa a internet.
Imagens (textos publicados como figura) ficam como link para o endereço original.

Uso:  python q/gerar_md.py   (antes: python q/extrair_metadados.py)
"""
import html
import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

PASTA = Path(__file__).resolve().parent
SAIDA = PASTA / "md"
VAZIOS = {"br", "img", "input", "hr", "meta", "link", "source", "wbr"}


# ------------------------------------------------------------ árvore HTML --

class No:
    def __init__(self, tag, attrs=None, pai=None):
        self.tag, self.attrs, self.pai, self.filhos = tag, dict(attrs or []), pai, []

    def elementos(self):
        return [f for f in self.filhos if isinstance(f, No)]

    def busca(self, cond):
        for f in self.elementos():
            if cond(f):
                yield f
            yield from f.busca(cond)


class Arvore(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.raiz = self.atual = No("raiz")

    def handle_starttag(self, tag, attrs):
        n = No(tag, attrs, self.atual)
        self.atual.filhos.append(n)
        if tag not in VAZIOS:
            self.atual = n

    def handle_startendtag(self, tag, attrs):
        self.atual.filhos.append(No(tag, attrs, self.atual))

    def handle_endtag(self, tag):
        n = self.atual
        while n is not None and n.tag != tag:
            n = n.pai
        if n is not None and n.pai is not None:
            self.atual = n.pai

    def handle_data(self, data):
        self.atual.filhos.append(data)


def arvore(fragmento: str) -> No:
    p = Arvore()
    p.feed(re.sub(r"<(script|style|svg)\b[^>]*>.*?</\1>", "", fragmento, flags=re.S))
    return p.raiz


def para_html(n) -> str:
    """Serializa só o essencial; negrito/itálico por estilo viram <strong>/<em>."""
    if isinstance(n, str):
        return html.escape(n, quote=False)
    dentro = "".join(para_html(f) for f in n.filhos)
    est = n.attrs.get("style", "")
    if n.tag == "img":
        return f'<img src="{html.escape(n.attrs.get("src", ""))}" alt="">'
    if n.tag == "br":
        return "<br>"
    if n.tag == "span" and "bold" in est:
        return f"<strong>{dentro}</strong>"
    if n.tag == "span" and "italic" in est:
        return f"<em>{dentro}</em>"
    if n.tag in ("p", "strong", "b", "em", "i", "u", "sub", "sup", "ul", "ol", "li",
                 "table", "thead", "tbody", "tr", "td", "th", "blockquote"):
        return f"<{n.tag}>{dentro}</{n.tag}>"
    return dentro


def md(fragmento_html: str) -> str:
    r = subprocess.run(["pandoc", "-f", "html", "-t", "gfm-raw_html", "--wrap=none"],
                       input=fragmento_html.encode("utf-8"), capture_output=True, check=True)
    t = r.stdout.decode("utf-8")
    t = t.replace("\r\n", "\n").replace(" ", " ")
    t = re.sub(r"(?m)^[ \t]+$", "", t)                   # linhas só com espaços (<p><br></p>)
    t = re.sub(r"\*\*(\S[^*]*?)\s+\*\*", r"**\1**", t)    # "**texto **" -> "**texto**"
    t = re.sub(r"\*\*[ \t]*\n\*\*(?=\n|$)", "", t)            # negrito vazio ("**  \n**")
    t = re.sub(r"(?m)^[ \t]+(?=!\[)", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return re.sub(r"(?m)^\\$\n?", "", t).strip()



# --------------------------------------------------------------- questões --

def questoes_da_pagina(arquivo: Path) -> dict[str, dict]:
    h = arquivo.read_text(encoding="utf-8")
    res = {}
    for c in re.split(r'data-e2e="question-item"', h)[1:]:
        m = re.search(r">Q(?:<!-- -->)?(\d{7})</a>", c)
        if not m:
            continue
        raiz = arvore(c)
        fs = next(raiz.busca(lambda n: n.tag == "fieldset"), None)
        if fs is None:
            continue
        pai = fs.pai
        # enunciado: irmãos anteriores ao fieldset
        irmaos = pai.elementos()
        enun = "".join(para_html(x) for x in irmaos[:irmaos.index(fs)])
        # texto associado: irmão anterior do pai, se houver o botão "Texto associado"
        texto = ""
        if "Texto associado" in c and pai.pai is not None:
            tios = pai.pai.elementos()
            i = tios.index(pai)
            if i > 0:
                texto = para_html(tios[i - 1])
        alts = []
        for lab in fs.busca(lambda n: n.tag == "label" and n.attrs.get("data-e2e") == "question-alternative"):
            spans = list(lab.busca(lambda n: n.tag == "span"))
            corpo = spans[-1] if spans else lab
            alts.append((lab.attrs.get("data-label", "?"), md(para_html(corpo)).replace("\n\n", " ")))
        res["Q" + m.group(1)] = {"texto": md(texto) if texto else "", "enunciado": md(enun), "alternativas": alts}
    return res


def main():
    meta = {q["codigo"]: q for q in json.loads((PASTA / "questoes.json").read_text(encoding="utf-8"))}
    SAIDA.mkdir(exist_ok=True)
    conteudo = {}
    for arq in sorted(PASTA.glob("page-*.html")):
        conteudo.update(questoes_da_pagina(arq))
    n = 0
    for cod, q in meta.items():
        c = conteudo.get(cod)
        if not c:
            print(f"{cod}: conteúdo não encontrado nas páginas salvas")
            continue
        linhas = [
            f"# {cod}", "",
            f"- **URL:** {q['url']}",
            f"- **Assuntos:** {q['assuntos_texto']}",
            f"- **Ano:** {q['ano']}",
            f"- **Banca:** {q['banca']}",
            f"- **Órgão:** {q['orgao']}",
            f"- **Provas:** {'; '.join(q['provas'])}", "",
        ]
        if c["texto"]:
            linhas += ["## Texto associado", "", c["texto"], ""]
        linhas += ["## Enunciado", "", c["enunciado"], "", "## Alternativas", ""]
        linhas += [f"- **{l})** {t}" for l, t in c["alternativas"]]
        linhas += ["", "## Gabarito comentado", "", "*(a completar)*", ""]
        (SAIDA / f"{cod}.md").write_text("\n".join(linhas), encoding="utf-8")
        n += 1
    print(f"{n} arquivos em {SAIDA}")


if __name__ == "__main__":
    main()
