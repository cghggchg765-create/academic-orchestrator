import ssl
import random
import re
import threading
import warnings

# Optional dependencies are imported only on the feature path that needs them.
# Importing this module must remain fast and must never download a package/model.
nltk = None
wordnet = None
spacy = None
SentenceTransformer = None
util = None
NLP_GLOBAL = None
_MODEL_CACHE = {}
_MODEL_LOCK = threading.RLock()


def _load_nlp():
    """Load spaCy and its model only when the humanizer is constructed."""
    global NLP_GLOBAL, spacy
    if NLP_GLOBAL is not None:
        return NLP_GLOBAL
    if spacy is None:
        try:
            import spacy as _spacy
        except ImportError:  # pragma: no cover - dependency preflight path
            return None
        spacy = _spacy
    try:
        NLP_GLOBAL = spacy.load("en_core_web_sm")
    except OSError:
        NLP_GLOBAL = None
    return NLP_GLOBAL


def _load_sentence_transformers():
    global SentenceTransformer, util
    if SentenceTransformer is None or util is None:
        try:
            from sentence_transformers import SentenceTransformer as _SentenceTransformer, util as _util
        except ImportError:  # pragma: no cover - dependency preflight path
            return None, None
        SentenceTransformer, util = _SentenceTransformer, _util
    return SentenceTransformer, util


def _load_wordnet():
    global nltk, wordnet
    if wordnet is None:
        try:
            import nltk as _nltk
            from nltk.corpus import wordnet as _wordnet
        except ImportError:  # pragma: no cover - dependency preflight path
            return None
        nltk, wordnet = _nltk, _wordnet
    return wordnet


def download_nltk_resources():
    """Download required NLTK resources if not already installed."""
    global nltk
    if nltk is None:
        try:
            import nltk as _nltk
        except ImportError as exc:
            raise RuntimeError("NLTK is unavailable; install the optional humanizer dependency") from exc
        nltk = _nltk
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context
    resources = ['punkt', 'wordnet', 'averaged_perceptron_tagger', 'punkt_tab', 'averaged_perceptron_tagger_eng']
    for resource in resources:
        try:
            nltk.download(resource, quiet=True)
        except Exception as e:
            print(f"Warning: cannot download {resource}: {e}")


