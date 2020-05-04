from typing import List, Tuple, Optional
import re
import html
import requests
import random
import os
import math
import wikitextparser as wtp

VOWELS = "aeiouy"
CONSONANTS = "bcdfghjklmnpqrstvwz"
WIKI_ENDPOINT_EN = "https://en.wiktionary.org/w/api.php"
WIKI_ENDPOINT_FR = "https://fr.wiktionary.org/w/index.php"

LIST_FILE = "wikidict.txt"


def create_list_file():
    print("loading from API...")
    session = requests.Session()
    params = {
        "format": "json",
        "action": "query",
        "list": "categorymembers",
        "cmtitle": "Category:French_lemmas",
        "cmlimit": "500",
    }
    response = None
    data = None
    cont_key = None
    start = True
    count = 0
    with open(LIST_FILE, mode="w", encoding="utf8") as f:
        while start or cont_key is not None:
            start = False
            if cont_key is not None:
                params["cmcontinue"] = cont_key
            response = session.get(url=WIKI_ENDPOINT_EN, params=params)
            data = response.json()
            cont_key = None
            if "continue" in data and "cmcontinue" in data["continue"]:
                cont_key = data["continue"]["cmcontinue"]
            if "query" in data and "categorymembers" in data["query"]:
                for word in data["query"]["categorymembers"]:
                    word = word["title"]
                    if not (
                        len(word) < 3
                        or word[0].isupper()
                        or word[0].isdigit()
                        or word[-4:] == "ment"
                        or word.count(" ") > 2
                        or re.match(r"^\w.*\w$", word)
                        is None  # first and last char must be word letters
                    ):
                        f.write(word + "\n")
                        count += 1
            progress = count / 60511  # total entries on 03/05/2020
            print(
                "{}[{}{}]".format(
                    "\r" * 66,
                    "=" * (math.floor(progress * 64)),
                    " " * (64 - math.floor(progress * 64)),
                ),
                end="",
            )


def load_list() -> List[str]:
    if not os.path.exists(LIST_FILE):
        create_list_file()
    with open(LIST_FILE, mode="r", encoding="utf8") as f:
        return [word.strip() for word in f.readlines() if len(word.strip()) > 0]


print("loading wiktionary words...")
WORDS = load_list()
print(f"loaded {len(WORDS)} words")

# DEFINITION FETCHER


def render_wikitext(wikitext):
    wikidef = wtp.parse(wikitext)
    links = []
    templates = []

    # resolve links text
    for link in wikidef.wikilinks:
        content = link.text
        if not content:
            content = link.title
        links += [content]
    chunks = (
        wikitext.replace("[[", chr(1) + "[[").replace("]]", "]]" + chr(1)).split(chr(1))
    )
    chunks_out = []
    for chunk in chunks:
        if re.match("\[\[.*\]\]", chunk):
            chunks_out += [links.pop(0)]
        else:
            chunks_out += [chunk]
    wikitext = "".join(chunks_out)

    # resolve templates names
    for tmpl in wikidef.templates:
        content = tmpl.name
        if (len(tmpl.arguments) and tmpl.arguments[0].value in ("fr", "1")) or (
            len(tmpl.arguments) == 0 and len(tmpl.name) > 3
        ):
            templates += [f"({content.capitalize()})"]
        else:
            templates += [content]

    chunks = (
        wikitext.replace("{{", chr(1) + "{{").replace("}}", "}}" + chr(1)).split(chr(1))
    )
    chunks_out = []
    for chunk in chunks:
        if re.match("\{\{.*\}\}", chunk):
            chunks_out += [templates.pop(0)]
        else:
            chunks_out += [chunk]

    # return rendered text, adapted to markdown
    return "".join(chunks_out).replace("'''", "**").replace("''", "*")[2:]


def get_random_word() -> str:
    return random.choice(WORDS)


def remove_html(raw_html: str) -> str:
    cleanr = re.compile("<.*?>")
    return re.sub(cleanr, "", raw_html)


def get_definition(word) -> Optional[str]:
    URL = f"https://fr.wiktionary.org/w/api.php?action=parse&format=json&prop=wikitext&page={word}"  # &prop=sections
    r = requests.get(URL)
    if not r.json().get("parse"):
        return

    r = r.json()["parse"]["wikitext"]["*"]
    w = wtp.parse(r)
    definitions = []
    for section in w.sections:
        title = str(section.title).strip()
        if title and title[0:4] == "{{S|" and title.find("|fr") != -1:
            for line in str(section).split("\n"):
                if len(line) > 2 and line[0] == "#" and line[1] != "*":
                    definitions += [render_wikitext(line)]
    return "\n".join(definitions)


def get_word_and_definition() -> Tuple[str, str]:
    success = False
    definition = None
    word = None
    while definition is None:
        success = True
        word = get_random_word()
        definition = get_definition(word)
    definition = html.unescape(definition)
    return html.unescape(word), definition
