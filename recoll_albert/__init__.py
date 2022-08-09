"""Recoll."""
import os
import inspect
from sys import platform
import traceback
from pathlib import Path
from collections import Counter
import mimetypes

# TODO: Check if this fails and return a more comprehensive error message for the user
from recoll import recoll

from albert import *

__iid__ = "PythonInterface/v0.2"
__prettyname__ = "Recoll"
__title__ = "Recoll for Albert"
__version__ = "0.1.1"
#__trigger__ = "rc " # Use this if you want it to be only triggered by rc <query>
__authors__ = "Gerard Simons"
__dependencies__ = []
__homepage__ = "https://github.com/gerardsimons/recoll-albert/blob/master/recoll/recoll"

HOME_DIR = os.environ["HOME"]

icon_path = Path.home()  / "recoll"
cache_path = Path.home()   / "recoll"
config_path = Path.home() / "recoll"
data_path = Path.home() / "recoll"
dev_mode = True

# If set to to true it removes duplicate documents hits that share the same URL, such as epubs or other archives.
# Note that this means the number of results returned may be different from the actual recoll results
remove_duplicates = True

# String definitions
OPEN_WITH_DEFAULT_APP = "Open with default application"
REVEAL_IN_FILE_BROWSER = "Reveal in file browser"
OPEN_TERMINAL_AT_THIS_PATH = "Open terminal at this path"
COPY_FILE_CLIPBOARD = "Copy file to clipboard"
COPY_PATH_CLIPBOARD = "Copy path to clipboard"

# plugin main functions -----------------------------------------------------------------------

def initialize():
    """Called when the extension is loaded (ticked in the settings) - blocking."""

    # create plugin locations
    for p in (cache_path, config_path, data_path):
        p.mkdir(parents=False, exist_ok=True)

def query_recoll(query_str, max_results=10, max_chars=80, context_words=4, verbose=False):
    """
    Query recoll index for simple query string and return the filenames in order of relevancy
    :param query_str:
    :param max_results:
    :return:
    """
    if not query_str:
        return []

    db = recoll.connect()
    db.setAbstractParams(maxchars=max_chars, contextwords=context_words)
    query = db.query()
    nres = query.execute(query_str)
    docs = []
    if nres > max_results:
        nres = max_results
    for i in range(nres):
        doc = query.fetchone() # TODO: JUst use fetchall and return the lot?!
        docs.append(doc)

    return docs


def path_from_url(url: str) -> str:
    if not url.startswith('file://'):
        return None
    else:
        return url.replace("file://", "")


def get_open_dir_action(dir: str):
    if platform == "linux" or platform == "linux2":
        return ProcAction(text=REVEAL_IN_FILE_BROWSER, commandline=["xdg-open", dir])
    elif platform == "darwin":
        return ProcAction(text=REVEAL_IN_FILE_BROWSER, commandline=["open", dir])
    elif platform == "win32": # From https://stackoverflow.com/a/2878744/916382
        return FuncAction(text=REVEAL_IN_FILE_BROWSER, callable=lambda : os.startfile(dir))


def doc_to_icon_path(doc) -> str:
    """ Attempts to convert a mime type to a text string that is accepted by """
    mime_str = getattr(doc, "mtype", None)
    if not mime_str:
        return albert.iconLookup("unknown")
    mime_str = mime_str.replace("/", "-")
    icon_path = iconLookup(mime_str)
    if not icon_path:
        icon_path = iconLookup("unknown")
    return icon_path


def remove_duplicate_docs(docs: list):
    """
    Removes Recoll docs that have the same URL but actually refer to different files, for example an epub file
    which contains HTML files will have multiple docs for each but they all refer to the same epub file.
    :param docs: the original list of documents
    :return: the same docs param but with the docs removed that share the same URL attribute
    """
    urls = [x.url for x in docs]
    url_count = Counter(urls)

    duplicates = [k for k in url_count.keys() if url_count[k] > 1]
    # Merge duplicate results, this might happen becase it actually consists of more than 1 file, like an epub
    # We adopt the relevancy rating of the max one
    for dup in duplicates:
        # Just take the one with the highest relevancy
        best_doc = None
        best_rating = -1
        for doc in [x for x in docs if x.url == dup]:
            rating = float(doc.relevancyrating.replace("%", ""))
            if rating > best_rating:
                best_doc = doc
                best_rating = rating

        docs = [x for x in docs if x.url != dup]
        docs.append(best_doc)
    return docs

def recoll_docs_as_items(docs: list):
    """Return an item - ready to be appended to the items list and be rendered by Albert."""

    items = []

    # First we find duplicates if so configured
    if remove_duplicates:
        docs = remove_duplicate_docs(docs)

    for doc in docs:
        path = path_from_url(doc.url) # The path is not always given as an attribute by recoll doc
        dir = os.path.dirname(path)
        file_extension = Path(path).suffix # Get the file extension and work out the mimetype
        mime_type = mimetypes.guess_type(file_extension)[0]

        dir_open = get_open_dir_action(dir)

        if path:
            actions=[
                    UrlAction(
                        OPEN_WITH_DEFAULT_APP, 
                        doc.url),
                    ClipAction(text=COPY_PATH_CLIPBOARD,
                               clipboardText=path),
                    TermAction(text=COPY_FILE_CLIPBOARD,
                                script="xclip -selection clipboard -t " + mime_type + " -i '" + path + "'",
                                behavior=TermAction.CloseBehavior(0),
                                cwd="/usr/bin")
                ]

            if dir_open:
                actions.append(dir_open)

            # Add the item
            items.append(Item(
                id=__prettyname__,
                icon=doc_to_icon_path(doc),
                text=doc.filename,
                subtext=dir,
                completion="",
                actions=actions
            ))
    return items


def handleQuery(query) -> list:
    """Hook that is called by albert with *every new keypress*."""  # noqa
    results = []

    try:
        if __trigger__  and not query.isTriggered:
            return []
        # be backwards compatible with v0.2
        if "disableSort" in dir(query):
            query.disableSort()

        results_setup = setup(query)
        if results_setup:
            return results_setup

        docs = query_recoll(query.string)
        results = recoll_docs_as_items(docs)
    except Exception:  # user to report error
        if dev_mode:  # let exceptions fly!
            print(traceback.format_exc())
            raise

        results.insert(
            0,
            albert.Item(
                id=__prettyname__,
                icon=icon_path,
                text="Something went wrong! Press [ENTER] to copy error and report it",
                actions=[
                    albert.ClipAction(
                        f"Copy error - report it to {__homepage__[8:]}",
                        f"{traceback.format_exc()}",
                    )
                ],
            ),
        )

    return results


# supplementary functions ---------------------------------------------------------------------
def save_data(data: str, data_name: str):
    """Save a piece of data in the configuration directory."""
    with open(config_path / data_name, "w") as f:
        f.write(data)


def load_data(data_name) -> str:
    """Load a piece of data from the configuration directory."""
    with open(config_path / data_name, "r") as f:
        data = f.readline().strip().split()[0]

    return data


def setup(query):
    """Setup is successful if an empty list is returned.

    Use this function if you need the user to provide you data
    """

    results = []
    return results

# In case the __trigger__ was not set at all we set it to the empty string
try:
    __trigger__
except NameError:
    __trigger__ = ""
