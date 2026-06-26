import json
import os
import re
import zlib
from datetime import datetime
from typing import Any, Dict, List, Tuple

import nltk
from nltk.corpus import stopwords
from nltk.stem.snowball import SnowballStemmer

nltk.download("stopwords")

stop_words = set(stopwords.words("english"))
snow_stemmer = SnowballStemmer(language="english")


def get_lexicon() -> Dict[str, List[int]]:
    """returns previous lexicon if exists otherwise initializes lexicon"""

    lexicon = None
    # if lexicon file is present we load it to memory
    if os.path.isfile("lexicon.txt"):
        with open("lexicon.txt", "r") as prev_lexicon:
            lexicon = json.load(prev_lexicon)
    else:
        lexicon = {"word_count": [0, 0]}

    return lexicon


def get_document_index() -> Any:
    """load the previous document index if the file exists and load the data"""

    document_index = {}
    if os.path.isfile("./document_index.txt"):
        with open("./document_index.txt") as doc_idx:
            document_index = json.load(doc_idx)
    return document_index


def get_forward_barrels() -> List:
    """creates forward barrels files and return list of pointers"""

    # create a list of forward barrels and we use 300 barrels
    forward_barrels = []
    for barrel_count in range(1, 301):
        forward_barrels.append(open("./ForwardBarrels/forward_barrel_{}.txt".format(barrel_count), "w"))
    return forward_barrels


def get_forward_dicts() -> List[Dict]:
    """initializes forward dictionaries"""

    # created a list of 300 forward dictionaries
    forward_dicts = []
    for barrelCount in range(1, 301):
        forward_dicts.append({})
    return forward_dicts


def write_forward_barrels(forward_dicts: List, forward_barrels: List) -> None:
    """writes forward dictionaries to forward barrel files"""

    id = 0
    while id < 300:  # here 300 is barrel count
        # write content of forward dictionary to corresponding forward barrels
        for object_ in forward_dicts[id].items():
            forward_barrels[id].write(json.dumps(object_))
            forward_barrels[id].write("\n")
        id += 1


def parse_content(content: Any) -> List:
    """split content, lowercase it and remove stop words and do stemming"""

    content = (re.sub("[^a-zA-Z]", " ", content)).lower().split()
    stemmed_words = [snow_stemmer.stem(word) for word in content if word not in stop_words]
    return stemmed_words


def process_article_title(
    stemmed_title: Any, forward_dicts: List[Dict], lexicon: Dict[str, List[int]], hashed_id: int, word_count: int
) -> int:
    """reads words in title and updates forwards dictionaries and lexicon"""

    position = 1  # position of word in the title

    # store the title words in the hit list
    for word in stemmed_title:
        # add word to lexicon if not in lexicon
        if word not in lexicon:
            lexicon[word] = [word_count, 0]
            word_count += 1

        # through word_id calculate which barrel it belongs to and then add hitlist for title
        barrel_location = int(lexicon[word][0] / 533)

        if (hashed_id, lexicon[word][0]) not in forward_dicts[barrel_location]:
            # here hitlist consist of two sub lists, first list for title and second for content
            # in title hitlist, first element is always 1 and second element is hit count
            forward_dicts[barrel_location][(hashed_id, lexicon[word][0])] = []
            forward_dicts[barrel_location][(hashed_id, lexicon[word][0])].insert(0, [1, 1])
            forward_dicts[barrel_location][(hashed_id, lexicon[word][0])].insert(1, [0, 0])
        else:
            # if hit list is present we just increase hit count for title hits
            forward_dicts[barrel_location][(hashed_id, lexicon[word][0])][0][1] += 1

        position += 1

    return word_count


def process_article_content(
    stemmed_words: Any, forward_dicts: List[Dict], lexicon: Dict[str, List[int]], hashed_id: int, word_count: int
) -> int:
    """reads words in content and updates forwards dictionaries and lexicon"""

    position = 1  # position of word in the document

    for word in stemmed_words:
        if word not in lexicon:
            lexicon[word] = [word_count, 0]
            word_count += 1

        barrel_location = int(lexicon[word][0] / 533)

        if (hashed_id, lexicon[word][0]) not in forward_dicts[barrel_location]:
            # in content hitlist, first element is always 0 and second element is hit count
            # and then hit position are appended
            forward_dicts[barrel_location][(hashed_id, lexicon[word][0])] = []
            forward_dicts[barrel_location][(hashed_id, lexicon[word][0])].insert(0, [1, 0])
            forward_dicts[barrel_location][(hashed_id, lexicon[word][0])].insert(1, [0, 1, position])
        else:
            # if hit list is present we just increase hit count for content hits
            forward_dicts[barrel_location][(hashed_id, lexicon[word][0])][1][1] += 1
            forward_dicts[barrel_location][(hashed_id, lexicon[word][0])][1].append(position)

        position += 1

    return word_count


def process_loaded_data(
    loaded_data: Any,
    forward_dicts: List[Dict],
    lexicon: Dict[str, List[int]],
    document_index: Dict,
    doc_count: int,
    word_count: int,
) -> Tuple[int, int]:
    """Parses loaded data and adds to forward dictionaries"""

    # read articles in loaded datas
    for article in loaded_data:
        # hash the doc id
        doc_id = bytes(article["id"], "utf-8")
        hashed_id = zlib.crc32(doc_id)

        # If the article is already indexed then continue else add doc id to document index
        if str(hashed_id) in document_index:
            continue
        else:
            document_index[str(hashed_id)] = article["url"]
            doc_count += 1

        # parse the article's content
        stemmed_words = parse_content(article["content"])

        # parse the article's title
        stemmed_title = parse_content(article["title"])

        word_count = process_article_title(stemmed_title, forward_dicts, lexicon, hashed_id, word_count)
        word_count = process_article_content(stemmed_words, forward_dicts, lexicon, hashed_id, word_count)

    return doc_count, word_count


def generate_forward_index(path_to_data: str) -> List:
    """This parses json files and creates lexicon and forward index"""

    start = datetime.now()
    doc_count = 0
    lexicon = get_lexicon()
    word_count = lexicon["word_count"][0]

    try:
        # check the directory for files of json format
        file_names = [pos_json for pos_json in os.listdir(path_to_data) if pos_json.endswith(".json")]

        # create a temporary document index to store record of documents being indexed
        document_index = get_document_index()
        forward_barrels = get_forward_barrels()

        for file_name in file_names:
            forward_dicts = get_forward_dicts()

            # open file and load data to be processed
            with open("{}/{}".format(path_to_data, file_name)) as f:
                loaded_data = json.load(f)

            doc_count, word_count = process_loaded_data(
                loaded_data, forward_dicts, lexicon, document_index, doc_count, word_count
            )

            write_forward_barrels(forward_dicts, forward_barrels)

    except Exception as error:
        print(error)

    # dump lexicon program which updates previous lexicon to create new lexicon
    lexicon["word_count"][0] = word_count
    with open("lexicon.txt", "w") as new_lexicon:
        new_lexicon.write(json.dumps(lexicon))

    # document index is written to document index file
    with open("./document_index.txt", "w") as new_document_index:
        new_document_index.write(json.dumps(document_index))

    end = datetime.now()
    time_taken = str(end - start)
    print("The time of execution to create forward index and lexicon is:", time_taken)
    print("doc_count = ", doc_count)
    print("word_count = ", word_count)

    if doc_count:  # if it is more than 0
        return [1, doc_count, time_taken]
    else:
        return [0, doc_count, time_taken]
