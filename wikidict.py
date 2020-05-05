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


class Wiki:
    def __init__(self, lang, category, estimated):
        self.lang = lang
        self.list_file = f"wikidict.{lang}.txt"
        self.api_endpoint = f"https://{lang}.wiktionary.org/w/api.php"
        self.category = category
        self.estimated = estimated


WIKIS = {
    "fr": Wiki("fr", "Catégorie:Lemmes_en_français", 203164),
    "en": Wiki("en", "Category:English_lemmas", 468304),
}

LANG = "fr"  # TODO temporary


def create_list_file(lang):
    print("loading from API...")
    params = {
        "format": "json",
        "action": "query",
        "list": "categorymembers",
        "cmtitle": WIKIS[lang].category,
        "cmlimit": "500",
    }
    cont_key = None
    start = True
    count = 0
    with open(WIKIS[lang].list_file, mode="w", encoding="utf8") as f:
        while start or cont_key is not None:
            start = False
            if cont_key is not None:
                params["cmcontinue"] = cont_key
            response = requests.get(url=WIKIS[lang].api_endpoint, params=params)
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
            progress = count / WIKIS[lang].estimated
            print(
                "{}[{}{}]".format(
                    "\r" * 66,
                    "=" * (math.floor(progress * 64)),
                    " " * (64 - math.floor(progress * 64)),
                ),
                end="",
            )
        print()


def load_list(lang) -> List[str]:
    if not os.path.exists(WIKIS[lang].list_file):
        create_list_file(lang)
    with open(WIKIS[lang].list_file, mode="r", encoding="utf8") as f:
        return [word.strip() for word in f.readlines() if len(word.strip()) > 0]


print("loading wiktionary words...")
WORDS = load_list(LANG)  # TODO temporary
print(f"loaded {len(WORDS)} words")

# DEFINITION FETCHER

def remove_ref(raw_html: str) -> str:
    cleanr = re.compile("<ref>.*?</ref>")
    return re.sub(cleanr, "", raw_html)

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
    return '`' + remove_ref("".join(chunks_out).replace("'''", "**").replace("''", "*")[2:]) + '`'


def get_random_word() -> str:
    return random.choice(WORDS)


def get_definition(word, lang) -> Optional[str]:
    params = {
        "format": "json",
        "action": "parse",
        "prop": "wikitext",
        "page": word
    }  # &prop=sections
    r = requests.get(url=WIKIS[lang].api_endpoint, params=params)
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
        definition = get_definition(word, LANG)  # TODO temporary
    definition = html.unescape(definition)
    return html.unescape(word), definition
