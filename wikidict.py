from typing import List, Tuple, Optional
import re
import html
import requests
import random

VOWELS = "aeiouy"
CONSONANTS = "bcdfghjklmnpqrstvwz"
WIKI_ENDPOINT = "https://en.wiktionary.org/w/index.php?title=Category%3AFrench_lemmas&printable=yes&pagefrom={}"


def random_tag() -> str:
    if random.random() > 0.88:
        return random.choice(VOWELS)
    else:
        return random.choice(CONSONANTS) + random.choice(VOWELS)


def simplify(words: List[str]) -> List[str]:
    rm_candidates = []
    for word in words:
        conditions_for_rm = [
            len(word) < 3,
            word.isupper(),
            word[0].isupper(),
            word[0] == "-",
            word[-1] == "-",
            word[-4:] == "ment",
            word.count(" ") > 2,
        ]
        if True in conditions_for_rm:
            rm_candidates += [word]
    return [word for word in words if word not in rm_candidates]


def get_random_word() -> Tuple[str, str]:
    r = requests.get(WIKI_ENDPOINT.format(random_tag()))

    words = {}
    start_after = '<li><a href="/wiki/Category:French_verbs"'
    found = False

    for line in r.content.decode().split("\n"):
        if found and line.startswith('<li><a href="/wiki/'):
            tmp = line[19 : line.find("</a>")]
            word = tmp[tmp.find(">") + 1 :]
            URL = tmp[0 : tmp.find('"')]
            words[word] = URL
        if line.startswith(start_after):
            found = True

    word = random.choice(simplify(list(words.keys())))
    return word, words[word]


def remove_html(raw_html: str) -> str:
    cleanr = re.compile("<.*?>")
    return re.sub(cleanr, "", raw_html)


def get_definition(url) -> Optional[str]:
    r = requests.get(
        "https://fr.wiktionary.org/w/index.php?title={}&printable=yes".format(url)
    )
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
        word, url = get_random_word()
        definition = get_definition(url)
        if definition is not None:
            if definition.find("Variante") != -1 or len(definition.split(" ")) < 5:
                definition = None
    definition = html.unescape(remove_citation(definition))
    print(word, url)
    return html.unescape(word), definition
