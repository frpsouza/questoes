"""Gera apostilas/supervisor-escolar.html.

Os artigos de lei são extraídos *ipsis litteris* dos textos oficiais em
legislacao/md/ (convertidos de Planalto, AL-RS, MEC e CEEd-RS). Redações
revogadas (texto riscado nas versões compiladas) são omitidas, e fica só a
redação vigente com as notas de alteração ("Redação dada pela...").

Uso:  python apostilas/gerar_supervisor.py
"""
import html
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MD = RAIZ / "legislacao" / "md"
SAIDA = RAIZ / "apostilas" / "supervisor-escolar.html"

# ---------------------------------------------------------------- extração --

RE_ART = re.compile(r"^Art\.\s*(\d+(?:\.\d+)?)(?:\s*(?:º|°|o\b))?(-[A-Z]{1,2}\b)?")
RE_HEAD = re.compile(r"^(T[ÍI]TULO|CAP[ÍI]TULO|Cap[íi]tulo|SE[ÇC][ÃA]O|Se[çc][ãa]o|SUBSE[ÇC][ÃA]O|Subse[çc][ãa]o|LIVRO|PARTE)\b")
RE_RUIDO = re.compile(r"^(https?://www\.al\.rs\.gov\.br\S*|\d{1,3}|#?\s*ESTADO DO RIO GRANDE DO SUL ASSEMBLEIA LEGISLATIVA.*)$")
RE_NOTA = re.compile(
    r"\((?:Redação dada|Incluíd[oa]|Acrescid[oa]|Vide|Vigência|Revogad[oa]|Renumerad[oa]|Produção de efeito|Regulamento|"
    r"Regulamenta|Promulgação|Expressão|Parágrafo|Inciso|Alínea|Artigo|Texto|Vetado|VETADO)[^()]*(?:\([^()]*\)[^()]*)*\)"
)

_cache: dict[str, list[str]] = {}


def limpar(bloco: str) -> str:
    b = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", bloco)            # imagens
    b = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", b)             # links -> texto
    b = re.sub(r"<[^>]+>", "", b)                              # <u>, <br> etc.
    b = b.replace("^(o)", "º").replace("^(a)", "ª")
    b = "\n".join(l.strip() for l in b.splitlines()).strip()
    return "" if re.fullmatch(r"[\\*\s]*", b) else b


def blocos(arquivo: str) -> list[str]:
    if arquivo not in _cache:
        txt = (MD / arquivo).read_text(encoding="utf-8")
        out = []
        for b in re.split(r"\n\s*\n", txt):
            b = "\n".join(l for l in b.splitlines() if not RE_RUIDO.match(l.strip()))
            # descarta redação revogada: bloco que, sem o texto riscado e as notas, fica vazio
            if "~~" in b:
                resto = RE_NOTA.sub("", limpar(re.sub(r"~~.*?~~", "", b, flags=re.S)))
                if len(re.sub(r"[^A-Za-zÀ-ú]", "", resto)) < 3:
                    continue
                b = re.sub(r"~~.*?~~", "", b, flags=re.S)
            b = limpar(b)
            if b and b != "[TABLE]":
                out.append(b)
        _cache[arquivo] = out
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
    res, ant_tit = [], False
    for b in bl[j:]:
        c = chave(b)
        if c is not None and c > kf:
            break
        t = c is None and eh_titulo(b, ant_tit or RE_HEAD.match(b.replace("*", "").strip()) is not None)
        res.append(("tit" if t else "txt", b))
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
    return _todos(bl[i0:])


def _todos(bl):
    res, ant = [], False
    for b in bl:
        t = chave(b) is None and eh_titulo(b, ant)
        res.append(("tit" if t else "txt", b))
        ant = t
    return res


def linhas_entre(arquivo: str, inicio: str, fim_regex: str) -> str:
    txt = (MD / arquivo).read_text(encoding="utf-8")
    i = txt.index(inicio)
    m = re.compile(fim_regex, re.M).search(txt, i + len(inicio))
    return txt[i: m.start() if m else None]


