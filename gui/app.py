import re
import json
import webbrowser
from datetime import datetime
from functools import partial

from tkinter import *
import tkinter as tk
from tkinter.font import ITALIC
from tkinter import filedialog
from gui.tkHyperLinkManager import HyperlinkManager

from nltk import stem
from nltk.corpus import stopwords
from nltk.stem.snowball import SnowballStemmer

from searcher import search_words
from indexer import generate_forward_index
from sorter import inverted_index_generator

stop_words = set(stopwords.words('english'))
snow_stemmer = SnowballStemmer(language='english')


def click_search_button(event: Event, result: Text, search_text: Entry, window: Tk) -> None:
    """Handler function for search button. Performs searching taking the
    search query as input and displaying search results as hyperlinks in window
    """

    start = datetime.now()

    search_text = search_text.get()
    search_query = (re.sub('[^a-zA-Z]', ' ', search_text)).lower().split()

    # if the user didnt enter anything then return
    if len(search_text) == 0:
        result.delete(0.0, END)
        result.insert(END, "You didn't enter anything!")
        return

    # stem the input words
    stemmed_words = [snow_stemmer.stem(
        word) for word in search_query if not word in stop_words]

    # open the file containing the URLs of each indexed document
    url_file = open('document_index.txt', 'r')
    doc_index = json.load(url_file)

    # perform the search and get ranked documents
    ranked_documents = search_words(stemmed_words)

    end = datetime.now()
    time_taken = str((end - start).total_seconds())

    # Convert to hyperLinks
    hyperLink = HyperlinkManager(result)

    frame3 = Frame(window, background="black")
    frame3.pack()
    time_taken_msg = Label(frame3, text="Search Time (in seconds): ", font=("Helvetica", 12, ITALIC),
                           background="black", foreground="#00FFC0")
    time_taken_msg.pack(side=LEFT)
    time_taken_secs = Label(frame3, text=time_taken, font=("Helvetica", 12, ITALIC), foreground="white",
                            background="black")
    time_taken_secs.pack(side=RIGHT)
    frame3.place(relx=0.5, rely=0.8, anchor=CENTER)
    result.delete(0.0, END)

    # this displays the result
    if len(ranked_documents):
        result.insert(END, "Search Results: \n\n")
        for document in ranked_documents:
            url = doc_index[document[0]]
            result.insert(END,  url, hyperLink.add(
                partial(webbrowser.open, url)))
            result.insert(END, "\n\n")
    else:
        result.insert(END, "Sorry, no results found!")


def click_insert_data_button(result: Text) -> None:
    """Handler function for insert data button. Traverses through directory,
    finds json files and starts computing forward index and inverted index
    """

    # gets the path of the folder containing the data
    folder_selected = filedialog.askdirectory()

    if folder_selected == "":
        return

    try:
        # if the index_info[0] contains a flag, it is 1 that means more documents
        # were added to the forward index else they weren't
        index_info = generate_forward_index(folder_selected)
        if index_info[0]:
            index_info.append(inverted_index_generator())
    except:
        result.delete(0.0, END)
        result.insert(
            END, "There was an error in generating the forward or inverted index!")
        return

    result.delete(0.0, END)
    if index_info[0]:
        result.insert(
            END, "Forward and Inverted indices generation successful for json files in " + folder_selected)
        result.insert(END, "\n")
        result.insert(
            END, "The number of docs scanned were: " + str(index_info[1]))
        result.insert(END, "\n")
        result.insert(
            END, "Time it took for forward index generation is: " + index_info[2])
        result.insert(END, "\n")
        result.insert(
            END, "Time it took for inverted index generation is: " + index_info[3])
    else:
        result.insert(END,
                      "There were either no json files in the input directory or those json files have already been indexed!")


def set_window_size(window):
    """sets the window size according to screen size"""

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    window.geometry(f"{screen_width}x{screen_height}")


def create_search_window() -> None:
    """Setting up search window"""

    window = Tk()
    window.title('Talash')
    set_window_size(window)
    window.resizable(False, False)

    window.configure(background="black")

    logo = PhotoImage(file="./assets/talash_png_2.png")
    Label(window, image=logo, background="black").place(
        relx=0.5, rely=0.15, anchor=CENTER)

    frame = Frame(window)
    frame.pack()

    search_button = Button(frame, text="Search",
                           font=("Helvetica", 10), width=10, borderwidth=0)
    search_button.pack(side=RIGHT)
    search_button.bind(
        "<Button-1>", lambda event: click_search_button(event, result, search_text, window))
    window.bind('<Return>', lambda event: click_search_button(
        event, result, search_text, window))

    search_text = Entry(frame, width=50, font=(
        "Helvetica", 14), bg="white")
    search_text.pack(side=LEFT, ipadx=4, ipady=4)

    frame.place(relx=0.5, rely=0.25, anchor=CENTER)

    result = Text(window, width=80, height=12, foreground="white", wrap=tk.WORD,
                  background="black", font=("Helvetica", 14), borderwidth=1)
    result.place(relx=0.50, rely=0.50, anchor=CENTER)

    add_button = Button(window, text="Index Data", font=(
        "Helvetica", 10), width=11, borderwidth=0, command=partial(click_insert_data_button, result))
    add_button.place(relx=0.50, rely=0.72, anchor=CENTER)

    window.mainloop()