class AcademicHumanizer:
    """
    De-AI-fy academic text by:
    - Expanding contractions (don't -> do not)
    - Removing AI-style academic transition crutches
    - Converting passive voice to active
    - Replacing words with natural synonyms
    Only transforms sentences that exceed AI-ness threshold.
    """

    AI_TRANSITIONS = [
        "Moreover,", "Additionally,", "Furthermore,", "Hence,",
        "Therefore,", "Consequently,", "Nonetheless,", "Nevertheless,"
    ]

    AI_OPENERS = [
        "it is worth noting", "it is important to", "it should be noted",
        "it goes without saying", "needless to say", "as we all know"
    ]

    # Irregular past participle -> base form, used for safe tense-aware rewrites.
    IRREGULAR_PAST = {
        "built": "build", "done": "do", "made": "make", "set": "set",
        "put": "put", "written": "write", "known": "know", "given": "give",
        "shown": "show", "seen": "see", "taken": "take", "found": "find",
        "told": "tell", "held": "hold", "brought": "bring", "thought": "think",
        "paid": "pay", "sent": "send", "left": "leave", "kept": "keep",
        "met": "meet", "led": "lead", "won": "win", "lost": "lose",
        "drawn": "draw", "grown": "grow", "chosen": "choose", "spoken": "speak",
        "begun": "begin", "driven": "drive", "forgotten": "forget",
        "hidden": "hide", "broken": "break", "stolen": "steal",
        "worn": "wear", "sworn": "swear", "torn": "tear", "borne": "bear",
        "caught": "catch", "taught": "teach", "fought": "fight", "bought": "buy",
        "sought": "seek", "cut": "cut", "hit": "hit", "let": "let",
        "cost": "cost", "split": "split", "spread": "spread", "read": "read"
    }

    # Compile rule patterns once; humanize() may process hundreds of sentences.
    _CONTRACTION_PATTERNS = tuple(
        (re.compile(re.escape(contraction) + r"\b", re.IGNORECASE), expansion)
        for contraction, expansion in {
            "can't": "cannot", "won't": "will not", "n't": " not",
            "'re": " are", "'ll": " will", "'ve": " have",
            "'d": " would", "'m": " am",
        }.items()
    )
    _PASSIVE_PATTERN = re.compile(
        r'\b(\w+(?:\s+\w+)?)\s+(was|were|is|are|been|being)\s+'
        r'(\w+)\s+by\s+(\w+(?:\s+\w+)?)', re.IGNORECASE
    )
    _PARTICIPLE_PATTERN = re.compile(
        r'^(?:' + '|'.join(re.escape(k) for k in IRREGULAR_PAST) + r'|\w+ed)$',
        re.IGNORECASE,
    )
    _IRREGULAR_SIMPLE_PAST = {
        "done": "did", "written": "wrote", "known": "knew", "given": "gave",
        "shown": "showed", "seen": "saw", "taken": "took", "found": "found",
        "told": "told", "held": "held", "brought": "brought", "thought": "thought",
        "sent": "sent", "left": "left", "kept": "kept", "met": "met", "led": "led",
        "won": "won", "lost": "lost", "drawn": "drew", "grown": "grew",
        "chosen": "chose", "spoken": "spoke", "begun": "began", "driven": "drove",
        "forgotten": "forgot", "hidden": "hid", "broken": "broke", "stolen": "stole",
        "worn": "wore", "sworn": "swore", "torn": "tore", "borne": "bore",
        "caught": "caught", "taught": "taught", "fought": "fought", "bought": "bought",
        "sought": "sought", "made": "made", "built": "built", "set": "set",
        "put": "put", "read": "read", "cut": "cut", "hit": "hit", "let": "let",
        "cost": "cost", "split": "split", "spread": "spread",
    }

    def __init__(self, model_name='paraphrase-MiniLM-L6-v2', seed=None):
        if seed is not None:
            random.seed(seed)
        nlp = _load_nlp()
        if spacy is None or nlp is None:
            raise RuntimeError(
                "academic-humanizer optional dependency/model unavailable; "
                "run the humanize preflight or choose the rule-based fallback"
            )
        self.nlp = nlp
        if model_name:
            sentence_transformer, _ = _load_sentence_transformers()
            if sentence_transformer is None:
                raise RuntimeError(
                    "sentence-transformers is unavailable; pass model_name='' "
                    "for the rule-based humanizer"
                )
            with _MODEL_LOCK:
                if model_name not in _MODEL_CACHE:
                    _MODEL_CACHE[model_name] = sentence_transformer(model_name)
                self.model = _MODEL_CACHE[model_name]
        else:
            self.model = None

    def humanize(self, text, use_synonyms=False, ai_score=0.0):
        """
        Main entry: de-AI-fy academic text.

        Args:
            text: Input academic text
            use_synonyms: Whether to apply synonym replacement
            ai_score: AI-ness Score from humanizer (0.0~1.0).
                      If < 0.3, minimal changes. If > 0.6, aggressive.
        """
        if not text or not text.strip():
            return text
        if len(text.split()) < 5:
            return text  # 极短文本不处理

        doc = self.nlp(text)
        transformed = []
        aggressiveness = min(ai_score * 1.5, 1.0)  # scale: 0.3->0.45, 0.6->0.9, 1.0->1.0

        for sent in doc.sents:
            raw = sent.text
            # spaCy can attach paragraph whitespace to the preceding sentence.
            # Keep that whitespace outside the semantic rewrite.
            leading_match = re.match(r"\s*", raw)
            trailing_match = re.search(r"\s*\Z", raw)
            leading = leading_match.group(0) if leading_match else ""
            trailing = trailing_match.group(0) if trailing_match else ""
            core_end = len(raw) - len(trailing) if trailing else len(raw)
            core = raw[len(leading):core_end]
            if not core:
                transformed.append(raw)
                continue
            s = core
            original_was_capitalized = s[0].isupper()

            # Always expand contractions
            s = self.expand_contractions(s)

            # Remove transition crutches (if aggressiveness > 0.3)
            if aggressiveness > 0.3:
                s = self.remove_transitions(s)
                if s and not s[0].isupper() and original_was_capitalized:
                    s = s[0].upper() + s[1:]

            # Remove AI openers (if aggressiveness > 0.3)
            if aggressiveness > 0.3:
                before_opener = s
                s = self.remove_ai_openers(s)
                if s and not s[0].isupper() and before_opener and before_opener[0].isupper():
                    s = s[0].upper() + s[1:]

            # Convert passive to active (if aggressiveness > 0.4)
            if aggressiveness > 0.4:
                s = self.convert_to_active(s)

            # Synonym replacement (if enabled and aggressiveness > 0.5)
            if use_synonyms and aggressiveness > 0.5:
                s = self.replace_with_synonyms(s)

            transformed.append(leading + s + trailing)

        # Recombine using the original sentence spans. This preserves every
        # inter-sentence separator, including LF, CRLF, and blank paragraphs.
        if not transformed:
            return text
        pieces = []
        cursor = 0
        for sent, replacement in zip(doc.sents, transformed):
            pieces.append(text[cursor:sent.start_char])
            pieces.append(replacement)
            cursor = sent.end_char
        pieces.append(text[cursor:])
        return ''.join(pieces)

    def expand_contractions(self, sentence):
        contraction_map = {
            "can't": "cannot", "won't": "will not", "n't": " not",
            "'re": " are", "'ll": " will", "'ve": " have",
            "'d": " would", "'m": " am"
        }
        result = sentence
        for pattern, expansion in self._CONTRACTION_PATTERNS:
            for match in reversed(list(pattern.finditer(result))):
                original = match.group()
                replaced = expansion[0].upper() + expansion[1:] if original[0].isupper() else expansion
                result = result[:match.start()] + replaced + result[match.end():]
        return result

    def remove_transitions(self, sentence):
        """Remove leading AI transition crutches."""
        s = sentence.strip()
        for t in self.AI_TRANSITIONS:
            if s.startswith(t):
                s = s[len(t):].strip()
                break
        return s

    def remove_ai_openers(self, sentence):
        """Remove AI formulaic openers like 'it is worth noting that'."""
        s = sentence.strip().lower()
        for opener in self.AI_OPENERS:
            if s.startswith(opener):
                rest = sentence.strip()[len(opener):].lstrip(", ")
                return rest[0].upper() + rest[1:] if rest else sentence
        return sentence

    def convert_to_active(self, sentence):
        """
        Convert passive to active:
        "The experiment was conducted by the researchers" -> "The researchers conducted the experiment"
        "The plan was made by the team" -> "The team made the plan"
        """
        leading_match = re.match(r"\s*", sentence)
        trailing_match = re.search(r"\s*\Z", sentence)
        leading = leading_match.group(0) if leading_match else ""
        trailing = trailing_match.group(0) if trailing_match else ""
        end = len(sentence) - len(trailing) if trailing else len(sentence)
        core = sentence[len(leading):end]

        def _past_form(participle: str) -> str:
            lower = participle.lower()
            if lower in self._IRREGULAR_SIMPLE_PAST:
                return self._IRREGULAR_SIMPLE_PAST[lower]
            if lower.endswith("ied"):
                return lower[:-3] + "ied"
            if lower.endswith("ed"):
                return lower
            return lower

        def _present_form(participle: str) -> str:
            lower = participle.lower()
            if lower in self.IRREGULAR_PAST:
                return self.IRREGULAR_PAST[lower]
            if lower.endswith("ied"):
                return lower[:-3] + "y"
            if lower.endswith("ed"):
                stem = lower[:-2]
                if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
                    stem = stem[:-1]
                return stem
            return lower

        def replacer(m):
            obj, auxiliary, participle, agent = m.groups()
            if not self._PARTICIPLE_PATTERN.fullmatch(participle):
                return m.group(0)
            auxiliary_lower = auxiliary.lower()
            if auxiliary_lower in {"was", "were", "been", "being"}:
                verb = _past_form(participle)
            else:
                verb = _present_form(participle)
            # The semantic core is already stripped in humanize(); only an
            # actual sentence-start match should trigger capitalization.
            if m.start() == 0:
                agent = agent[:1].upper() + agent[1:]
                obj = obj[:1].lower() + obj[1:]
            return f"{agent} {verb} {obj}"

        return leading + self._PASSIVE_PATTERN.sub(replacer, core) + trailing

    def replace_with_synonyms(self, sentence):
        if not self.model:
            return sentence
        doc = self.nlp(sentence)
        result = sentence
        replacements = []
        for token in doc:
            if token.pos_ in ['ADJ', 'NOUN', 'VERB', 'ADV'] and not token.is_stop:
                if random.random() < 0.3:
                    synonyms = self._get_synonyms(token.text, token.tag_)
                    if synonyms:
                        best = self._select_closest_synonym(token.text, synonyms)
                        if best and len(best.split()) == 1:
                            if token.text[0].isupper():
                                best = best.capitalize()
                            replacements.append((token.idx, token.idx + len(token.text), best))
        for start, end, replacement in reversed(replacements):
            result = result[:start] + replacement + result[end:]
        return result

    def _get_synonyms(self, word, pos):
        lexicon = _load_wordnet()
        if lexicon is None:
            return []
        wn_pos = None
        if pos.startswith('J'): wn_pos = wordnet.ADJ
        elif pos.startswith('N'): wn_pos = wordnet.NOUN
        elif pos.startswith('R'): wn_pos = wordnet.ADV
        elif pos.startswith('V'): wn_pos = wordnet.VERB
        synonyms = set()
        for syn in wordnet.synsets(word, pos=wn_pos):
            for lemma in syn.lemmas():
                name = lemma.name().replace('_', ' ')
                if name.lower() != word.lower():
                    synonyms.add(name)
        return list(synonyms)

    def _select_closest_synonym(self, original_word, synonyms):
        if not synonyms or not self.model:
            return synonyms[0] if synonyms else None
        _, cosine_util = _load_sentence_transformers()
        if cosine_util is None:
            return synonyms[0] if synonyms else None
        # Encode the original and candidates in one batch to avoid repeated
        # model dispatches on long documents.
        embeddings = self.model.encode([original_word, *synonyms], convert_to_tensor=True)
        cos_scores = cosine_util.cos_sim(embeddings[0], embeddings[1:])[0]
        max_idx = cos_scores.argmax().item()
        if cos_scores[max_idx].item() >= 0.5:
            return synonyms[max_idx]
        return None