# --------------------------------------------------------------- render md --

def md_lei(partes: list[tuple[str, str]]) -> str:
    out = []
    for tipo, b in partes:
        if tipo == "tit":
            out.append(f"::: tit\n{b.replace('*', '')}\n:::")
        else:
            b = re.sub(r"^\*{0,2}(Art\.\s*[\d.]+(?:\s*(?:º|°|o\b))?(?:-[A-Z]{1,2}\b)?\.?)\*{0,2}", r"**\1**", b)
            b = RE_NOTA.sub(lambda m: f"[{m.group(0)}]{{.nota}}", b)
            out.append(b)
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

def parte_portugues():
    return f"""
# Parte I — Língua Portuguesa {{#pt}}

<p class="meta">10 questões · 1,00 ponto cada · mínimo de 5 acertos</p>

## a) Leitura e compreensão de textos {{#pt-a}}

{topicos("Assunto, tema e tese; estruturação do texto (introdução, desenvolvimento, conclusão)",
"Ideias principais e secundárias; relação entre as ideias (causa, consequência, oposição, concessão, conclusão)",
"Efeitos de sentido; figuras de linguagem (metáfora, metonímia, ironia, eufemismo, hipérbole, antítese, paradoxo, personificação)",
"Recursos de argumentação (exemplificação, autoridade, dados, comparação, contra-argumentação)",
"Informações implícitas: pressupostos (marcados linguisticamente) × subentendidos (inferidos do contexto)",
"Coesão (referencial, sequencial, lexical) e coerência textual")}

## b) Léxico {{#pt-b}}

{topicos("Significação de palavras e expressões no texto (sentido denotativo × conotativo)",
"Substituição de palavras e expressões mantendo sentido e correção",
"Estrutura e formação de palavras: radical, afixos, desinências; derivação e composição",
"Sinônimos, antônimos, parônimos e homônimos")}

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
"""


