from typing import List, Tuple, Optional
import re
import html
import requests
import random
import os
import math
import wikitextparser as wtp
from loguru import logger
import time
import string
from fuzzywuzzy import fuzz

VOWELS = "aeiouy"
CONSONANTS = "bcdfghjklmnpqrstvwz"


class Wikidict():
    WIKIS = {
        "french-simple": {
            "tag": "simple.fr",
            "description": "Mots simples et régulièrement utilisés",
            "wiki_category": "Catégorie:Lemmes_en_français",
            "wiki_lang": "fr",
            "avoid-regex": [
                "^((Féminin|Masculin) (singulier|pluriel)|Pluriel) de .*",
                "^Participe passé.*",
                "^(Deuxième|Première|Troisième) personne du (singulier|pluriel).*"
            ]
        },
        "french-full": {
            "tag": "fr",
            "description": "Tout le dictionnaire ou presque",
            "wiki_category": "Catégorie:Lemmes_en_français",
            "wiki_lang": "fr",
            "avoid-regex": [
                "^Pluriel de .*",
                "^Participe passé.*",
                "^(Deuxième|Première|Troisième) personne du ((singulier|pluriel) (de l’indicatif présent|du présent du subjonctif) du verbe|singulier de|pluriel de|singulier de l’indicatif présent du verbe) \w+(\.| de \w+\.)$"
            ]
        },
        "en-simple": {
            # https://gist.githubusercontent.com/eyturner/3d56f6a194f411af9f29df4c9d4a4e6e/raw/63b6dbaf2719392cb2c55eb07a6b1d4e758cc16d/20k.txt
            "tag" : "simple.en",
            "wiki_category": "Category:English_lemmas",
            "wiki_lang": "en",
            "description": "Basic english words",
        },
        "en-full": {
            "tag": "en",
            "wiki_category": "Category:English_lemmas",
            "wiki_lang": "en",
            "description": "Nearly all english words",
        },
    }
    WORDS = []
    def __init__(self, wiki_slug="french-simple"):
        wiki_config = self.WIKIS[wiki_slug]
        self.wiki_slug = wiki_slug
        self.lang = wiki_config["wiki_lang"]
        self.list_file = f"data/wikidict.{wiki_config['tag']}.txt"
        self.exclude_file = f"data/exclude.{wiki_config['tag']}.txt"
        self.bug_reports_file = f"data/bugs.{wiki_config['tag']}.txt"
        self.api_endpoint = f"https://{wiki_config['wiki_lang']}.wiktionary.org/w/api.php"
        self.category = wiki_config["wiki_category"]
        self.wiki_config = wiki_config
        self.load_list()
        self.estimated = self.get_wordlist_len()

    @staticmethod
    def get_dict(_filter):
        try:
            return [k for k in Wikidict.WIKIS.keys() if k.startswith(_filter)][0]
        except Exception:
            return None

    def get_dict_string(self):
        return self.wiki_slug + " => " + self.wiki_config["description"]

    def get_available_lang(self, _filter=None):
        if _filter is not None:
            return [k for k in self.WIKIS.keys() if _filter in k]
        else:
            return list(self.WIKIS.keys())

    def _dump_state(self):
        pass

    def get_wordlist_len(self):
        line_count = 0
        with open(self.list_file, 'r', buffering=1) as f:
            for line in f:
                line_count += 1
        return line_count


    def create_list_file(self):
        logger.info("Loading words from API...")
        params = {
            "format": "json",
            "action": "query",
            "list": "categorymembers",
            "cmtitle": self.category,
            "cmlimit": "500",
        }
        cont_key = None
        start = True
        count = 0
        with open(self.list_file, mode="w", encoding="utf8") as f:
            while start or cont_key is not None:
                start = False
                if cont_key is not None:
                    params["cmcontinue"] = cont_key
                response = requests.get(url=self.api_endpoint, params=params)
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
                            or re.match(r"^\w.*\w$", word) is None  # first and last char must be word letters
                            or re.match(r"^[a-zA-Z].*", word) is None
                        ):
                            f.write(word + "\n")
                            count += 1
                self.estimated = count+500
                progress = count / self.estimated
                print(
                    "{}[{}{}]".format(
                        "\r" * 66,
                        "=" * (math.floor(progress * 64)),
                        " " * (64 - math.floor(progress * 64)),
                    ),
                    end="",
                )
            print()


    def bug_report(self, word, info):
        logger.warning(f"A bug was reported : {word}\n{info}")
        with open(self.bug_reports_file, mode="a", encoding="utf8") as f:
            f.write(f">{word}<\n{info}\n")

    def load_excluded(self):
        if not os.path.exists(self.exclude_file):
            return []
        with open(self.exclude_file, mode="r", encoding="utf8") as f:
            return [word.strip() for word in f.readlines() if len(word.strip()) > 0]


    def exclude(self, word):
        self.WORDS.remove(word)
        with open(self.exclude_file, mode="a", encoding="utf8") as f:
            f.write(word + "\n")

    def load_list(self):
        if not os.path.exists(self.list_file):
            self.create_list_file()
        with open(self.list_file, mode="r", encoding="utf8") as f:
            excluded_words = self.load_excluded()
            self.WORDS = [
                word.strip()
                for word in f.readlines()
                if len(word.strip()) > 0 and word.strip() not in excluded_words
            ]

    def has_words(self, s):
        pattern = re.compile(r'\b\w+\b')
        if pattern.search(s):
            return True
        return False

    def remove_ref(self, raw_html):
        cleanr = re.compile("<ref>.*?</ref>")
        return re.sub(cleanr, "", raw_html)

    def remove_duplicates(self, input_list):
        seen = set()  # A set to keep track of seen elements
        result = []   # List to store the result without duplicates

        for item in input_list:
            if item not in seen:
                result.append(item)  # Add item to the result if it has not been seen
                seen.add(item)       # Add item to seen set
        return result


    def render_wikitext(self, wikitext):
        logger.debug(f"Processing wikitext: {wikitext}")
        if self.is_only_wiki_templates(wikitext):
            logger.debug("Rejected wikitext because it look like templates only")
            logger.debug("---")
            return ""
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
        logger.debug(f"(1st pass) Processed wikitext: {wikitext}")

        # resolve templates names
        for tmpl in wikidef.templates:
            logger.debug(f"Resolving template {tmpl.arguments} ; name={tmpl.name}")

            if (len(tmpl.arguments) and tmpl.arguments[0].value in ("fr", "1")) or (
                len(tmpl.arguments) == 0 and len(tmpl.name) > 3
            ):
                templates += [f"({tmpl.name.capitalize()})"]
            elif len(tmpl.arguments) and tmpl.name in ("w", "lien", "lexique", "info lex", "term"):
                if tmpl.name not in ("lexique",) and str(tmpl.arguments[-1])[-2:] == self.lang:
                    templates += [str(tmpl.arguments[0])[1:]]
                else:
                    templates += ["(" + str(tmpl.arguments[0])[1:] + ")"]
            elif len(tmpl.arguments) and tmpl.name in ("lb",):
                templates += ["(" + str(tmpl.arguments[-1])[1:] + ")"]
            elif tmpl.name.startswith('variante') and tmpl.name.endswith('de') and tmpl.arguments[-1].value == self.lang:
                templates += [f"Variante de {tmpl.arguments[0].value}"]
            elif tmpl.name in ("exemple ", "exemple"):
                templates += [None]
            else:
                templates += [tmpl.name]

            logger.debug(f"Resolved to {templates[-1]}")

        chunks = (
            wikitext.replace("{{", chr(1) + "{{").replace("}}", "}}" + chr(1)).split(chr(1))
        )
        logger.debug(chunks)
        chunks_out = []
        for chunk in chunks:
            if re.match("\{\{.*\}\}", chunk) and len(templates) > 0:
                template_resolved = templates.pop(0)
                checks = (
                    template_resolved is None,
                    #template_resolved[0] == "(" and template_resolved[-1] == ")"
                )
                if not any(checks):
                    chunks_out += [template_resolved]
            else:
                chunks_out += [chunk]

        for chunk in chunks_out:
            if chunk.startswith("{{"):
                logger.debug("Rejected wikitext because it looks like a wrongly rendered wiki template")
                return ""

        logger.debug(f"(2st pass) Processed wikitext: {chunks_out}")

        clean_text = self.remove_ref("".join(chunks_out).replace("'''", "**").replace("''", "*")[2:])

        # return rendered text, adapted to markdown
        has_words = self.has_words(clean_text)

        logger.debug(f"(3rd pass) Processed wikitext: {has_words=} {clean_text}")

        if has_words:
            logger.debug("+++")
            return clean_text.strip()
        else:
            logger.debug("---")
            return ""



    def get_random_word(self):
        return random.choice(self.WORDS)


    # ================
    # Heuristics for cleaning up definitions list
    # ================

    def score_sentence(self, sentence):
        # Calculate features
        words_in_sentence = sentence.split()
        num_words = len(words_in_sentence)
        if num_words == 0:
            return 0

        special_char_count = sum(1 for c in sentence if c in string.punctuation)
        valid_word_count = sum(1 for word in words_in_sentence if word.lower() in self.WORDS)

        # Heuristic scores can be weighted as necessary
        score = valid_word_count - special_char_count + num_words

        return score

    def sort_sentences_by_coherence(self, sentences):
        scored_sentences = [(sentence, self.score_sentence(sentence)) for sentence in sentences]
        # Sort by score in descending order (most likely coherent first)
        sorted_sentences = sorted(scored_sentences, key=lambda x: x[1], reverse=True)
        return [sentence for sentence, score in sorted_sentences]

    def sort_sentences_by_masked_chars(self, sentences):
        scored_sentences = [(sentence, sentence.count("_")) for sentence in sentences]
        # Sort by score in descending order (most likely coherent first)
        sorted_sentences = sorted(scored_sentences, key=lambda x: x[1], reverse=False)
        return [sentence for sentence, score in sorted_sentences]

    def remove_similar_sentences(self, sentences):
        unique_sentences = []
        for sentence in sentences:
            if not any(fuzz.ratio(sentence, unique_sentence) >= 80 for unique_sentence in unique_sentences):
                unique_sentences.append(sentence)
        return unique_sentences

    def is_only_wiki_templates(self,s):
        s = s.replace("#","")
        remainder = s
        templates = re.findall(r'(\{\{.*?\}\}|\[\[.*?\]\])', s, re.DOTALL)
        for t in templates:
            remainder = remainder.replace(t,"")
        if len(remainder.strip()) < 3:
            return True
        return False

    def mask_sentences(self, sentences, word):
        return [s.replace(word, "_" * len(word)).replace(word.capitalize(), "_" * len(word)) for s in sentences]

    def get_definition(self, word):
        params = {
            "format": "json",
            "action": "parse",
            "prop": "wikitext",
            "page": word,
        }  # &prop=sections
        r = requests.get(url=self.api_endpoint, params=params)
        if not r.json().get("parse"):
            return

        r = r.json()["parse"]["wikitext"]["*"]
        logger.debug(r)
        # some redirection, usually because ’ != '
        if r.find("#REDIRECT [[") != -1:
            return (False, r[len("#REDIRECT [[") : -2])
        w = wtp.parse(r)
        definitions = []
        for section in w.sections:
            title = str(section.title).strip()
            logger.debug(f"Title: {title}")
            # title.find('verbe') == -1 and
            definition_filters = {
                "fr": title and title[0:4] == "{{S|" and title.find("|fr") != -1,
                "en": title
            }
            if definition_filters[self.wiki_config['wiki_lang']]:
                for line in str(section).split("\n"):
                    if len(line) > 2 and line[0] == "#" and line[1] != "*":
                        definitions += [self.render_wikitext(line)]

        logger.debug("Filtering and sorting definitions ...")
        definitions = self.remove_duplicates(definitions)
        definitions = self.remove_similar_sentences(definitions)
        definitions = self.sort_sentences_by_coherence(definitions)
        definitions = self.mask_sentences(definitions, word)
        definitions = self.sort_sentences_by_masked_chars(definitions)
        definitions = [d for d in definitions if d.strip()]

        #if len(definitions) > 4:
        #    definitions = definitions[0:4]
        random.shuffle(definitions)

        logger.debug("Checking if definitions are usable ...")
        logger.debug(definitions)
        definition_count = len(definitions)
        masked_count = 0
        word_mask = "_" * len(word)
        to_avoid = 0
        for definition in definitions:
            if word_mask in definition:
                masked_count += 1
            for regex in self.wiki_config.get("avoid-regex", []):
                definition_clean = definition.replace("*","")
                logger.debug(f"Checking definition ({definition_clean}) against {regex} ...")
                r = re.compile(regex)
                if r.match(definition_clean):
                    to_avoid += 1
                    logger.warning("Matched !")

        if masked_count == definition_count and masked_count != 0:
            logger.debug("Too many masked definitions, giving up")
            return
        if to_avoid == definition_count and to_avoid != 0:
            logger.debug("Too many 'to-avoid' regex matched, giving up")
            return
        if definition_count == 0:
            logger.debug("No definition found, giving up")
            return

        out = "\n".join([f"➥ `{d}`" for d in definitions])
        if len(out) > 2000:
            logger.debug("Final definition is too long, giving up")
            return
        else:
            logger.debug("Passed all checks !")
            return out


    def get_word_and_definition(self):
        definition = None
        word = None
        while definition is None:
            try:
                word = self.get_random_word()
                definition = self.get_definition(word)
                if isinstance(definition, tuple):  # got a redirection
                    definition = self.get_definition(definition[1])
            except Exception as e:
                logger.warning(f"Exception while picking new word: {e}")
        definition = html.unescape(definition)
        return html.unescape(word).replace("œ", "oe"), definition

problematic = (
    # "saccarifier",
    # "tronquer",
    # "physiques",
    # "canada",
    # "gousse",
    # "mont",
    # "soucie",
    # "encercler",
    # "cuivreux",
    # "insupportables"
    # "prononcées",
    #"attente"
)

w = Wikidict()

for word in problematic:
    logger.debug(word)
    print(w.get_definition(word))

#raise Exception("done")

while False:
    word, definition = w.get_word_and_definition()
    logger.debug(word)
    print(definition)
    time.sleep(3)
