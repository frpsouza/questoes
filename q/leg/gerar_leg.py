"""Gera as questões de Legislação com gabarito comentado a partir de q/leg/dump.json.

dump.json é gravado pelo navegador (lista do filtro de q/filtro-legislacao.md, com a aba
"Gabarito Comentado" de cada questão aberta): {código: {page, href, html, comentado}}.

Saída (não acessa a internet):
  q/leg/questoes.json   metadados + gabarito de cada questão
  q/leg/md/Q#######.md  enunciado, alternativas e gabarito comentado

Requer pandoc.   Uso:  python q/leg/gerar_leg.py
"""
import html
import json
import re
import subprocess
from pathlib import Path

PASTA = Path(__file__).resolve().parent
BASE = "https://elite.qconcursos.com"
ROTULOS = ("Análise das alternativas", "Pegadinha da questão", "Dica para questões semelhantes")


def md(fragmento: str) -> str:
    r = subprocess.run(["pandoc", "-f", "html", "-t", "gfm-raw_html", "--wrap=none"],
                       input=fragmento.encode("utf-8"), capture_output=True, check=True)
    t = r.stdout.decode("utf-8").replace("\r\n", "\n").replace(" ", " ")
    t = re.sub(r"(?m)^[ \t]+$", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return re.sub(r"(?m)^\\$\n?", "", t).strip()


def texto(fr: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fr)).split())


def dd(h: str, rotulo: str) -> str:
    m = re.search(rf"<dt>{rotulo}:?</dt><dd>(.*?)</dd>", h)
    return texto(m.group(1)) if m else ""


def estilo(h: str) -> str:
    """Marcas de estilo gravadas pelo navegador (data-b/data-i) -> <strong>/<em>."""
    h = re.sub(r'<span data-b="1">(.*?)</span>', r"<strong>\1</strong>", h)
    h = re.sub(r'<span data-i="1">(.*?)</span>', r"<em>\1</em>", h)
    return h.replace('data-i="1"', "")


def comentario(h: str) -> tuple[str, str, str]:
    """(gabarito, autor, markdown do comentário)."""
    i = h.find('data-e2e="belt-commentary-body"')
    if i < 0:
        return "", "", ""
    corpo = h[h.find(">", i) + 1:]
    fim = corpo.find("<h4>O que achou desse gabarito?")
    corpo = corpo[:fim] if fim > 0 else corpo
    autor = re.search(r"<span>Autor: </span><span>(.*?)</span>", h)
    gab = re.search(r"<h3>Gabarito: ([A-E]|Certo|Errado)</h3>", corpo)
    corpo = re.sub(r"<h3>Gabarito: [^<]*</h3>", "", corpo, count=1)
    # cada alternativa: <div><div>A</div><div><div>Errada</div><div>TEXTO</div></div></div>
    corpo = re.sub(r"<div><div>([A-E])</div><div><div>(Certa|Errada|Correta|Incorreta)</div><div>(.*?)</div></div></div>",
                   r"<p><strong>\1) \2.</strong> \3</p>", corpo, flags=re.S)
    for r in ROTULOS:
        corpo = corpo.replace(f"<div>{r}</div>", f"<h4>{r}</h4>")
    corpo = corpo.replace("<strong>Tema central:</strong>", "<p><strong>Tema central:</strong>")
    return (gab.group(1) if gab else ""), (texto(autor.group(1)) if autor else ""), md(estilo(corpo))


def questao(cod: str, q: dict) -> dict:
    h = q["html"]
    bc = re.search(r'<nav data-slot="breadcrumb".*?</nav>', h, flags=re.S)
    itens = [texto(x) for x in re.findall(r"<a[^>]*>(.*?)</a>", bc.group(0))] if bc else []
    ini = h.find('<div role="none" data-slot="separator"></div>')
    fs = h.find("<fieldset>")
    enun = md(estilo(h[ini:fs])) if 0 <= ini < fs else ""
    alts = []
    for letra, corpo in re.findall(r'data-label="([A-E])"><span></span><div><span>[A-E]</span><span>(.*?)</span></div></label>', h, flags=re.S):
        alts.append((letra, md(estilo(corpo)).replace("\n\n", " ")))
    gab, autor, com = comentario(h)
    return {
        "codigo": cod, "url": BASE + q["href"], "pagina": int(q["page"]),
        "disciplina": itens[0] if itens else "", "assuntos": itens[1:],
        "ano": int(a) if (a := dd(h, "Ano")).isdigit() else a,
        "banca": dd(h, "Banca"), "orgao": dd(h, "Órgão"), "prova": dd(h, "Provas?"),
        "enunciado": enun, "alternativas": alts, "gabarito": gab, "autor": autor, "comentario": com,
    }


def main():
    dump = json.loads((PASTA / "dump.json").read_text(encoding="utf-8"))
    qs = [questao(c, q) for c, q in dump.items()]
    qs.sort(key=lambda q: (q["pagina"], q["codigo"]))
    (PASTA / "questoes.json").write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding="utf-8")
    saida = PASTA / "md"
    saida.mkdir(exist_ok=True)
    for q in qs:
        l = [f"# {q['codigo']}", "",
             f"- **URL:** {q['url']}",
             f"- **Assuntos:** {q['disciplina']} > {', '.join(q['assuntos'])}",
             f"- **Ano:** {q['ano']}", f"- **Banca:** {q['banca']}", f"- **Órgão:** {q['orgao']}",
             f"- **Prova:** {q['prova']}", "", "## Enunciado", "", q["enunciado"], "", "## Alternativas", ""]
        l += [f"- **{a})** {t}" for a, t in q["alternativas"]]
        l += ["", "## Gabarito comentado", ""]
        if q["comentario"]:
            l += [f"**Gabarito: {q['gabarito']}**" + (f" · Autor: {q['autor']}, Professor Qconcursos" if q["autor"] else ""),
                  "", q["comentario"]]
        else:
            l += ["*(sem gabarito comentado no Qconcursos)*"]
        (saida / f"{q['codigo']}.md").write_text("\n".join(l) + "\n", encoding="utf-8")
    sem = [q["codigo"] for q in qs if not q["comentario"]]
    print(f"{len(qs)} questões · {len(qs) - len(sem)} com gabarito comentado · sem: {', '.join(sem) or '—'}")


if __name__ == "__main__":
    main()