def parte_legislacao():
    s = """
# Parte II — Legislação {#leg}

<p class="meta">10 questões · 1,00 ponto cada · mínimo de 5 acertos. Textos transcritos <em>ipsis litteris</em> das fontes oficiais. Clique em cada quadro para abrir o texto legal.</p>

<p class="meta">Ordem de estudo sugerida (do geral ao específico): <a href="#leg-c">Constituição</a> → <a href="#leg-j">LDB</a> → <a href="#leg-l">BNCC</a> → <a href="#leg-k">PNEPT</a> → <a href="#leg-m">ECA</a> → <a href="#leg-h">LBI</a> → <a href="#leg-e">igualdade racial</a> → <a href="#leg-g">Maria da Penha</a> → <a href="#leg-i">LGPD</a> → <a href="#leg-a">Liberato</a> → <a href="#leg-d">CLT</a>.</p>
"""
    s += f"""
## a) Lei RS nº 14.498/2014 — Plano de Empregos, Funções e Salários da Fundação Liberato {{#leg-a}}

{topicos("Estrutura do Plano: quadro de empregos permanentes, empregos e funções em comissão",
"Emprego de Analista Educacional e a ocupação de **Supervisor Escolar** (número de vagas, padrão salarial)",
"Jornada de trabalho e carga horária; atribuições; promoção e avaliação de desempenho")}
{LI("Lei nº 14.498, de 3 de abril de 2014 — íntegra", "rs-lei14498-pefs-liberato.md")}

## b) Estatuto da Fundação Liberato (Decreto nº 18.446/1967, alterado pelo Decreto nº 52.101/2014) {{#leg-b}}

{topicos("Natureza jurídica (pessoa jurídica de direito privado), sede e regência (Estatuto, Regimento Geral, Resoluções do Conselho Técnico Deliberativo)",
"Finalidades da Fundação (art. 3º): educação profissional e tecnológica; pesquisa e inovação",
"Patrimônio, rendas e aplicação de recursos (art. 5º)")}

<p class="aviso">O texto integral do Decreto 18.446/1967 não está disponível em meio digital no LEGIS/AL-RS. Abaixo está a íntegra do Decreto 52.101/2014, que dá nova redação aos dispositivos alterados do Estatuto.</p>
{LI("Decreto nº 52.101, de 27 de novembro de 2014 — íntegra", "rs-dec52101-estatuto-liberato.md")}

## c) Constituição Federal de 1988 — art. 37 e arts. 205 a 214 {{#leg-c}}

{topicos("Art. 37: princípios da Administração Pública (legalidade, impessoalidade, moralidade, publicidade, eficiência); concurso público; acumulação de cargos",
"Art. 205: educação como direito de todos e dever do Estado e da família; finalidades",
"Art. 206: princípios do ensino (inclusive gestão democrática e valorização dos profissionais)",
"Art. 207: autonomia universitária · Art. 208: deveres do Estado com a educação",
"Arts. 209 a 211: ensino privado, conteúdos mínimos, regime de colaboração",
"Arts. 212 a 214: financiamento (vinculação de receitas, Fundeb) e Plano Nacional de Educação")}
{L("CF/88 — Art. 37 (Administração Pública)", "cf88.md", ("37",))}
{L("CF/88 — Arts. 205 a 214 (Da Educação)", "cf88.md", ("205", "214"))}

## d) CLT — Jornada, descanso e férias {{#leg-d}}

{topicos("Cap. II, Seção II — Da Jornada de Trabalho (arts. 58 a 65): duração normal, tempo parcial, horas extras, compensação, banco de horas, 12×36",
"Cap. II, Seção III — Dos Períodos de Descanso (arts. 66 a 72): interjornada (11 h), descanso semanal, intervalo intrajornada",
"Cap. IV, Seção I — Do Direito a Férias e da sua Duração (arts. 129 a 133)",
"Cap. IV, Seção II — Da Concessão e da Época das Férias (arts. 134 a 138): fracionamento em até 3 períodos (Reforma Trabalhista, Lei 13.467/2017)")}
{L("CLT — Arts. 58 a 72 (Jornada e Descanso)", "clt-del5452.md", ("58", "72"))}
{L("CLT — Arts. 129 a 138 (Férias)", "clt-del5452.md", ("129", "138"))}

## e) Lei nº 12.288/2010 — Estatuto da Igualdade Racial {{#leg-e}}

{topicos("Conceitos (art. 1º): discriminação racial, desigualdade racial, desigualdade de gênero e raça, população negra, políticas públicas, ações afirmativas",
"Deveres do Estado e da sociedade (arts. 2º a 4º)",
"Direito à educação (arts. 11 a 16): ensino de história geral da África e da população negra no Brasil (LDB art. 26-A)",
"Trabalho, cultura, esporte, lazer, liberdade religiosa e SINAPIR")}
{LI("Lei nº 12.288, de 20 de julho de 2010 — íntegra", "lei12288-estatuto-igualdade-racial.md")}

## f) Lei RS nº 13.694/2011 — Estatuto Estadual da Igualdade Racial {{#leg-f}}

{topicos("Estatuto Estadual da Igualdade Racial e de Combate à Intolerância Religiosa",
"Diretrizes das políticas públicas estaduais; educação, saúde, cultura, comunidades quilombolas")}
{LI("Lei nº 13.694, de 19 de janeiro de 2011 — íntegra", "rs-lei13694-igualdade-racial-rs.md")}

## g) Lei nº 11.340/2006 — Lei Maria da Penha {{#leg-g}}

{topicos("Objeto e direitos fundamentais da mulher (arts. 1º a 4º)",
"Conceito de violência doméstica e familiar e formas de violência: física, psicológica, sexual, patrimonial e moral (arts. 5º a 7º)",
"Medidas integradas de prevenção, inclusive conteúdos nos currículos escolares (art. 8º)",
"Assistência à mulher em situação de violência (art. 9º)")}
{L("Lei nº 11.340/2006 — Arts. 1º a 9º", "lei11340-maria-da-penha.md", ("1", "9"))}

## h) Lei nº 13.146/2015 — Lei Brasileira de Inclusão (Estatuto da Pessoa com Deficiência) {{#leg-h}}

{topicos("Conceito de pessoa com deficiência e avaliação biopsicossocial (art. 2º)",
"Definições: acessibilidade, desenho universal, tecnologia assistiva, barreiras, adaptações razoáveis, profissional de apoio escolar (art. 3º)",
"Igualdade e não discriminação (arts. 4º a 8º)",
"Direito à educação: sistema educacional inclusivo em todos os níveis; incumbências do poder público; vedação de cobrança adicional pelas escolas privadas (arts. 27 a 30)")}
{L("Lei nº 13.146/2015 — Arts. 1º a 8º (Disposições gerais; igualdade e não discriminação)", "lei13146-lbi.md", ("1", "8"))}
{L("Lei nº 13.146/2015 — Arts. 27 a 30 (Do Direito à Educação)", "lei13146-lbi.md", ("27", "30"))}

## i) Lei nº 13.709/2018 — LGPD {{#leg-i}}

{topicos("Objetivo e fundamentos (arts. 1º e 2º); aplicação (arts. 3º e 4º)",
"Conceitos (art. 5º): dado pessoal, dado sensível, titular, controlador, operador, encarregado, tratamento, consentimento",
"Princípios (art. 6º): finalidade, adequação, necessidade, livre acesso, qualidade, transparência, segurança, prevenção, não discriminação, responsabilização",
"Bases legais do tratamento (art. 7º); dados sensíveis (art. 11); **dados de crianças e adolescentes (art. 14)** — relevante para a escola")}
{L("LGPD — Arts. 1º a 7º", "lei13709-lgpd-compilada.md", ("1", "7"))}
{L("LGPD — Art. 11 (dados pessoais sensíveis)", "lei13709-lgpd-compilada.md", ("11",))}
{L("LGPD — Art. 14 (dados de crianças e adolescentes)", "lei13709-lgpd-compilada.md", ("14",))}

## j) Lei nº 9.394/1996 — LDB (com as Leis 14.533/2023 e 14.811/2024) {{#leg-j}}

{topicos("Títulos I a III: conceito de educação, princípios e fins (arts. 1º a 3º); direito à educação e dever de educar (arts. 4º a 7º-A)",
"Título IV: organização da educação nacional; incumbências da União, estados, municípios, **estabelecimentos de ensino (art. 12)** e **docentes (art. 13)**; **gestão democrática (art. 14)**; autonomia (art. 15)",
"Título V, Cap. II: educação básica — disposições gerais (arts. 22 a 28): organização, calendário, **verificação do rendimento e frequência (art. 24)**, currículo e BNCC (art. 26), temas obrigatórios (26-A)",
"Ensino Médio (arts. 35 a 36) e **Educação Profissional Técnica de Nível Médio (arts. 36-A a 36-D)**; Educação Profissional e Tecnológica (arts. 39 a 42)",
"Educação Especial (arts. 58 a 60) · Educação Digital (art. 4º, XII; art. 26, § 11, entre outros — Lei 14.533/2023)",
"Título VI: **profissionais da educação (arts. 61 a 67)** — formação de especialistas em supervisão (art. 64)",
"Lei 14.811/2024: medidas de proteção contra a violência em estabelecimentos educacionais")}
{L("LDB — íntegra (texto compilado vigente)", "lei9394-ldb.md", ("1", "92"), ident="ldb-integral")}
{LI("Lei nº 14.533, de 11 de janeiro de 2023 — Política Nacional de Educação Digital — íntegra", "lei14533-educacao-digital.md")}
{LI("Lei nº 14.811, de 12 de janeiro de 2024 — Proteção contra a violência nos estabelecimentos educacionais — íntegra", "lei14811-seguranca-escolar.md")}

## k) Decreto nº 12.603/2025 — Política Nacional de Educação Profissional e Tecnológica (PNEPT) {{#leg-k}}

{topicos("Objeto: institui a PNEPT, regulamenta o art. 4º da Lei 14.645/2023 e institui o SINAEPT",
"Princípios, objetivos (art. 4º) e eixos (art. 5º) da PNEPT",
"Governança: Comissão Tripartite Paritária Permanente (CTPP); sistemas de informação e avaliação")}
{LI("Decreto nº 12.603, de 28 de agosto de 2025 — íntegra", "dec12603-pnept.md")}

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
                   [("txt", b.strip()) for b in re.split(r"\n\s*\n", comp) if b.strip()])
    s += f"""
