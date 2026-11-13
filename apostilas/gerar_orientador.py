"""Gera apostilas/orientador-educacional.html.

Os artigos de lei são extraídos *ipsis litteris* dos textos oficiais em
legislacao/md/ (convertidos de Planalto, AL-RS, MEC e CEEd-RS). Redações
revogadas (texto riscado nas versões compiladas) são omitidas, e fica só a
redação vigente com as notas de alteração ("Redação dada pela...").

Uso:  python apostilas/gerar_orientador.py
"""
import difflib
import html
import json
import re
import subprocess
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MD = RAIZ / "legislacao" / "md"
SAIDA = RAIZ / "apostilas" / "orientador-educacional.html"

# ---------------------------------------------------------------- extração --

RE_ART = re.compile(r"^Art\.\s*(\d+(?:\.\d+)?)(?:\s*(?:º|°|o\b))?(-[A-Z]{1,2}\b)?")
RE_HEAD = re.compile(r"^(T[ÍI]TULO|CAP[ÍI]TULO|Cap[íi]tulo|SE[ÇC][ÃA]O|Se[çc][ãa]o|SUBSE[ÇC][ÃA]O|Subse[çc][ãa]o|LIVRO|PARTE)\b")
RE_RUIDO = re.compile(r"^(https?://www\.al\.rs\.gov\.br\S*|\**Resolução CEEd nº 365/2021\s*[–-]\s*fl\.\s*\d+\**|\d{1,3}|#?\s*ESTADO DO RIO GRANDE DO SUL ASSEMBLEIA LEGISLATIVA.*)$")
RE_NOTA = re.compile(
    r"\((?:Redação dada|Incluíd[oa]|Acrescid[oa]|Vide|Vigência|Revogad[oa]|Renumerad[oa]|Produção de efeito|Regulamento|"
    r"Regulamenta|Promulgação|Expressão|Parágrafo|Inciso|Alínea|Artigo|Texto|Vetado|VETADO)[^()]*(?:\([^()]*\)[^()]*)*\)"
)

_cache: dict[str, list[str]] = {}
_antes: dict[str, dict[int, list[str]]] = {}   # arquivo -> {índice do bloco: [redações anteriores, da mais antiga à mais recente]}

ANO_LIMITE = date.today().year - 10   # só alterações dos últimos 10 anos recebem destaque (diff, redação anterior)
ANO_RECENTE = 2023          # alterações a partir deste ano recebem destaque "potencial de prova"
RE_ROTULO = re.compile(r"^(Art\.\s*\d+(?:\.\d+)?\s*(?:º|°|o\b)?(?:-[A-Z]{1,2}\b)?|§\s*\d+\s*(?:º|°|o\b)?|Parágrafo único|[IVXLC]+(?=\s*[-–])|[a-z](?=\)))")
RE_ALTERADOR = re.compile(
    r"(Redação dada|Incluíd[oa]|Acrescid[oa]|Revogad[oa]|Renumerad[oa])\s+(?:pel[oa]s?|por)\s+"
    r"((?:Lei(?: Complementar)?|Emenda Constitucional|Medida Provisória|Decreto(?:-Lei)?)\s*n[ºo°]?\s*[\d.\-]+)"
    r"(?:,\s*de\s*(?:\d{1,2}\.\d{1,2}\.)?(\d{4}))?"
)


def rotulo(t: str):
    m = RE_ROTULO.match(t.replace("*", "").strip())
    return re.sub(r"[\s.º°]|o$", "", m.group(1)).lower() if m else None


def limpar(bloco: str) -> str:
    b = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", bloco)            # imagens
    b = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", b)             # links -> texto
    b = re.sub(r"<[^>]+>", "", b)                              # <u>, <br> etc.
    b = re.sub(r"(?m)^#{1,6}\s*", "", b)                       # "## CAPÍTULO I" (textos vindos de PDF)
    b = b.replace("^(o)", "º").replace("^(a)", "ª")
    b = "\n".join(l.strip() for l in b.splitlines()).strip()
    return "" if re.fullmatch(r"[\\*\s]*", b) else b


def blocos(arquivo: str) -> list[str]:
    if arquivo not in _cache:
        txt = (MD / arquivo).read_text(encoding="utf-8")
        out, antes, pend = [], {}, []
        for b in re.split(r"\n\s*\n", txt):
            b = "\n".join(l for l in b.splitlines() if not RE_RUIDO.match(l.strip()))
            # redação revogada (texto riscado nas versões compiladas): guarda como "versão anterior"
            if "~~" in b:
                velho = limpar(" ".join(re.findall(r"~~(.*?)~~", b, flags=re.S)).replace("~~", ""))
                resto = limpar(re.sub(r"~~.*?~~", "", b, flags=re.S))
                if len(re.sub(r"[^A-Za-zÀ-ú]", "", RE_NOTA.sub("", resto))) < 3:
                    # bloco só com texto antigo (+ a nota que lhe deu aquela redação)
                    if velho:
                        pend.append((velho + " " + resto).strip())
                    continue
                if velho:
                    pend.append(velho)
                b = resto
            b = limpar(b)
            if b and b != "[TABLE]":
                if pend:
                    r = rotulo(b)
                    casam = [p for p in pend if r and rotulo(p) == r]
                    if casam:
                        antes[len(out)] = casam
                    pend = []
                out.append(b)
        _cache[arquivo] = out
        _antes[arquivo] = antes
    return _cache[arquivo]


def chave(b: str):
    m = RE_ART.match(b.replace("*", "").strip())
    if not m:
        return None
    suf = (m.group(2) or "").replace("-", "").replace(" ", "")
    return (int(m.group(1).replace(".", "")), suf)


def k(s: str):
    n, _, suf = s.partition("-")
    return (int(n), suf)


def eh_titulo(b: str, anterior_titulo: bool) -> bool:
    t = b.replace("*", "").strip()
    if RE_HEAD.match(t):
        return True
    if not anterior_titulo or len(t) >= 160 or re.search(r"[.;:,]$", t):
        return False
    if re.match(r"^(Art\.|§|Parágrafo|[IVXLC]+\s*[-–]|[a-z]\))", t):
        return False
    return bool(re.sub(r"[^A-Za-zÀ-ú]", "", t))


def trecho(arquivo: str, ini: str, fim: str | None = None, titulos_antes=True) -> list[tuple[str, str]]:
    """Blocos do art. `ini` ao art. `fim` (inclusive), com títulos/capítulos intermediários.
    Retorna lista de (tipo, texto) com tipo em {'tit', 'txt'}."""
    bl = blocos(arquivo)
    ki, kf = k(ini), k(fim or ini)
    i0 = next((i for i, b in enumerate(bl) if chave(b) == ki), None)
    if i0 is None:
        raise ValueError(f"{arquivo}: art. {ini} não encontrado")
    # títulos imediatamente anteriores (ex.: "Seção I / DA EDUCAÇÃO")
    j = i0
    if titulos_antes:
        while j > 0 and chave(bl[j - 1]) is None and (RE_HEAD.match(bl[j - 1].replace("*", "").strip()) or eh_titulo(bl[j - 1], True)) and len(bl[j - 1]) < 160:
            j -= 1
        # só aceita o recuo se ele começar num cabeçalho estrutural (TÍTULO, CAPÍTULO, Seção...)
        while j < i0 and not RE_HEAD.match(bl[j].replace("*", "").strip()):
            j += 1
    res, ant_tit = [], False
    av = _antes[arquivo]
    for i in range(j, len(bl)):
        b = bl[i]
        c = chave(b)
        if c is not None and c > kf:
            break
        t = c is None and eh_titulo(b, ant_tit or RE_HEAD.match(b.replace("*", "").strip()) is not None)
        res.append(("tit", b) if t else ("txt", b, av.get(i, [])))
        ant_tit = t
    def fim_titulo(b):
        t = b.replace("*", "").strip()
        return len(t) < 160 and not re.search(r"[.;:,)]$", t) and not re.match(r"^(Art\.|§|Parágrafo|[IVXLC]+\s*[-–]|[a-z]\))", t)
    while res and (res[-1][0] == "tit" or fim_titulo(res[-1][1])):   # títulos do próximo bloco
        res.pop()
    return res


def integral(arquivo: str) -> list[tuple[str, str]]:
    bl = blocos(arquivo)
    i0 = next(i for i, b in enumerate(bl) if chave(b) == (1, ""))
    while i0 > 0 and len(bl[i0 - 1]) < 160 and chave(bl[i0 - 1]) is None and eh_titulo(bl[i0 - 1], True):
        i0 -= 1
    res, ant, av = [], False, _antes[arquivo]
    for i in range(i0, len(bl)):
        b = bl[i]
        t = chave(b) is None and eh_titulo(b, ant)
        res.append(("tit", b) if t else ("txt", b, av.get(i, [])))
        ant = t
    return res


def linhas_entre(arquivo: str, inicio: str, fim_regex: str) -> str:
    txt = (MD / arquivo).read_text(encoding="utf-8")
    i = txt.index(inicio)
    m = re.compile(fim_regex, re.M).search(txt, i + len(inicio))
    return txt[i: m.start() if m else None]


# --------------------------------------------------------------- render md --

REGISTRO: list[dict] = []     # alterações recentes encontradas (lido por MAPA)
_n_alt = [0]


def esc(s: str) -> str:
    """Texto puro -> HTML seguro dentro de bloco HTML que o pandoc ainda lê como Markdown."""
    s = html.escape(re.sub(r"\s+", " ", s.replace("*", "")).strip())
    return re.sub(r"([\\`_\[\]#])", r"\\\1", s)


def alteradores(notas: str):
    return [(m.group(1), m.group(2).strip(), int(m.group(3)) if m.group(3) else None) for m in RE_ALTERADOR.finditer(notas)]


