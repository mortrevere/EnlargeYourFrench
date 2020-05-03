from typing import List, Tuple, Optional
import re
import html
import requests
import random
import os
import math

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
        "cmlimit": "500"
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
                    word = word['title']
                    if not (
                            len(word) < 3 or
                            word[0].isupper() or
                            word[0].isdigit() or
                            word[-4:] == "ment" or
                            word.count(" ") > 2 or
                            re.match(r"^\w.*\w$", word) is None  # first and last char must be word letters
                    ):
                        f.write(word + "\n")
                        count += 1
            progress = count/60511 #total entries on 03/05/2020
            print("{}[{}{}]".format('\r'*66, '='*(math.floor(progress*64)), ' '*(64-math.floor(progress*64))), end='')


def load_list() -> List[str]:
    if not os.path.exists(LIST_FILE):
        create_list_file()
    with open(LIST_FILE, mode="r", encoding="utf8") as f:
        return [word.strip() for word in f.readlines() if len(word.strip()) > 0]


print("loading wiktionary words...")
WORDS = load_list()
print(f"loaded {len(WORDS)} words")


def get_random_word() -> str:
    return random.choice(WORDS)


def remove_html(raw_html: str) -> str:
    cleanr = re.compile("<.*?>")
    return re.sub(cleanr, "", raw_html)


def get_definition(word) -> Optional[str]:
    params = {
        "title": word,
        "printable": "yes"
    }
    r = requests.get(url=WIKI_ENDPOINT_FR, params=params)
    # print(r.content.decode())
    result = re.search("<ol>(.*)</ol>", r.content.decode().replace("\n", ""))
    if not result:
        return None
    return remove_html(result.group(1))


def remove_citation(text: str) -> str:
    cleanr = re.compile("\.(.*)—&#160;\((.*)\)")
    return remove_crap(re.sub(cleanr, ".", text))


def remove_crap(text: str) -> str:
    return text[0 : text.find(".") + 1]
    cleanr = re.compile("\.(.*)\(")
    return re.sub(cleanr, "\n(", text)


def get_word_and_definition() -> Tuple[str, str]:
    success = False
    definition = None
    word, url = None, None
    while definition is None:
        success = True
        word = get_random_word()
        definition = get_definition(word)
        if definition is not None:
            if definition.find("Variante") != -1 or len(definition.split(" ")) < 5:
                definition = None
    definition = html.unescape(remove_citation(definition))
    print(word, url)
    return html.unescape(word), definition