## m) Lei nº 8.069/1990 — Estatuto da Criança e do Adolescente {{#leg-m}}

{topicos("Disposições preliminares: proteção integral, conceito de criança e adolescente, prioridade absoluta (arts. 1º a 6º)",
"Direito à liberdade, ao respeito e à dignidade; educação sem castigo físico ou tratamento cruel (arts. 15 a 18-B)",
"**Direito à educação, à cultura, ao esporte e ao lazer (arts. 53 a 59)** — dever dos dirigentes de comunicar ao Conselho Tutelar (art. 56)",
"Prevenção: políticas contra violência e castigo físico (arts. 70-A e 70-B)",
"Medidas de proteção (arts. 98 a 101) · Conselho Tutelar (arts. 131 a 137) · infração administrativa do art. 245")}
{L("ECA — Arts. 1º a 6º", "lei8069-eca.md", ("1", "6"))}
{L("ECA — Arts. 15 a 18-B", "lei8069-eca.md", ("15", "18-B"))}
{L("ECA — Arts. 53 a 59 (Do Direito à Educação, à Cultura, ao Esporte e ao Lazer)", "lei8069-eca.md", ("53", "59"))}
{L("ECA — Arts. 70-A e 70-B", "lei8069-eca.md", ("70-A", "70-B"))}
{L("ECA — Arts. 98 a 101 (Medidas de proteção)", "lei8069-eca.md", ("98", "101"))}
{L("ECA — Arts. 131 a 137 (Conselho Tutelar)", "lei8069-eca.md", ("131", "137"))}
{L("ECA — Art. 245", "lei8069-eca.md", ("245",), )}
"""
    return s


def parte_especificos():
    LDB = "lei9394-ldb.md"
    return f"""
