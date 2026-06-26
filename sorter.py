import json
import os
from datetime import datetime
from typing import Any, List, Tuple


def sort(input_list: List) -> List[List]:
    """performs sorting on forward barrel content"""

    # creates a list of 533 lists corresponding to the number of words in one fwd index file
    sorted_list = [[] for i in range(533)]

    # Uses counting sort to sort in O(n) time
    for value in input_list:
        sorted_list[value[0][1] % 533].append(value)

    return sorted_list


def get_single_inverted_barrel_content(curr_barrel: str, barrels: List) -> Tuple[List, str]:
    """Takes data from corresponding forward barrel, combines it
    with content of inverted barrel if exist and returns all content
    """

    with open("./ForwardBarrels/{}".format(curr_barrel)) as forward_file:
        inverted_list = []

        # get the barrel number corresponding to the forward index file because they are not sorted
        if curr_barrel[17].isnumeric() and curr_barrel[16].isnumeric():
            barrel_num = curr_barrel[15] + curr_barrel[16] + curr_barrel[17]
        elif curr_barrel[16].isnumeric():
            barrel_num = curr_barrel[15] + curr_barrel[16]
        else:
            barrel_num = curr_barrel[15]

        # if inverted barrel is present we load its content to a list
        inverted_barrel_path = "./InvertedBarrels/inverted_barrel_" + barrel_num + ".txt"
        if os.path.isfile(inverted_barrel_path):
            with open(inverted_barrel_path, "r") as inverted_index:
                for line in inverted_index:
                    inverted_list.append(json.loads(line))

        # we append content of forward barrel to inverted list
        for line in forward_file:
            inverted_list.append(json.loads(line))

    return inverted_list, barrel_num


def write_inverted_barrel(inverted_list: List, barrel_num: str, lexicon: Any, lexicon_keys: List) -> None:
    """sorts content by wordID and write content to single inverted barrel"""

    inverted_barrel_path = "./InvertedBarrels/inverted_barrel_" + barrel_num + ".txt"
    with open(inverted_barrel_path, "w") as inverted_file:
        sorted_list = sort(inverted_list)
        for i in range(len(sorted_list)):
            for j in range(len(sorted_list[i])):
                if j == 0:
                    lexicon[lexicon_keys[sorted_list[i][0][0][1] + 1]][1] = inverted_file.tell()
                inverted_file.write(json.dumps(sorted_list[i][j]))
                inverted_file.write("\n")


def inverted_index_generator() -> str:
    """Generate inverted index from forward index"""

    start = datetime.now()

    os.makedirs("./InvertedBarrels", exist_ok=True)

    # we find forward barrels present in directory
    barrels = [
        forward_barrel
        for forward_barrel in os.listdir("./ForwardBarrels")
        if forward_barrel.startswith("forward_barrel_")
    ]

    # opening lexicon to update the offset values into inverted barrels
    with open("lexicon.txt", "r") as lexicon_file:
        lexicon = json.load(lexicon_file)
        lexicon_keys = list(lexicon.keys())

    for curr_barrel in barrels:
        # at a time we open one forward barrel and get all content
        inverted_list, barrel_num = get_single_inverted_barrel_content(curr_barrel, barrels)

        # re sort the inverted list and write to the inverted barrel
        write_inverted_barrel(inverted_list, barrel_num, lexicon, lexicon_keys)

    with open("lexicon.txt", "w") as lexicon_file:
        lexicon_file.write(json.dumps(lexicon))

    end = datetime.now()
    time_taken = str(end - start)
    print("The time of execution to create inverted index is:", time_taken)

    return time_taken