def diff(antigo: str, novo: str):
    """Diferença por palavras. Retorna (html_antigo_com_del, md_novo_com_add, acrescidos, suprimidos, semelhança)."""
    a, b = antigo.split(), novo.split()
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    h_old, m_new, add, rem = [], [], [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            h_old.append(esc(" ".join(a[i1:i2])))
            m_new.append(" ".join(b[j1:j2]))
            continue
        if i2 > i1:
            t = " ".join(a[i1:i2]); rem.append(t)
            h_old.append(f'<span class="del">{esc(t)}</span>')
        if j2 > j1:
            t = " ".join(b[j1:j2]); add.append(t)
            m_new.append(f'<span class="add">{" ".join(b[j1:j2])}</span>')
    return " ".join(h_old), " ".join(m_new), add, rem, sm.ratio()


def _curto(xs, n=3, lim=90):
    xs = [x.replace("*", "") for x in xs if re.search(r"[A-Za-zÀ-ú0-9]", x)]
    t = " … ".join(f"“{x if len(x) <= lim else x[:lim] + '…'}”" for x in xs[:n])
    return t + (" …" if len(xs) > n else "")


def md_lei(partes) -> str:
    out = []
    for p in partes:
        tipo, b = p[0], p[1]
        if tipo == "tit":
            out.append(f"::: tit\n{b.replace('*', '')}\n:::")
            continue
        olds = p[2] if len(p) > 2 else []
        notas = " ".join(RE_NOTA.findall(b))
        corpo = re.sub(r"[ \t]{2,}", " ", RE_NOTA.sub("", b)).strip()
        alts = [a for a in alteradores(notas) if a[0] != "Renumerado"]
        anos = [a[2] for a in alts if a[2]]
        ano = max(anos) if anos else None
        ref = next((f"{a[1]}/{a[2]}" if a[2] else a[1] for a in alts if a[2] == ano), None) if alts else None
        recente = bool(ano and ano >= ANO_RECENTE)
        no_periodo = ano is not None and ano >= ANO_LIMITE
        sem_texto = len(re.sub(r"[^A-Za-zÀ-ú]", "", RE_ROTULO.sub("", corpo.replace("*", ""), count=1))) < 3
        revogado = "(Revogad" in notas and sem_texto
        corpo_md, h_ant, coment = corpo, None, None
        if olds and no_periodo:
            ant = re.sub(r"[ \t]{2,}", " ", RE_NOTA.sub("", olds[-1])).strip()
            h_old, m_new, add, rem, sim = diff(ant, corpo)
            if revogado:
                coment = "dispositivo <strong>revogado</strong>; o texto que vigorava está abaixo."
                h_ant = esc(ant)
            elif sim >= 0.35:
                corpo_md, h_ant = m_new, h_old
                partes_c = []
                if add:
                    partes_c.append(f'<span class="add">acrescentou</span> {esc(_curto(add))}')
                if rem:
                    partes_c.append(f'<span class="del-l">suprimiu</span> {esc(_curto(rem))}')
                coment = "; ".join(partes_c) or "ajuste de redação (pontuação ou forma)."
            else:
                coment = "redação <strong>reformulada</strong> — compare com a versão anterior abaixo."
                h_ant = esc(ant)
        elif recente and alts and alts[0][0].startswith(("Incluíd", "Acrescid")) and not sem_texto:
            corpo_md = f'<span class="add">{corpo}</span>'
            coment = "dispositivo <strong>incluído</strong> — não existia na redação anterior."
        elif recente and revogado:
            coment = "dispositivo <strong>revogado</strong>."
        corpo_md = re.sub(r"^(<span class=\"add\">)?\*{0,2}(Art\.\s*[\d.]+(?:\s*(?:º|°|o\b))?(?:-[A-Z]{1,2}\b)?\.?)\*{0,2}",
                          lambda m: (m.group(1) or "") + f"**{m.group(2)}**", corpo_md)
        if notas:
            corpo_md += " " + " ".join(f"[{n}]{{.nota}}" for n in RE_NOTA.findall(b))
        if coment is None:
            out.append(corpo_md)
            continue
        _n_alt[0] += 1
        ident = f"alt-{_n_alt[0]}"
        if recente:
            REGISTRO.append({"id": ident, "ano": ano, "ref": ref,
                             "trecho": re.sub(r"\s+", " ", corpo.replace("*", ""))[:110]})
        selo = (f'<p class="selo"><span class="badge">Alteração recente · {ano} · potencial de prova</span></p>\n\n'
                if recente else "")
        h = [f'<p class="mudou"><strong>O que mudou{f" ({esc(ref)})" if ref else ""}:</strong> {coment}</p>']
        if h_ant is not None:
            h.append(f'<p><strong>Redação anterior:</strong> {h_ant}</p>')
            for velho in reversed(olds[:-1]):
                h.append(f'<p class="velha"><strong>Redação mais antiga:</strong> {esc(velho)}</p>')
        out.append(f"::: {{#{ident} .alt{' .recente' if recente else ''}}}\n{selo}{corpo_md}\n\n"
                   f'<div class="antes">{"".join(h)}</div>\n:::')
    return "\n\n".join(out)


def caixa_lei(titulo: str, fonte: str, partes, aberto=False, ident=None) -> str:
    idattr = f' id="{ident}"' if ident else ""
    op = " open" if aberto else ""
    return (
        f'\n\n<details class="lei"{idattr}{op}><summary>{html.escape(titulo)}</summary>\n\n'
        f'<p class="fonte">Fonte oficial: {fonte}</p>\n\n'
        f"{md_lei(partes)}\n\n</details>\n\n"
    )


PLANALTO = '<a href="{u}">planalto.gov.br</a> (texto compilado)'
U = {
    "cf88.md": "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    "clt-del5452.md": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452.htm",
    "lei12288-estatuto-igualdade-racial.md": "https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2010/lei/l12288.htm",
    "lei11340-maria-da-penha.md": "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11340.htm",
    "lei13146-lbi.md": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm",
    "lei13709-lgpd-compilada.md": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm",
    "lei9394-ldb.md": "https://www.planalto.gov.br/ccivil_03/leis/l9394.htm",
    "lei14533-educacao-digital.md": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/lei/l14533.htm",
    "lei14811-seguranca-escolar.md": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/l14811.htm",
    "dec12603-pnept.md": "https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/decreto/d12603.htm",
    "lei8069-eca.md": "https://www.planalto.gov.br/ccivil_03/leis/l8069.htm",
    "lei14254-dislexia-tdah.md": "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14254.htm",
}


def F(arq):
    if arq in U:
        return PLANALTO.format(u=U[arq])
    return {
        "rs-lei14498-pefs-liberato.md": '<a href="https://ww3.al.rs.gov.br/filerepository/repLegis/arquivos/LEI%2014.498.pdf">AL-RS / LEGIS</a> (texto original; tabelas extraídas de PDF, conferir no original)',
        "rs-lei13694-igualdade-racial-rs.md": '<a href="https://ww3.al.rs.gov.br/filerepository/repLegis/arquivos/13.694.pdf">AL-RS / LEGIS</a> (texto original)',
        "rs-dec52101-estatuto-liberato.md": '<a href="https://ww3.al.rs.gov.br/filerepository/repLegis/arquivos/DEC%2052.101.pdf">AL-RS / LEGIS</a>',
        "ceed-rs-resolucao-365-2021.md": '<a href="https://www.ceed.rs.gov.br/upload/arquivos/202112/20125528-resolucao-0365-2021.pdf">CEEd-RS</a> (extraído de PDF)',
        "bncc.md": '<a href="http://basenacionalcomum.mec.gov.br/images/BNCC_EI_EF_110518_versaofinal_site.pdf">MEC – BNCC</a>',
    }[arq]


def L(titulo, arq, *faixas, aberto=False, ident=None):
    """Caixa com um ou mais trechos: faixas = ("12","15"), ("24",) ..."""
    partes = []
    for f in faixas:
        partes += trecho(arq, *f)
    return caixa_lei(titulo, F(arq), partes, aberto, ident)


def LI(titulo, arq, ident=None):
    return caixa_lei(titulo, F(arq), integral(arq), ident=ident)


def topicos(*itens):
    return "\n".join(f"- {i}" for i in itens) + "\n"


# ------------------------------------------------------------- conteúdo --

QUESTOES_JSON = RAIZ / "q" / "questoes.json"

# assuntos do Qconcursos -> subtópicos do programa de Português (Anexo II)
GRUPOS_PT = {
    "pt-a1": ("Compreensão e interpretação", {"Noções Gerais de Compreensão e Interpretação de Texto",
              "Tipologia Textual", "Funções da Linguagem: emotiva, apelativa, referencial, metalinguística, fática e poética."}),
    "pt-a2": ("Efeitos de sentido e figuras de linguagem", {"Figuras de Linguagem", "Denotação e Conotação"}),
    "pt-a3": ("Coesão e coerência", {"Coesão e coerência", "Uso dos conectivos"}),
    "pt-b1": ("Significação e substituição de palavras e expressões", {
              "Significação Contextual de Palavras e Expressões. Sinônimos e Antônimos.", "Denotação e Conotação",
              "Redação - Reescritura de texto"}),
    "pt-b2": ("Estrutura e formação de palavras", {"Estrutura das Palavras: Radical, Desinência, Prefixo e Sufixo"}),
    "pt-c1": ("Ortografia e acentuação gráfica", {"Ortografia", "Acentuação Gráfica: Proparoxítonas, Paroxítonas, Oxítonas e Hiatos"}),
    "pt-c2": ("Relações entre fonemas e grafias", {"Fonologia", "Fonemas e Letras", "Encontros consonantais: Dígrafos", "Noções de Fonética"}),
    "pt-c3": ("Flexões e emprego das classes gramaticais", {"Morfologia", "Morfologia - Verbos", "Morfologia - Pronomes",
              "Pronomes demonstrativos", "Advérbios", "Adjetivos", "Funções morfossintáticas da palavra ATÉ"}),
    "pt-c4": ("Vozes verbais", {"Flexão de voz (ativa, passiva, reflexiva)"}),
    "pt-c5": ("Concordância nominal e verbal", {"Concordância verbal, Concordância nominal", "Concordância Verbal", "Concordância Nominal"}),
    "pt-c6": ("Regência e crase", {"Regência", "Crase"}),
    "pt-c7": ("Pontuação", {"Pontuação", "Uso dos dois-pontos", "Uso da vírgula"}),
    "pt-c8": ("Coordenação, subordinação e relações sintáticas", {"Sintaxe", "Análise sintática", "Uso dos conectivos",
              "Orações coordenadas sindéticas: Aditivas, Adversativas, Alternativas, Conclusivas...",
              "Orações subordinadas adverbiais: Causal, Comparativa, Consecutiva, Concessiva, Condicional...",
              "Vocativo e Termos Acessórios da Oração: Adjunto Adnominal, Diferença entre Adjunto Adnominal e Complemento Nominal, Adjunto Adverbial e Aposto"}),
}
# assunto genérico: só conta quando a questão não tem outro assunto mapeado
GENERICOS_PT = {"Interpretação de Textos": "pt-a1"}


def _questoes_pt():
    """{grupo: [questões]} a partir de q/questoes.json (metadados extraídos do Qconcursos)."""
    if not QUESTOES_JSON.exists():
        return {}, 0, set()
    qs = json.loads(QUESTOES_JSON.read_text(encoding="utf-8"))
    por = {g: [] for g in GRUPOS_PT}
    sem = set()
    for q in qs:
        gs = [g for g, (_, ass) in GRUPOS_PT.items() if ass & set(q["assuntos"])]
        if not gs:
            gs = [GENERICOS_PT[a] for a in q["assuntos"] if a in GENERICOS_PT][:1]
        if not gs:
            sem.add(q["codigo"])
        for g in gs:
            por[g].append(q)
    for g in por:
        por[g].sort(key=lambda q: (-(q["ano"] or 0), q["codigo"]))
    return por, len(qs), sem


QPT, NQPT, SEM_GRUPO_PT = _questoes_pt()


def QPT_BLOCO(grupo: str) -> str:
    """Lista de questões da Legalle do subtópico, com link para o Qconcursos."""
    titulo, _ = GRUPOS_PT[grupo]
    qs = QPT.get(grupo, [])
    if not qs:
        return (f'\n\n<p class="ref" id="{grupo}"><strong>{titulo}</strong> — nenhuma questão da Legalle '
                f'neste assunto na seleção atual.</p>\n\n')
    itens = []
    for q in qs:
        prova = q["provas"][0] if q["provas"] else ""
        cargo = prova.split(" - ")[-1] if prova else ""
        outros = ", ".join(a for a in q["assuntos"] if a not in GRUPOS_PT[grupo][1] and a not in GENERICOS_PT)
        itens.append(
            f'<li><a href="{html.escape(q["url"])}" target="_blank" rel="noopener">{q["codigo"]}</a> '
            f'· {q["ano"]} · {html.escape(q["orgao"] or "")} · {html.escape(cargo)}'
            + (f' <span class="nota">(também: {html.escape(outros)})</span>' if outros else "") + "</li>")
    return (f'\n\n<details class="questoes" id="{grupo}"><summary>{titulo} — {len(qs)} '
            f'{"questão" if len(qs) == 1 else "questões"} da Legalle</summary>\n'
            f'<ul>{"".join(itens)}</ul></details>\n\n')


def parte_portugues():
    resumo = (f'<p class="meta">Questões da Legalle no Qconcursos ({NQPT} de Português, nível superior), '
              'agrupadas pelos subtópicos do programa a partir dos assuntos indicados pelo próprio Qconcursos. '
              'Os links abrem a questão no Qconcursos (requer login). Uma questão com vários assuntos aparece em '
              'mais de um subtópico.</p>') if NQPT else ""
    return f"""
# Parte I — Língua Portuguesa {{#pt}}

<p class="meta">10 questões · 1,00 ponto cada · mínimo de 5 acertos</p>

{resumo}

## a) Leitura e compreensão de textos {{#pt-a}}

{topicos("Assunto, tema e tese; estruturação do texto (introdução, desenvolvimento, conclusão)",
"Ideias principais e secundárias; relação entre as ideias (causa, consequência, oposição, concessão, conclusão)",
"Efeitos de sentido; figuras de linguagem (metáfora, metonímia, ironia, eufemismo, hipérbole, antítese, paradoxo, personificação)",
"Recursos de argumentação (exemplificação, autoridade, dados, comparação, contra-argumentação)",
"Informações implícitas: pressupostos (marcados linguisticamente) × subentendidos (inferidos do contexto)",
"Coesão (referencial, sequencial, lexical) e coerência textual")}
{QPT_BLOCO("pt-a1")}{QPT_BLOCO("pt-a2")}{QPT_BLOCO("pt-a3")}

## b) Léxico {{#pt-b}}

{topicos("Significação de palavras e expressões no texto (sentido denotativo × conotativo)",
"Substituição de palavras e expressões mantendo sentido e correção",
"Estrutura e formação de palavras: radical, afixos, desinências; derivação e composição",
"Sinônimos, antônimos, parônimos e homônimos")}
{QPT_BLOCO("pt-b1")}{QPT_BLOCO("pt-b2")}

## c) Aspectos linguísticos {{#pt-c}}

{topicos("Relações morfossintáticas",
"Ortografia: emprego de letras e acentuação gráfica (Acordo Ortográfico vigente)",
"Relações entre fonemas e grafias",
"Flexões e emprego das classes gramaticais",
"Vozes verbais (ativa, passiva analítica, passiva sintética, reflexiva) e sua conversão",
"Concordância nominal e verbal",
"Regência nominal e verbal; acento indicativo de crase",
"Pontuação: regras e implicações de sentido",
"Coordenação e subordinação: conjunções, locuções conjuntivas e pronomes relativos")}
{"".join(QPT_BLOCO(g) for g in GRUPOS_PT if g.startswith("pt-c"))}
"""


PONTOS = {
    "esp-b": "Esp. b — prática pedagógica", "esp-c": "Esp. c — aprendizagem e competências",
    "esp-d": "Esp. d — orientação educacional", "esp-e": "Esp. e — desenvolvimento e identidades",
    "esp-f": "Esp. f — família, escola e conflitos", "esp-g": "Esp. g — inclusão e dificuldades",
    "esp-h": "Esp. h — trabalho e educação profissional", "esp-i": "Esp. i — gestão democrática e currículo",
    "esp-j": "Esp. j — avaliação e supervisão", "leg-j": "Leg. j — LDB", "leg-k": "Leg. k — PNEPT",
    "leg-l": "Leg. l — BNCC", "leg-m": "Leg. m — ECA", "leg-h": "Leg. h — LBI", "leg-e": "Leg. e — Igualdade Racial",
}


def MAPA(ident, nome, arq, itens):
    """Mapa tópico × dispositivos + uma seção por tópico com o trecho da lei logo abaixo.
    itens: (tópico, rótulo dos dispositivos, [faixas], [pontos do programa relacionados])"""
    linhas, secoes = [], []
    reg0 = len(REGISTRO)
    for n, (top, rot, faixas, rel) in enumerate(itens, 1):
        anc = f"{ident}-{n}"
        rel_html = " · ".join(f'<a href="#{r}">{PONTOS[r]}</a>' for r in rel) or "—"
        linhas.append(f'<tr><td><a href="#{anc}">{n}. {top}</a></td><td>{rot}</td><td>{rel_html}</td></tr>')
        partes = []
        for f in faixas:
            partes += trecho(arq, *f)
        secoes.append(
            f'\n\n<h3 id="{anc}">{n}\\. {top}</h3>\n\n<p class="arts">{rot}'
            + (f' · relacionado a: {rel_html}' if rel else "") + "</p>\n"
            + caixa_lei(f"{nome} — {rot}", F(arq), partes, aberto=True)
        )
    tabela = ('\n\n<table class="mapa"><caption>Mapa da lei por tópico</caption>'
              '<thead><tr><th>Tópico</th><th>Dispositivos</th><th>Pontos do programa</th></tr></thead><tbody>'
              + "".join(linhas) + "</tbody></table>\n\n")
    rec = REGISTRO[reg0:]
    if rec:
        tabela += (f'<div class="recentes"><p><strong>Alterações recentes nesta norma (desde {ANO_RECENTE}) — potencial de prova:</strong></p><ul>'
                   + "".join(f'<li><a href="#{r["id"]}">{esc(r["trecho"])}…</a> <span class="nota">({esc(r["ref"] or str(r["ano"]))})</span></li>' for r in rec)
                   + "</ul></div>\n\n")
    return tabela + "".join(secoes)


def parte_legislacao():
    s = """
# Parte II — Legislação {#leg}

<p class="meta">10 questões · 1,00 ponto cada · mínimo de 5 acertos. Textos transcritos <em>ipsis litteris</em> das fontes oficiais. Cada lei abre com um <strong>mapa por tópico</strong>; em seguida, cada tópico traz o trecho correspondente da lei, com seus títulos e capítulos.</p>

<div class="legenda"><strong>Legenda das alterações:</strong> <span class="add">texto acrescido</span> · <span class="del">texto suprimido</span> · <span class="badge">Alteração recente · potencial de prova</span> (mudança feita a partir de 2023). Só são destacadas as alterações dos últimos 10 anos (desde {ANO_LIMITE}); alterações mais antigas aparecem apenas na nota cinza. Abaixo de cada dispositivo alterado aparecem, em letra menor, <em>o que mudou</em> e a <em>redação anterior</em>. O comentário é gerado automaticamente pela comparação entre as redações; a nota cinza indica a norma que fez a alteração.</div>

<p class="meta">Ordem de estudo sugerida (do geral ao específico): <a href="#leg-c">Constituição</a> → <a href="#leg-j">LDB</a> → <a href="#leg-l">BNCC</a> → <a href="#leg-k">PNEPT</a> → <a href="#leg-m">ECA</a> → <a href="#leg-h">LBI</a> → <a href="#leg-e">igualdade racial</a> → <a href="#leg-g">Maria da Penha</a> → <a href="#leg-i">LGPD</a> → <a href="#leg-a">Liberato</a> → <a href="#leg-d">CLT</a>.</p>
"""
    s = s.replace("{ANO_LIMITE}", str(ANO_LIMITE))
    LDB = "lei9394-ldb.md"
    s += """
## a) Lei RS nº 14.498/2014 — Plano de Empregos, Funções e Salários da Fundação Liberato {#leg-a}

<p class="aviso">Texto original (AL-RS). As tabelas foram extraídas de PDF e podem estar desalinhadas: confira no PDF pelo link da fonte.</p>
"""
    s += MAPA("leg-a", "Lei nº 14.498/2014", "rs-lei14498-pefs-liberato.md", [
        ("Disposições preliminares: instituição e composição do Plano", "Cap. I — arts. 1º e 2º", [("1", "2")], []),
        ("Quadro de Empregos Permanentes (Analista Educacional — Orientador Educacional)", "Cap. II — arts. 3º e 4º", [("3", "4")], ["esp-d"]),
        ("Seleção, admissão e lotação", "Cap. III — arts. 5º e 6º", [("5", "6")], []),
        ("Jornada de trabalho", "Cap. IV — art. 7º", [("7",)], []),
        ("Promoções e avaliação de desempenho", "Cap. V — arts. 8º a 10", [("8", "10")], ["esp-j"]),
        ("Adicional de incentivo à capacitação", "Cap. VI — art. 11", [("11",)], []),
        ("Quadro de Empregos e de Funções em Comissão", "Cap. VII — arts. 12 a 14", [("12", "14")], []),
        ("Disposições finais e transitórias; aplicação subsidiária da CLT; anexos", "Cap. VIII — arts. 15 a 20 e anexos", [("15", "20")], []),
    ])
    s += f"""
## b) Estatuto da Fundação Liberato (Decreto nº 18.446/1967, alterado pelo Decreto nº 52.101/2014) {{#leg-b}}

{topicos("Natureza jurídica (pessoa jurídica de direito privado), sede e regência (Estatuto, Regimento Geral, Resoluções do Conselho Técnico Deliberativo)",
"Finalidades da Fundação (art. 3º): educação profissional e tecnológica; pesquisa e inovação",
"Patrimônio, rendas e aplicação de recursos (art. 5º)")}

<p class="aviso">O texto integral do Decreto 18.446/1967 não está disponível em meio digital no LEGIS/AL-RS. Abaixo está a íntegra do Decreto 52.101/2014, que dá nova redação aos dispositivos alterados do Estatuto.</p>
{LI("Decreto nº 52.101, de 27 de novembro de 2014 — íntegra", "rs-dec52101-estatuto-liberato.md")}

## c) Constituição Federal de 1988 — art. 37 e arts. 205 a 214 {{#leg-c}}
"""
    s += MAPA("leg-c", "CF/88", "cf88.md", [
        ("Administração Pública: princípios, concurso público, acumulação de cargos", "Art. 37", [("37",)], []),
        ("Educação: direito de todos, finalidades e princípios do ensino (gestão democrática, valorização dos profissionais)", "Arts. 205 e 206", [("205", "206")], ["esp-i", "leg-j"]),
        ("Autonomia universitária", "Art. 207", [("207",)], []),
        ("Dever do Estado com a educação", "Art. 208", [("208",)], ["esp-g", "leg-m"]),
        ("Ensino privado, conteúdos mínimos e regime de colaboração entre os sistemas", "Arts. 209 a 211", [("209", "211")], ["esp-i", "leg-l"]),
        ("Financiamento da educação e Fundeb", "Arts. 212, 212-A e 213", [("212", "213")], []),
        ("Plano Nacional de Educação", "Art. 214", [("214",)], []),
    ])
    s += """
## d) CLT — Jornada, descanso e férias {#leg-d}
"""
    s += MAPA("leg-d", "CLT", "clt-del5452.md", [
        ("Cap. II, Seção II — Da Jornada de Trabalho: duração normal, tempo parcial, horas extras, compensação, banco de horas, 12×36", "Arts. 58 a 65", [("58", "65")], []),
        ("Cap. II, Seção III — Dos Períodos de Descanso: interjornada, descanso semanal, intervalo intrajornada", "Arts. 66 a 72", [("66", "72")], []),
        ("Cap. IV, Seção I — Do Direito a Férias e da sua Duração", "Arts. 129 a 133", [("129", "133")], []),
        ("Cap. IV, Seção II — Da Concessão e da Época das Férias (fracionamento — Lei 13.467/2017)", "Arts. 134 a 138", [("134", "138")], []),
    ])
    s += """
## e) Lei nº 12.288/2010 — Estatuto da Igualdade Racial {#leg-e}
"""
    s += MAPA("leg-e", "Lei nº 12.288/2010", "lei12288-estatuto-igualdade-racial.md", [
        ("Disposições preliminares: objetivo, conceitos e deveres do Estado e da sociedade", "Título I — arts. 1º a 5º", [("1", "5")], []),
        ("Direito à saúde", "Arts. 6º a 8º", [("6", "8")], []),
        ("Direito à educação: disposições gerais e ensino de história geral da África e da população negra", "Arts. 9º a 16", [("9", "16")], ["esp-e", "leg-j"]),
        ("Cultura, esporte e lazer", "Arts. 17 a 22", [("17", "22")], []),
        ("Liberdade de consciência e de crença e livre exercício dos cultos religiosos", "Arts. 23 a 26", [("23", "26")], []),
        ("Acesso à terra e à moradia adequada", "Arts. 27 a 37", [("27", "37")], []),
        ("Trabalho", "Arts. 38 a 42", [("38", "42")], []),
        ("Meios de comunicação", "Arts. 43 a 46", [("43", "46")], []),
        ("Sistema Nacional de Promoção da Igualdade Racial (SINAPIR)", "Título III — arts. 47 a 57", [("47", "57")], []),
        ("Disposições finais", "Título IV — arts. 58 a 65", [("58", "65")], []),
    ])
    s += """
## f) Lei RS nº 13.694/2011 — Estatuto Estadual da Igualdade Racial {#leg-f}
"""
    s += MAPA("leg-f", "Lei nº 13.694/2011", "rs-lei13694-igualdade-racial-rs.md", [
        ("Disposições preliminares: objeto, diretrizes e participação da população negra", "Arts. 1º a 3º", [("1", "3")], []),
        ("Do direito à vida e à saúde", "Cap. I — arts. 4º a 8º", [("4", "8")], []),
        ("Do direito à cultura, à educação, ao esporte e ao lazer: ensino, datas cívicas, diversidade, literatura, permanência", "Cap. II — arts. 9º a 16", [("9", "16")], ["esp-e", "leg-e"]),
        ("Do acesso ao mercado de trabalho; quesito raça/cor", "Cap. III — arts. 17 e 18", [("17", "18")], []),
        ("Das terras quilombolas", "Cap. IV — art. 19", [("19",)], []),
        ("Da comunicação social; contratos administrativos", "Cap. V — arts. 20 a 23", [("20", "23")], []),
        ("Disposições finais", "Cap. VI — art. 24", [("24",)], []),
    ])
    s += """
## g) Lei nº 11.340/2006 — Lei Maria da Penha {#leg-g}
"""
    s += MAPA("leg-g", "Lei nº 11.340/2006", "lei11340-maria-da-penha.md", [
        ("Disposições preliminares: objeto e direitos fundamentais da mulher", "Arts. 1º a 4º", [("1", "4")], []),
        ("Violência doméstica e familiar: conceito e formas (física, psicológica, sexual, patrimonial e moral)", "Arts. 5º a 7º", [("5", "7")], ["esp-f"]),
        ("Medidas integradas de prevenção (inclusive nos currículos escolares) e assistência à mulher", "Arts. 8º e 9º", [("8", "9")], ["esp-e", "esp-f"]),
    ])
    s += """
## h) Lei nº 13.146/2015 — Lei Brasileira de Inclusão (Estatuto da Pessoa com Deficiência) {#leg-h}
"""
    s += MAPA("leg-h", "Lei nº 13.146/2015", "lei13146-lbi.md", [
        ("Disposições gerais: finalidade, conceito de pessoa com deficiência, definições (acessibilidade, desenho universal, adaptação razoável, profissional de apoio escolar)", "Arts. 1º a 3º", [("1", "3")], ["esp-g"]),
        ("Igualdade e não discriminação", "Arts. 4º a 8º", [("4", "8")], []),
        ("Direito à educação: sistema educacional inclusivo; incumbências do poder público; escolas privadas", "Arts. 27 a 30", [("27", "30")], ["esp-g", "leg-j"]),
    ])
    s += """
## i) Lei nº 13.709/2018 — LGPD {#leg-i}
"""
    s += MAPA("leg-i", "LGPD", "lei13709-lgpd-compilada.md", [
        ("Disposições preliminares: objetivo, fundamentos, aplicação, conceitos e princípios", "Arts. 1º a 6º", [("1", "6")], []),
        ("Requisitos (bases legais) para o tratamento de dados pessoais", "Art. 7º", [("7",)], []),
        ("Tratamento de dados pessoais sensíveis", "Art. 11", [("11",)], []),
        ("Tratamento de dados pessoais de crianças e adolescentes — aplicação na escola", "Art. 14", [("14",)], ["esp-d", "esp-f", "leg-m"]),
    ])
    s += """
## j) Lei nº 9.394/1996 — LDB (com as Leis 14.533/2023 e 14.811/2024) {#leg-j}

<p class="meta">LDB em texto compilado vigente, completa, dividida pelos tópicos do programa. As alterações das Leis 14.533/2023 (educação digital) e 14.811/2024 (segurança escolar) já estão no corpo do texto.</p>
"""
    s += MAPA("leg-j", "LDB", LDB, [
        ("Conceito de educação, princípios e fins da educação nacional", "Títulos I e II — arts. 1º a 3º", [("1", "3")], ["esp-i"]),
        ("Direito à educação e dever de educar (inclusive educação digital e AEE)", "Título III — arts. 4º a 7º-A", [("4", "7-A")], ["esp-g", "leg-m"]),
        ("Organização da educação nacional: incumbências da União, dos Estados e dos Municípios", "Título IV — arts. 8º a 11", [("8", "11")], ["esp-j"]),
        ("Incumbências dos estabelecimentos de ensino e dos docentes; gestão democrática; autonomia", "Título IV — arts. 12 a 15", [("12", "15")], ["esp-b", "esp-f", "esp-i"]),
        ("Sistemas de ensino", "Título IV — arts. 16 a 20", [("16", "20")], []),
        ("Educação básica — composição dos níveis e disposições gerais: organização, calendário, verificação do rendimento, frequência, currículo e BNCC", "Título V, Cap. I e Cap. II, Seção I — arts. 21 a 28", [("21", "28")], ["esp-b", "esp-i", "esp-j", "leg-l"]),
        ("Educação infantil e ensino fundamental", "Seções II e III — arts. 29 a 34", [("29", "34")], []),
        ("Ensino médio: finalidades, BNCC, formação geral básica e itinerários formativos", "Seção IV — arts. 35 a 36", [("35", "36")], ["esp-h", "leg-l"]),
        ("Educação profissional técnica de nível médio", "Seção IV-A — arts. 36-A a 36-D", [("36-A", "36-D")], ["esp-h", "leg-k"]),
        ("Educação de jovens e adultos", "Seção V — arts. 37 e 38", [("37", "38")], []),
        ("Educação profissional e tecnológica", "Cap. III — arts. 39 a 42", [("39", "42")], ["esp-h", "leg-k"]),
        ("Educação superior", "Cap. IV — arts. 43 a 57", [("43", "57")], []),
        ("Educação especial e educação bilíngue de surdos", "Cap. V e V-A — arts. 58 a 60-B", [("58", "60-B")], ["esp-g", "leg-h"]),
        ("Profissionais da educação: formação, orientação educacional (art. 64), valorização", "Título VI — arts. 61 a 67", [("61", "67")], ["esp-d", "esp-j"]),
        ("Recursos financeiros", "Título VII — arts. 68 a 77", [("68", "77")], []),
        ("Disposições gerais: educação indígena, EAD, estágio, educação no campo", "Título VIII — arts. 78 a 86", [("78", "86")], []),
        ("Disposições transitórias", "Título IX — arts. 87 a 92", [("87", "92")], []),
    ])
    s += """
### Lei nº 14.533/2023 — Política Nacional de Educação Digital {#leg-j-pned}
"""
    s += MAPA("leg-jd", "Lei nº 14.533/2023", "lei14533-educacao-digital.md", [
        ("Política Nacional de Educação Digital (PNED) e seus eixos", "Art. 1º", [("1",)], []),
        ("Eixo inclusão digital", "Art. 2º", [("2",)], []),
        ("Eixo Educação Digital Escolar", "Art. 3º", [("3",)], ["esp-b", "esp-g"]),
        ("Eixos capacitação e especialização digital; pesquisa e desenvolvimento em TIC", "Arts. 4º e 5º", [("4", "5")], []),
        ("Implementação dos eixos; alterações na LDB e na Lei 9.448/1997", "Arts. 6º a 8º", [("6", "8")], ["leg-j"]),
        ("Financiamento e vigência", "Arts. 9º a 12", [("9", "12")], []),
    ])
    s += """
### Lei nº 14.811/2024 — Proteção contra a violência nos estabelecimentos educacionais {#leg-j-seg}
"""
    s += MAPA("leg-js", "Lei nº 14.811/2024", "lei14811-seguranca-escolar.md", [
        ("Medidas de proteção e de prevenção à violência em estabelecimentos educacionais; protocolos", "Arts. 1º a 3º", [("1", "3")], ["esp-f"]),
        ("Política Nacional de Prevenção e Combate ao Abuso e Exploração Sexual da Criança e do Adolescente", "Art. 4º", [("4",)], ["leg-m"]),
        ("Alterações no Código Penal (inclusive intimidação sistemática — bullying e cyberbullying) e na Lei dos Crimes Hediondos", "Arts. 5º a 7º", [("5", "7")], []),
        ("Alterações no ECA e vigência", "Arts. 8º a 10", [("8", "10")], ["leg-m"]),
    ])
    s += """
## k) Decreto nº 12.603/2025 — Política Nacional de Educação Profissional e Tecnológica (PNEPT) {#leg-k}
"""
    s += MAPA("leg-k", "Decreto nº 12.603/2025", "dec12603-pnept.md", [
        ("Disposições gerais: objeto, princípios, objetivos e eixos da PNEPT", "Cap. I — arts. 1º a 6º", [("1", "6")], ["esp-h", "leg-j"]),
        ("Oferta de cursos", "Cap. II — arts. 7º a 13", [("7", "13")], ["esp-h"]),
        ("Estratégias", "Cap. III — art. 14", [("14",)], []),
        ("Governança e participação (CTPP)", "Cap. IV — art. 15", [("15",)], []),
        ("Monitoramento e avaliação (SINAEPT)", "Cap. V — arts. 16 a 20", [("16", "20")], []),
        ("Fontes e recursos", "Cap. VI — art. 21", [("21",)], []),
        ("Disposições finais", "Cap. VII — arts. 22 a 24", [("22", "24")], []),
    ])
    s += f"""
## l) Base Nacional Comum Curricular — Ensino Médio e Educação Profissional Técnica {{#leg-l}}

{topicos("Marcos legais da BNCC (CF art. 210; LDB arts. 9º, IV, 26 e 35-A; PNE)",
"As **10 competências gerais da Educação Básica**",
"Ensino Médio: áreas do conhecimento (Linguagens, Matemática, Ciências da Natureza, Ciências Humanas e Sociais Aplicadas), competências específicas e habilidades",
"Itinerários formativos e o itinerário de formação técnica e profissional (LDB art. 36)",
"Juventudes e projeto de vida; protagonismo juvenil")}
"""
    comp = linhas_entre("bncc.md", "###### COMPETÊNCIAS GERAIS DA EDUCAÇÃO BÁSICA", r"^#{1,6} ")
    comp = re.sub(r"^#{1,6}\s*", "", comp, flags=re.M)
    s += caixa_lei("BNCC — Competências gerais da Educação Básica (texto oficial)", F("bncc.md"),
                   [("txt", b.strip()) for b in re.split(r"\n\s*\n", comp) if b.strip()], aberto=True)
    s += """
## m) Lei nº 8.069/1990 — Estatuto da Criança e do Adolescente {#leg-m}
"""
    s += MAPA("leg-m", "ECA", "lei8069-eca.md", [
        ("Disposições preliminares: proteção integral, conceito de criança e adolescente, prioridade absoluta", "Arts. 1º a 6º", [("1", "6")], ["esp-e"]),
        ("Direito à liberdade, ao respeito e à dignidade; educação sem castigo físico", "Arts. 15 a 18-B", [("15", "18-B")], ["esp-e", "esp-f"]),
        ("Direito à educação, à cultura, ao esporte e ao lazer; comunicação ao Conselho Tutelar (art. 56)", "Arts. 53 a 59", [("53", "59")], ["esp-f", "leg-j"]),
        ("Prevenção: políticas contra a violência e o castigo físico", "Arts. 70-A e 70-B", [("70-A", "70-B")], []),
        ("Medidas de proteção", "Arts. 98 a 101", [("98", "101")], ["esp-f"]),
        ("Conselho Tutelar", "Arts. 131 a 137", [("131", "137")], ["esp-f"]),
        ("Infração administrativa: falta de comunicação de maus-tratos", "Art. 245", [("245",)], ["esp-f"]),
    ])
    return s


def parte_especificos():
    LDB = "lei9394-ldb.md"
    return f"""
# Parte III — Conhecimentos Específicos: Orientador Educacional {{#esp}}

<p class="meta">40 questões · 1,75 ponto cada · mínimo de 20 acertos (70% da nota total)</p>

<div class="legenda"><strong>Atribuições do emprego (Anexo III do edital):</strong> coletar dados sobre o aluno; estudar, atender e acompanhar casos; realizar entrevistas individuais e reuniões com alunos, professores, pais e demais pessoas envolvidas com a escola; articular-se com médicos, psicólogos, clínicas e serviços; estudar e encaminhar os casos que extrapolam a esfera escolar; assistir às turmas das últimas séries no prosseguimento do seu aperfeiçoamento, na colocação profissional e em problemas que envolvam escolhas ou decisões; programar e desenvolver sessões coletivas e palestras para os alunos; sugerir medidas de melhoria dos sistemas de ensino; auxiliar a Diretoria na solução de problemas de relações humanas; auxiliar na integração da Fundação à comunidade; estimular os professores a avaliarem seu desempenho.</div>

## a) Pensadores da educação e história da educação {{#esp-a}}

{topicos("Antiguidade e Idade Média: paideia grega (Sócrates, Platão, Aristóteles); escolástica",
"Modernidade: Comenius (*Didática Magna*), Rousseau (*Emílio*), Pestalozzi, Herbart, Froebel",
"Escola Nova: Dewey, Montessori, Decroly, Claparède, Freinet; no Brasil, Anísio Teixeira e o Manifesto dos Pioneiros (1932)",
"Pedagogias críticas: Paulo Freire, Saviani (pedagogia histórico-crítica), Libâneo (crítico-social dos conteúdos)",
"Tendências pedagógicas liberais (tradicional, renovada progressivista e não diretiva, tecnicista) e progressistas (libertadora, libertária, crítico-social dos conteúdos)",
"História da educação brasileira: jesuítas, reformas pombalinas, Império, República, LDBs de 1961, 1971 e 1996")}

## b) Elementos da prática pedagógica. Recursos tecnológicos. Metodologias ativas {{#esp-b}}

{topicos("Planejamento de aula e níveis de planejamento (sistema, escola, currículo, ensino, aula)",
"Currículo: formal, real, oculto; organização curricular",
"Regimento escolar: natureza, conteúdo e relação com o PPP",
"Metodologias de ensino, projetos de trabalho e técnicas didáticas",
"Avaliação da aprendizagem (aprofundada no <a href='#esp-j'>ponto j</a>)",
"Recursos tecnológicos e educação: educação digital, cultura digital, ensino híbrido",
"Metodologias ativas: sala de aula invertida, aprendizagem baseada em projetos e em problemas, rotação por estações, gamificação, instrução por pares (*peer instruction*)")}
{L("Base legal — LDB, arts. 12 e 13 (incumbências da escola e dos docentes)", LDB, ("12", "13"))}
{L("Base legal — LDB, arts. 23 e 24 (organização e verificação do rendimento)", LDB, ("23", "24"))}
{L("Base legal — Lei nº 14.533/2023, arts. 1º a 3º (Política Nacional de Educação Digital; educação digital escolar)", "lei14533-educacao-digital.md", ("1", "3"))}

## c) Teorias do conhecimento e da aprendizagem; tipos de conhecimento; desenvolvimento cognitivo; inteligências múltiplas; o lúdico {{#esp-c}}

{topicos("Empirismo, inatismo (apriorismo) e interacionismo/construtivismo",
"Comportamentalismo (Skinner, Watson): condicionamento e reforço",
"Epistemologia genética (Piaget): assimilação, acomodação, equilibração",
"Sociointeracionismo (Vygotsky): mediação, zona de desenvolvimento proximal, internalização, linguagem",
"Teoria psicogenética de Wallon: afetividade, emoção, movimento",
"Aprendizagem significativa (Ausubel); aprendizagem por descoberta (Bruner)",
"Interdisciplinaridade, multidisciplinaridade, pluridisciplinaridade e transdisciplinaridade: graus crescentes de integração entre as disciplinas (Japiassu, Fazenda, Morin)",
"Tipos de conhecimento: senso comum, científico, filosófico, teológico/religioso, artístico",
"Estágios do desenvolvimento cognitivo (Piaget): sensório-motor, pré-operatório, operatório-concreto, operatório-formal",
"Competências e capacidades: conceito (Perrenoud; BNCC — mobilização de conhecimentos, habilidades, atitudes e valores)",
"Inteligências múltiplas (Gardner): linguística, lógico-matemática, espacial, corporal-cinestésica, musical, interpessoal, intrapessoal, naturalista",
"O lúdico na educação: jogo, brincadeira e aprendizagem (Kishimoto, Vygotsky, Piaget)")}
<p class="ref">Ver também: <a href="#leg-l">BNCC — competências gerais</a> · <a href="#esp-e">ponto e (desenvolvimento humano)</a>.</p>

## d) Fundamentos e práticas da Orientação Educacional {{#esp-d}}

<p class="autores">Autora sugerida: Mírian P. S. Zippin Grinspun</p>

{topicos("História da Orientação Educacional (OE) no Brasil: origem na orientação profissional (década de 1920); Leis Orgânicas do Ensino de 1942 (Reforma Capanema), que introduzem a OE na escola; LDB de 1961 (formação do orientador); Lei nº 5.564/1968 e Decreto nº 72.846/1973 (profissão de orientador educacional); Lei nº 5.692/1971 (OE obrigatória, com aconselhamento vocacional); LDB de 1996 (art. 64)",
"Períodos da OE segundo Grinspun: implementador (1920–1941), institucional (1942–1960), transformador (1961–1970), disciplinador (1971–1980), questionador (década de 1980) e orientador (a partir de 1990)",
"Conceitos e princípios: da orientação terapêutica e individual, centrada no “aluno-problema” e no ajustamento, para a orientação pedagógica, coletiva e contextualizada, comprometida com a formação do sujeito e da cidadania",
"Áreas de atuação: alunos, professores, famílias, comunidade e equipe gestora",
"Desafios no espaço escolar contemporâneo: diversidade, violência, mídias e redes, saúde mental, projeto de vida, permanência e êxito",
"Gestão da OE: plano de ação do serviço, diagnóstico da realidade escolar, registros e projetos específicos da área (justificativa, objetivos, metodologia, cronograma, avaliação)",
"O orientador como agente integrador e articulador do trabalho pedagógico, mediador entre aluno, professor, família e escola",
"Paradigmas da ciência aplicados à educação: paradigma newtoniano-cartesiano (fragmentação, objetividade) × paradigma emergente, da complexidade (Kuhn, Morin, Boaventura de Sousa Santos); o “conflito de paradigmas” em Grinspun")}
{L("Base legal — LDB, arts. 61 e 64 (profissionais da educação; formação para a orientação educacional)", LDB, ("61",), ("64",))}
<p class="ref">Ver também: <a href="#leg-a-2">Lei RS 14.498/2014 — Quadro de Empregos Permanentes</a> · <a href="#esp-j">ponto j (parceria com a Supervisão Escolar)</a>.</p>

## e) Desenvolvimento humano e subjetividade {{#esp-e}}

<p class="autores">Autores sugeridos: Jean Piaget · Lev Vygotsky · Henri Wallon · César Coll · Howard Gardner · Yves de La Taille</p>

{topicos("Desenvolvimento da criança e do adolescente: aspectos cognitivos, afetivos, sociais e psicológicos",
"Piaget: estágios do desenvolvimento cognitivo e construção do conhecimento; desenvolvimento moral (anomia, heteronomia, autonomia)",
"Vygotsky: origem social das funções psicológicas superiores; pensamento e linguagem; mediação; zona de desenvolvimento proximal",
"Wallon: estágios (impulsivo-emocional, sensório-motor e projetivo, personalismo, categorial, puberdade e adolescência); alternância entre afetividade e cognição; a pessoa completa",
"César Coll: construtivismo na sala de aula; conteúdos conceituais, procedimentais e atitudinais; ajuda pedagógica ajustada",
"Gardner: inteligências múltiplas; competências e capacidades",
"La Taille: moral e ética; limites; virtudes; personalidade ética",
"Estruturação da subjetividade: o sujeito constituído nas relações sociais, na cultura e na linguagem",
"Identidades na sociedade contemporânea: diversidade, gênero e juventude(s); culturas juvenis; projeto de vida")}
{L("Base legal — ECA, arts. 1º a 6º (proteção integral; condição peculiar de pessoa em desenvolvimento)", "lei8069-eca.md", ("1", "6"))}
{L("Base legal — ECA, arts. 15 a 18-B (liberdade, respeito e dignidade)", "lei8069-eca.md", ("15", "18-B"))}
<p class="ref">Ver também: <a href="#esp-c">ponto c (teorias da aprendizagem)</a> · <a href="#leg-e">Estatuto da Igualdade Racial</a> · <a href="#leg-g">Lei Maria da Penha</a>.</p>

## f) Relações interpessoais, família e escola {{#esp-f}}

{topicos("Gestão das relações intra e interpessoais no ambiente escolar: autoconhecimento, empatia, comunicação, escuta ativa, clima escolar",
"A rede de vínculos: familiar, escolar e do aluno consigo mesmo",
"Articulação escola/comunidade e participação da família na escola: reuniões, entrevistas, conselhos, corresponsabilidade",
"Mediação e gestão de conflitos no cotidiano escolar: conflito × violência; mediação entre pares; práticas restaurativas e círculos de diálogo; comunicação não violenta",
"Intimidação sistemática (*bullying* e *cyberbullying*): prevenção, protocolos e encaminhamentos",
"Rede de proteção: Conselho Tutelar, serviços de saúde e assistência social; comunicação obrigatória de maus-tratos e de faltas reiteradas",
"Marketing educacional: marketing de relacionamento, imagem institucional, captação e retenção de alunos, endomarketing; construção de relacionamentos institucionais positivos")}
{L("Base legal — LDB, art. 12 (articulação com as famílias; notificação de faltas ao Conselho Tutelar; combate à intimidação sistemática; cultura de paz)", LDB, ("12",))}
{L("Base legal — ECA, arts. 53 a 56 (direito à educação; deveres dos pais; comunicação ao Conselho Tutelar)", "lei8069-eca.md", ("53", "56"))}
{L("Base legal — Lei nº 14.811/2024, arts. 1º a 3º (proteção contra a violência nos estabelecimentos educacionais)", "lei14811-seguranca-escolar.md", ("1", "3"))}
<p class="ref">Ver também: <a href="#leg-m">ECA — medidas de proteção e Conselho Tutelar</a> · <a href="#leg-i">LGPD — dados de crianças e adolescentes</a>.</p>

## g) Dificuldades de aprendizagem, inclusão e práticas educativas {{#esp-g}}

<p class="autores">Autores sugeridos: Paulo Freire · José Carlos Libâneo · Michel Foucault · Rubem Alves</p>

{topicos("Rendimento escolar e causas do fracasso escolar: explicações centradas no aluno e na família (carência cultural) × explicações institucionais e sociais (Patto: a produção do fracasso escolar)",
"Dificuldades × transtornos de aprendizagem: dislexia, disgrafia, disortografia, discalculia, TDAH; papel da escola, identificação precoce e encaminhamentos",
"Educação inclusiva e atendimento à diversidade: inclusão × integração; atendimento educacional especializado (AEE); adaptações razoáveis; desenho universal",
"O lúdico na educação como recurso de aprendizagem e de vínculo",
"Uso de tecnologias e recursos digitais na educação; tecnologia assistiva",
"Pedagogia da Emergência (Bernd Ruf): intervenção pedagógica, de base Waldorf, com crianças e jovens em situação de trauma (catástrofes, violência, perdas); ritmo, vínculo, arte, movimento e brincar para estabilizar e prevenir o transtorno pós-traumático",
"Paulo Freire: educação bancária × problematizadora; diálogo; autonomia; leitura do mundo",
"Libâneo: didática, democratização da escola pública, pedagogia crítico-social dos conteúdos",
"Foucault: poder disciplinar, vigilância, exame e normalização na escola (*Vigiar e punir*)",
"Rubem Alves: escolas que são gaiolas × escolas que são asas; o prazer de aprender; a alegria de ensinar")}
{L("Base legal — LDB, arts. 58 a 60 (Educação Especial)", LDB, ("58", "60"))}
{L("Base legal — LBI, arts. 27 e 28 (Direito à Educação)", "lei13146-lbi.md", ("27", "28"))}
{LI("Base legal — Lei nº 14.254/2021 (dislexia, TDAH e outros transtornos de aprendizagem) — íntegra", "lei14254-dislexia-tdah.md")}
<p class="ref">Ver também: <a href="#esp-b">ponto b (educação digital)</a> · <a href="#leg-h">LBI</a>.</p>

## h) Orientação para o trabalho e cidadania {{#esp-h}}

<p class="autores">Autora sugerida: Acácia Kuenzer</p>

{topicos("O processo de escolha profissional: fatores pessoais, familiares, sociais e econômicos; autoconhecimento, informação profissional e projeto de vida",
"Orientação vocacional/profissional: abordagens de traço e fator (Parsons), desenvolvimentista (Super), tipológica (Holland), clínica (Bohoslavsky) e sócio-histórica (Bock)",
"Relação educação/trabalho e desenvolvimento econômico-social: o trabalho como princípio educativo; dualidade estrutural do ensino médio; politecnia e formação integrada (Kuenzer)",
"Educação para o consumo: consumo consciente, educação financeira, publicidade e juventude",
"O Ensino Médio e a Educação Profissional: formas de oferta (integrada, concomitante, subsequente); itinerário de formação técnica e profissional",
"Catálogo Nacional de Cursos Técnicos (CNCT): organização por eixos tecnológicos, cargas horárias mínimas e perfil profissional de conclusão",
"Meio ambiente e sociedade: sustentabilidade e educação ambiental como tema transversal",
"Legislação específica indicada no edital: Resolução nº 365/2021")}
{L("Base legal — LDB, arts. 35 a 36-D (Ensino Médio e Educação Profissional Técnica de Nível Médio)", LDB, ("35", "36-D"))}
{L("Base legal — LDB, arts. 39 a 42 (Educação Profissional e Tecnológica)", LDB, ("39", "42"))}

### Resolução CEEd-RS nº 365/2021 — normas complementares para o Ensino Médio no RS {{#esp-h-365}}

<p class="aviso">O edital cita apenas “Resolução nº 365/2021”, como legislação da Educação Técnica. Esta apostila adota a Resolução nº 365/2021 do Conselho Estadual de Educação do RS, que trata do Ensino Médio e de seus itinerários, inclusive o de formação técnica e profissional.</p>

{MAPA("esp-h-365", "Resolução CEEd-RS nº 365/2021", "ceed-rs-resolucao-365-2021.md", [
    ("Disposições gerais e organização do Ensino Médio", "Arts. 1º a 4º", [("1", "4")], []),
    ("Currículo: Formação Geral Básica e Itinerários Formativos", "Arts. 5º a 15", [("5", "15")], ["leg-l", "leg-j"]),
    ("Projeto de Vida e trilhas dos itinerários", "Arts. 16 a 20", [("16", "20")], ["esp-e"]),
    ("Unidades curriculares eletivas", "Arts. 21 a 29", [("21", "29")], []),
    ("Parcerias", "Arts. 30 a 37", [("30", "37")], []),
    ("Educação a distância no Ensino Médio", "Arts. 38 a 41", [("38", "41")], []),
    ("Ensino Médio noturno", "Arts. 42 a 48", [("42", "48")], []),
    ("Educação de Jovens e Adultos", "Arts. 49 a 62", [("49", "62")], []),
    ("Educação do campo, indígena e quilombola; aproveitamento de estudos; transferência", "Arts. 63 a 66", [("63", "66")], []),
    ("Registros, avaliação, certificação e documentação escolar", "Arts. 67 a 79", [("67", "79")], ["esp-j"]),
    ("Disposições finais", "Arts. 80 a 83", [("80", "83")], []),
])}
<p class="ref">Ver também: <a href="#leg-k">PNEPT (Decreto nº 12.603/2025)</a> · <a href="#leg-l">BNCC — Ensino Médio</a>.</p>

## i) Gestão democrática, planejamento e currículo {{#esp-i}}

<p class="autores">Autores sugeridos: Ilma Passos Alencastro Veiga · Danilo Gandin · Mary Rangel · Heloísa Lück</p>

{topicos("Gestão democrática na escola: participação, descentralização, transparência; Conselho Escolar (funções deliberativa, consultiva, fiscal e mobilizadora)",
"O princípio da autonomia: administrativa, financeira e pedagógica (Veiga acrescenta a jurídica)",
"PPP e proposta pedagógica: dimensões política e pedagógica; princípios (igualdade, qualidade, gestão democrática, liberdade, valorização do magistério — Veiga); elaboração, acompanhamento e avaliação",
"Planejamento participativo (Gandin): marco referencial (situacional, doutrinal, operativo), diagnóstico e programação",
"Organização do trabalho pedagógico, divisão social do trabalho e burocratização na escola: fragmentação entre quem pensa e quem executa; crítica aos “especialistas”; trabalho coletivo",
"Gestão educacional e liderança; da administração à gestão (Lück)",
"Reflexões sobre currículo e abordagens de ensino: interdisciplinaridade, multidisciplinaridade, transdisciplinaridade",
"Ação integrada de orientação, supervisão e administração escolar (Rangel)")}
{L("Base legal — CF/88, art. 206 (princípios do ensino; gestão democrática)", "cf88.md", ("206",), )}
{L("Base legal — LDB, arts. 3º, 12, 13, 14 e 15", LDB, ("3",), ("12", "15"))}
{L("Base legal — LDB, arts. 26, 26-A e 27 (currículo da educação básica)", LDB, ("26", "27"))}

## j) Articulação pedagógica: avaliação e Supervisão Escolar {{#esp-j}}

<p class="autores">Autores sugeridos: Jussara Hoffmann · Cipriano Luckesi · Isabel Alarcão · Philippe Perrenoud · Celso dos Santos Vasconcelos</p>

{topicos("História, conceitos e atuação da Orientação Educacional (ver <a href='#esp-d'>ponto d</a>)",
"Parceria entre Orientação e Supervisão Escolar: a orientação com foco no aluno e em suas relações, a supervisão com foco no professor e no currículo; trabalho integrado no Conselho de Classe, no PPP e na formação continuada",
"Diagnóstico e intervenção psicopedagógica: queixa escolar, entrevistas, observação, devolutiva, plano de intervenção e encaminhamentos; caráter preventivo e institucional",
"Avaliação escolar e sua função social: classificatória × diagnóstica (Luckesi: avaliar × examinar)",
"Avaliação mediadora e formativa — “avaliar para promover” (Hoffmann); concepção dialética-libertadora (Vasconcelos)",
"Dimensões da avaliação no processo ensino-aprendizagem: diagnóstica, formativa, somativa",
"Formação reflexiva de professores: professor reflexivo e escola reflexiva (Alarcão); reflexão na ação e sobre a ação (Schön); dez novas competências para ensinar (Perrenoud)",
"Avaliação docente: autoavaliação e avaliação de desempenho (nas atribuições do emprego: “estimular os professores a avaliarem seu desempenho”)")}
{L("Base legal — LDB, art. 24 (verificação do rendimento, frequência mínima, recuperação)", LDB, ("24",))}
{L("Base legal — LDB, arts. 61 a 67 (Dos Profissionais da Educação)", LDB, ("61", "67"))}
<p class="ref">Ver também: <a href="#leg-a-5">Lei RS 14.498/2014 — promoções e avaliação de desempenho</a>.</p>
"""


# -------------------------------------------------------------- template --

CSS = """
:root{--bg:#fbfaf7;--fg:#1f2328;--muted:#5d646d;--line:#e3e0d8;--card:#ffffff;--accent:#1d5fa8;--accent-bg:#e9f1fb;--law:#f6f4ee;--note:#7a6f5a;--warn:#8a5a00;--warn-bg:#fff4dc}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15171a;--fg:#e6e6e6;--muted:#a2a8b0;--line:#2c3036;--card:#1c1f23;--accent:#7fb0ea;--accent-bg:#1c2a3b;--law:#1a1d21;--note:#b5a98f;--warn:#f0c068;--warn-bg:#2e2716}}
:root[data-theme="dark"]{--bg:#15171a;--fg:#e6e6e6;--muted:#a2a8b0;--line:#2c3036;--card:#1c1f23;--accent:#7fb0ea;--accent-bg:#1c2a3b;--law:#1a1d21;--note:#b5a98f;--warn:#f0c068;--warn-bg:#2e2716}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 "Source Serif 4",Georgia,serif}
a{color:var(--accent)}
.wrap{display:grid;grid-template-columns:290px minmax(0,1fr);max-width:1280px;margin:0 auto}
nav{position:sticky;top:0;height:100vh;overflow:auto;padding:24px 16px;border-right:1px solid var(--line);font:14px/1.45 system-ui,sans-serif}
nav h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:18px 0 6px}
nav a{display:block;padding:3px 6px;border-radius:4px;text-decoration:none;color:var(--fg)}
nav a:hover{background:var(--accent-bg)}
nav .tools{display:flex;gap:6px;flex-wrap:wrap}
nav button{font:13px system-ui,sans-serif;padding:5px 8px;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;cursor:pointer}
main{padding:32px 40px 80px;min-width:0}
header.capa{border-bottom:2px solid var(--fg);padding-bottom:16px;margin-bottom:24px}
header.capa h1{font-size:32px;line-height:1.2;margin:0 0 6px}
header.capa p{margin:4px 0;color:var(--muted);font-family:system-ui,sans-serif;font-size:14px}
h1{font-size:28px;margin:56px 0 8px;padding-top:8px;border-top:1px solid var(--line)}
h2{font-size:21px;margin:36px 0 10px;color:var(--fg)}
.meta,.autores,.ref{font:14px/1.5 system-ui,sans-serif;color:var(--muted);margin:4px 0 12px}
.autores{color:var(--fg);background:var(--accent-bg);padding:6px 10px;border-radius:6px;display:inline-block}
ul{padding-left:22px}
li{margin:3px 0}
.aviso{font:14px/1.5 system-ui,sans-serif;background:var(--warn-bg);color:var(--warn);padding:8px 12px;border-radius:6px}
details.lei{background:var(--law);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:6px;margin:12px 0;padding:0 16px}
details.questoes{border:1px solid var(--line);border-radius:6px;margin:8px 0;padding:0 12px;background:var(--card);font:14px/1.5 system-ui,sans-serif}
details.questoes>summary{cursor:pointer;padding:7px 0;font-weight:600}
details.questoes ul{margin:4px 0 10px}
details.lei>summary{cursor:pointer;padding:10px 0;font:600 15px/1.4 system-ui,sans-serif;color:var(--accent)}
table.mapa{display:table;width:100%;font:14px/1.45 system-ui,sans-serif;margin:12px 0 20px}
table.mapa caption{text-align:left;font-weight:600;padding:4px 0;color:var(--muted)}
table.mapa th{background:var(--accent-bg);text-align:left}
table.mapa td:nth-child(2){white-space:nowrap}
@media (max-width:860px){table.mapa{display:block}table.mapa td:nth-child(2){white-space:normal}}
h3{font-size:17px;margin:28px 0 4px}
:root{--add-bg:#d7f5dd;--add-fg:#0b5d1e;--del-bg:#fde2e1;--del-fg:#9b1c1c;--hot:#c2410c;--hot-bg:#fff4ec}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--add-bg:#12391d;--add-fg:#8ee6a3;--del-bg:#45191a;--del-fg:#ffaaa5;--hot:#fb923c;--hot-bg:#2a1a10}}
:root[data-theme="dark"]{--add-bg:#12391d;--add-fg:#8ee6a3;--del-bg:#45191a;--del-fg:#ffaaa5;--hot:#fb923c;--hot-bg:#2a1a10}
.add{background:var(--add-bg);color:var(--add-fg);border-radius:3px;padding:0 2px}
.del{background:var(--del-bg);color:var(--del-fg);text-decoration:line-through;border-radius:3px;padding:0 2px}
.del-l{background:var(--del-bg);color:var(--del-fg);border-radius:3px;padding:0 2px}
.alt{border-left:3px solid var(--line);padding:2px 0 2px 10px;margin:8px 0}
.alt.recente{border-left-color:var(--hot);background:var(--hot-bg);border-radius:0 6px 6px 0}
.selo{margin:4px 0 0}
.badge{display:inline-block;font:600 11px/1.6 system-ui,sans-serif;letter-spacing:.02em;color:#fff;background:var(--hot);border-radius:10px;padding:0 8px}
.antes{font:12.5px/1.5 system-ui,sans-serif;color:var(--muted);margin:4px 0 8px;padding:4px 10px;border:1px dashed var(--line);border-radius:6px}
.antes p{margin:3px 0;font-size:12.5px}
.antes .velha{opacity:.8}
.recentes{font:14px/1.5 system-ui,sans-serif;background:var(--hot-bg);border:1px solid var(--hot);border-radius:6px;padding:6px 12px;margin:0 0 18px}
.recentes ul{margin:4px 0}
.legenda{font:13px/1.6 system-ui,sans-serif;border:1px solid var(--line);border-radius:6px;padding:8px 12px;background:var(--card)}
.arts{font:13px/1.5 system-ui,sans-serif;color:var(--muted);margin:0 0 6px}
details.lei>summary p{display:inline;margin:0;font:inherit}
details.lei[open]>summary{border-bottom:1px solid var(--line);margin-bottom:8px}
details.lei p{margin:6px 0;font-size:15px}
details.lei .fonte{font:12px system-ui,sans-serif;color:var(--muted)}
.tit{text-align:center;font:600 13px/1.4 system-ui,sans-serif;letter-spacing:.04em;text-transform:uppercase;margin:16px 0 4px;color:var(--muted)}
.tit p{margin:0}
.nota{font:12px system-ui,sans-serif;color:var(--note)}
table{border-collapse:collapse;font-size:13px;display:block;overflow-x:auto;margin:8px 0}
td,th{border:1px solid var(--line);padding:3px 6px;vertical-align:top}
@media (max-width:860px){.wrap{display:block}nav{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line);padding:16px}main{padding:16px 16px 60px}h1{font-size:24px}}
@media print{nav{display:none}.wrap{display:block}main{padding:0}details.lei{break-inside:auto}}
"""

JS = """
function todos(abrir){document.querySelectorAll('details.lei').forEach(d=>d.open=abrir)}
function tema(){const r=document.documentElement;const dark=r.dataset.theme?r.dataset.theme==='dark':matchMedia('(prefers-color-scheme: dark)').matches;r.dataset.theme=dark?'light':'dark';try{localStorage.setItem('tema',r.dataset.theme)}catch(e){}}
try{const t=localStorage.getItem('tema');if(t)document.documentElement.dataset.theme=t}catch(e){}
window.addEventListener('beforeprint',()=>todos(true));
"""


def nav():
    pt = [("pt-a", "a) Leitura e compreensão"), ("pt-b", "b) Léxico"), ("pt-c", "c) Aspectos linguísticos")]
    leg = [("leg-a", "a) Lei RS 14.498/2014"), ("leg-b", "b) Estatuto da Fundação"), ("leg-c", "c) CF/88"),
           ("leg-d", "d) CLT"), ("leg-e", "e) Lei 12.288/2010"), ("leg-f", "f) Lei RS 13.694/2011"),
           ("leg-g", "g) Maria da Penha"), ("leg-h", "h) LBI"), ("leg-i", "i) LGPD"), ("leg-j", "j) LDB"),
           ("leg-k", "k) PNEPT"), ("leg-l", "l) BNCC"), ("leg-m", "m) ECA")]
    esp = [("esp-a", "a) Pensadores e história"), ("esp-b", "b) Prática pedagógica"), ("esp-c", "c) Aprendizagem e conhecimento"),
           ("esp-d", "d) Orientação Educacional"), ("esp-e", "e) Desenvolvimento e subjetividade"), ("esp-f", "f) Família, escola e conflitos"),
           ("esp-g", "g) Dificuldades e inclusão"), ("esp-h", "h) Trabalho e cidadania"), ("esp-i", "i) Gestão, planejamento e currículo"),
           ("esp-j", "j) Avaliação e supervisão")]
    def bloco(t, ancora, itens):
        return f'<h2><a href="#{ancora}">{t}</a></h2>' + "".join(f'<a href="#{a}">{n}</a>' for a, n in itens)
    return ('<nav><div class="tools"><button onclick="todos(true)">Abrir leis</button>'
            '<button onclick="todos(false)">Fechar leis</button><button onclick="tema()">Tema</button></div>'
            + bloco("I · Português", "pt", pt) + bloco("II · Legislação", "leg", leg)
            + bloco("III · Específicos", "esp", esp) + "</nav>")


def main():
    md = parte_portugues() + parte_legislacao() + parte_especificos()
    # converte seção por seção (## ...) para limitar o uso de memória do pandoc
    pedacos = [p for p in re.split(r"(?m)^(?=#{1,2} )", md) if p.strip()]
    corpo = "\n".join(
        subprocess.run(
            ["pandoc", "+RTS", "-K512m", "-RTS", "-f", "markdown-fancy_lists-example_lists-implicit_figures-tex_math_dollars-subscript-superscript",
             "-t", "html5", "--wrap=none"],
            input=p.encode("utf-8"), capture_output=True, check=True,
        ).stdout.decode("utf-8")
        for p in pedacos
    )
    capa = ('<header class="capa"><h1>Apostila — Analista Educacional: Orientador Educacional</h1>'
            '<p>Fundação Escola Técnica Liberato Salzano Vieira da Cunha · Concurso Público 001/2026 · Banca: Legalle Concursos</p>'
            '<p>Prova teórico-objetiva (data provável): 07/03/2027 · 60 questões: Português (10) · Legislação (10) · Específicos (40)</p>'
            '<p>Versão inicial: tópicos de cada ponto do programa (Anexo II) e textos legais transcritos das fontes oficiais. '
            'Redações revogadas foram omitidas; as notas de alteração aparecem em cinza.</p></header>')
    pagina = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Apostila Orientador Educacional</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<style>{CSS}</style><script>{JS}</script></head>
<body><div class="wrap">{nav()}<main>{capa}{corpo}</main></div></body></html>"""
    SAIDA.write_text(pagina, encoding="utf-8")
    (RAIZ / "index.html").write_text(pagina, encoding="utf-8")   # página do GitHub Pages
    print(f"gerado {SAIDA} ({SAIDA.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