# Parte III — Conhecimentos Específicos: Supervisor Escolar {{#esp}}

<p class="meta">40 questões · 1,75 ponto cada · mínimo de 20 acertos (70% da nota total)</p>

## a) Pensadores da educação e história da educação {{#esp-a}}

{topicos("Antiguidade e Idade Média: paideia grega (Sócrates, Platão, Aristóteles); escolástica",
"Modernidade: Comenius (*Didática Magna*), Rousseau (*Emílio*), Pestalozzi, Herbart, Froebel",
"Escola Nova: Dewey, Montessori, Decroly, Claparède, Freinet; no Brasil, Anísio Teixeira e o Manifesto dos Pioneiros (1932)",
"Pedagogias críticas: Paulo Freire, Saviani (pedagogia histórico-crítica), Libâneo (crítico-social dos conteúdos)",
"Tendências pedagógicas liberais (tradicional, renovada progressivista e não diretiva, tecnicista) e progressistas (libertadora, libertária, crítico-social dos conteúdos)",
"História da educação brasileira: jesuítas, reformas pombalinas, Império, República, LDBs de 1961, 1971 e 1996")}

## b) Elementos da prática pedagógica {{#esp-b}}

{topicos("Planejamento escolar e planejamento de aula: níveis (sistema, escola, currículo, ensino, aula)",
"Currículo: formal, real, oculto; organização curricular",
"Regimento escolar: natureza, conteúdo e relação com o PPP",
"Metodologias de ensino, projetos de trabalho e técnicas didáticas",
"Avaliação da aprendizagem",
"Formação docente")}
{L("Base legal — LDB, arts. 12 e 13 (incumbências da escola e dos docentes)", LDB, ("12", "13"))}
{L("Base legal — LDB, arts. 23 e 24 (organização e verificação do rendimento)", LDB, ("23", "24"))}

## c) Teorias do conhecimento e da aprendizagem {{#esp-c}}

{topicos("Empirismo, inatismo (apriorismo) e interacionismo/construtivismo",
"Comportamentalismo (Skinner, Watson): condicionamento e reforço",
"Epistemologia genética (Piaget): assimilação, acomodação, equilibração",
"Sociointeracionismo (Vygotsky): mediação, ZDP, internalização, linguagem",
"Teoria psicogenética de Wallon: afetividade, emoção, movimento",
"Aprendizagem significativa (Ausubel); aprendizagem por descoberta (Bruner)",
"Concepções pedagógicas decorrentes e implicações para a supervisão")}

## d) Projeto político-pedagógico e proposta pedagógica da Fundação Liberato. Gestão democrática {{#esp-d}}

{topicos("PPP: conceito, dimensões política e pedagógica, princípios (Veiga), etapas de elaboração (marco referencial, diagnóstico, programação — Gandin/Vasconcelos)",
"Proposta pedagógica da Fundação Liberato: ler o PPP institucional publicado em liberato.com.br",
"Gestão democrática: participação, Conselho Escolar, autonomia (administrativa, financeira e pedagógica)",
"Relação PPP × Regimento × Planos de Ensino")}
{L("Base legal — CF/88, art. 206 (princípios do ensino; gestão democrática)", "cf88.md", ("206",), )}
{L("Base legal — LDB, arts. 3º, 12, 13, 14 e 15", LDB, ("3",), ("12", "15"))}

## e) Tipos de conhecimento; desenvolvimento cognitivo; competências; inteligências múltiplas; o lúdico {{#esp-e}}

{topicos("Tipos de conhecimento: senso comum, científico, filosófico, teológico/religioso, artístico",
"Estágios do desenvolvimento cognitivo (Piaget): sensório-motor, pré-operatório, operatório-concreto, operatório-formal",
"Competências e capacidades: conceito (Perrenoud; BNCC — mobilização de conhecimentos, habilidades, atitudes e valores)",
"Inteligências múltiplas (Gardner): linguística, lógico-matemática, espacial, corporal-cinestésica, musical, interpessoal, intrapessoal, naturalista",
"O lúdico na educação: jogo, brincadeira e aprendizagem (Kishimoto, Vygotsky, Piaget)")}
<p class="ref">Ver também: <a href="#leg-l">BNCC — competências gerais</a>.</p>

## f) Educação inclusiva; dificuldades e transtornos de aprendizagem; tecnologias; metodologias ativas {{#esp-f}}

{topicos("Educação inclusiva: paradigma da inclusão × integração; AEE; Política Nacional de Educação Especial na Perspectiva da Educação Inclusiva (2008)",
"Dificuldades × transtornos de aprendizagem: dislexia, disgrafia, discalculia, TDAH; papel da escola e encaminhamentos",
"Recursos tecnológicos e educação: educação digital, cultura digital, ensino híbrido",
"Metodologias ativas: sala de aula invertida, aprendizagem baseada em projetos (ABP), em problemas, rotação por estações, gamificação, peer instruction")}
{L("Base legal — LDB, arts. 58 a 60 (Educação Especial)", LDB, ("58", "60"))}
{L("Base legal — LBI, arts. 27 e 28 (Direito à Educação)", "lei13146-lbi.md", ("27", "28"))}
{LI("Base legal — Lei nº 14.254/2021 (dislexia, TDAH e outros transtornos de aprendizagem) — íntegra", "lei14254-dislexia-tdah.md")}
{L("Base legal — Lei nº 14.533/2023, arts. 1º a 3º (Política Nacional de Educação Digital; educação digital escolar)", "lei14533-educacao-digital.md", ("1", "3"))}

## g) Fundamentos e práticas da Supervisão Escolar {{#esp-g}}

<p class="autores">Autores sugeridos: Antonia da Silva Medina · Heloísa Lück · Mary Rangel</p>

{topicos("Aspectos históricos: origem fabril/taylorista da supervisão; inspeção escolar; PABAEE; Lei 5.692/1971 e Parecer CFE 252/1969 (habilitações); crítica à divisão do trabalho na escola",
"Aspectos legais: formação do supervisor (LDB art. 64); profissionais da educação (LDB art. 61)",
"Aspectos culturais e conceitos: supervisão como controle × supervisão como mediação/acompanhamento pedagógico",
"Áreas de atuação e propostas relacionadas aos diferentes modelos pedagógicos",
"O supervisor como especialista e articulador do trabalho pedagógico (Medina: o trabalho com o professor e a produção do professor)",
"Ação integrada entre supervisão, orientação e administração escolar na elaboração, construção e execução do PPP (Lück; Rangel)")}
{L("Base legal — LDB, arts. 61 e 64", LDB, ("61",), ("64",))}

## h) Formação docente e prática reflexiva {{#esp-h}}

<p class="autores">Autores sugeridos: Isabel Alarcão · Philippe Perrenoud · Terezinha Azerêdo Rios · Léopold Paquay</p>

{topicos("A ação supervisora e a formação continuada de professores: perspectiva histórica (“ontem e hoje” — Alarcão)",
"Bases epistemológicas e pedagógicas da ação docente",
"Formação crítica e reflexiva: professor reflexivo, escola reflexiva (Alarcão); reflexão na ação, sobre a ação e sobre a reflexão na ação (Schön)",
"Novas competências para ensinar (Perrenoud) e profissionalização do ofício de professor (Paquay, Perrenoud et al.)",
"Dimensões da competência docente: técnica, estética, ética e política (Terezinha Rios)",
"A didática como área de atuação da supervisão na formação em serviço",
"Avaliação docente")}
{L("Base legal — LDB, arts. 61 a 67 (Dos Profissionais da Educação)", LDB, ("61", "67"))}

## i) Organização curricular e metodologias de ensino {{#esp-i}}

<p class="autores">Autores sugeridos: José Carlos Libâneo · Juan Díaz Bordenave · Edgar Morin · Monica Gather Thurler</p>

{topicos("Reflexões sobre currículo: interdisciplinaridade, multidisciplinaridade, pluridisciplinaridade, transdisciplinaridade (Morin: *Os sete saberes*; pensamento complexo)",
"Aplicação da LDB, da BNCC, dos PCNs e do Referencial Curricular Gaúcho do Ensino Médio (RCGEM) na prática supervisora",
"Fundamentos teóricos e dimensões político-sociais da Didática (Libâneo)",
"Estratégias de ensino-aprendizagem (Bordenave & Pereira)",
"Inovação e mudança na escola (Gather Thurler)",
"Metodologias ativas, técnicas de ensino e integração de recursos tecnológicos ao currículo")}
{L("Base legal — LDB, arts. 26, 26-A e 27 (currículo da educação básica)", LDB, ("26", "27"))}
{L("Base legal — LDB, arts. 35 a 36-D (Ensino Médio e Educação Profissional Técnica de Nível Médio)", LDB, ("35", "36-D"))}
{LI("Base legal — Resolução CEEd-RS nº 365/2021 (normas complementares para o Ensino Médio no RS; Referencial Curricular Gaúcho) — íntegra", "ceed-rs-resolucao-365-2021.md")}
<p class="ref">Ver também: <a href="#leg-l">BNCC — competências gerais</a>.</p>

## j) Planejamento pedagógico e rotina escolar {{#esp-j}}

<p class="autores">Autores sugeridos: Danilo Gandin · Celso dos Santos Vasconcelos</p>

{topicos("O processo de planejamento em suas diferentes dimensões",
"Planejamento estratégico participativo (Gandin): marco referencial, diagnóstico, programação",
"Elaboração do projeto pedagógico de curso (PPC) integrado; planos de ensino e planos de aula (Vasconcelos)",
"Modalidades organizativas do trabalho pedagógico (atividades permanentes, sequências didáticas, projetos)",
"Registros das atividades docentes (diários de classe) e sua conferência pela supervisão",
"Organização e liderança do Conselho de Classe; atuação do supervisor perante as turmas")}
{L("Base legal — LDB, art. 24 (frequência mínima, recuperação, registros)", LDB, ("24",))}
{L("Base legal — ECA, art. 56 (comunicação ao Conselho Tutelar)", "lei8069-eca.md", ("56",))}

## k) Avaliação da aprendizagem e institucional {{#esp-k}}

<p class="autores">Autores sugeridos: Jussara Hoffmann · Cipriano Luckesi</p>

{topicos("Dimensões da avaliação no processo de ensino-aprendizagem: diagnóstica, formativa, somativa",
"Função social da avaliação escolar; avaliação classificatória × diagnóstica (Luckesi)",
"Concepção dialética-libertadora (Vasconcelos); avaliação mediadora e formativa — “avaliar para promover” (Hoffmann)",
"A relação intrínseca entre planejamento e avaliação",
"Avaliação institucional e avaliações externas (SAEB, ENEM, SINAEPT)",
"Pressupostos teóricos da pesquisa na ação supervisora")}
{L("Base legal — LDB, art. 9º (avaliação nacional do rendimento escolar)", LDB, ("9",))}
<p class="ref">Ver também: <a href="#esp-j">LDB, art. 24</a>.</p>
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
details.lei>summary{cursor:pointer;padding:10px 0;font:600 15px/1.4 system-ui,sans-serif;color:var(--accent)}
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
    esp = [("esp-a", "a) Pensadores e história"), ("esp-b", "b) Prática pedagógica"), ("esp-c", "c) Teorias da aprendizagem"),
           ("esp-d", "d) PPP e gestão democrática"), ("esp-e", "e) Cognição e competências"), ("esp-f", "f) Inclusão e tecnologias"),
           ("esp-g", "g) Supervisão escolar"), ("esp-h", "h) Formação docente"), ("esp-i", "i) Currículo e metodologias"),
           ("esp-j", "j) Planejamento e rotina"), ("esp-k", "k) Avaliação")]
    def bloco(t, ancora, itens):
        return f'<h2><a href="#{ancora}">{t}</a></h2>' + "".join(f'<a href="#{a}">{n}</a>' for a, n in itens)
    return ('<nav><div class="tools"><button onclick="todos(true)">Abrir leis</button>'
            '<button onclick="todos(false)">Fechar leis</button><button onclick="tema()">Tema</button></div>'
            + bloco("I · Português", "pt", pt) + bloco("II · Legislação", "leg", leg)
            + bloco("III · Específicos", "esp", esp) + "</nav>")


def main():
    md = parte_portugues() + parte_legislacao() + parte_especificos()
    corpo = subprocess.run(
        ["pandoc", "+RTS", "-K512m", "-RTS", "-f", "markdown-fancy_lists-example_lists-implicit_figures-tex_math_dollars-subscript-superscript",
         "-t", "html5", "--wrap=none"],
        input=md.encode("utf-8"), capture_output=True, check=True,
    ).stdout.decode("utf-8")
    capa = ('<header class="capa"><h1>Apostila — Analista Educacional: Supervisor Escolar</h1>'
            '<p>Fundação Escola Técnica Liberato Salzano Vieira da Cunha · Concurso Público 001/2026 · Banca: Legalle Concursos</p>'
            '<p>Prova teórico-objetiva (data provável): 07/03/2027 · 60 questões: Português (10) · Legislação (10) · Específicos (40)</p>'
            '<p>Versão inicial: tópicos de cada ponto do programa (Anexo II) e textos legais transcritos das fontes oficiais. '
            'Redações revogadas foram omitidas; as notas de alteração aparecem em cinza.</p></header>')
    pagina = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Apostila Supervisor Escolar</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<style>{CSS}</style><script>{JS}</script></head>
<body><div class="wrap">{nav()}<main>{capa}{corpo}</main></div></body></html>"""
    SAIDA.write_text(pagina, encoding="utf-8")
    print(f"gerado {SAIDA} ({SAIDA.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
