"""Recoll."""
import os
import inspect
from sys import platform
import traceback
import time
from pathlib import Path
from collections import Counter
import mimetypes

from pprint import pprint # troubleshooting


# TODO: Check if this fails and return a more comprehensive error message for the user
from recoll import recoll

from albert import *

md_iid = "0.5"
md_version = "2.0"
md_name = "Recoll"
md_description = "Recoll for Albert"
md_license = "BSD-3"
md_url = "https://github.com/theitd/recoll-albert"
md_maintainers = "@theitd"

#__iid__ = "PythonInterface/v0.2"
#__prettyname__ = "Recoll"
#__title__ = "Recoll for Albert"
#__version__ = "0.1.1"
#__triggers__ = "rc " # Use this if you want it to be only triggered by rc <query>
#__authors__ = "Gerard Simons"
#__dependencies__ = []
#__homepage__ = "https://github.com/gerardsimons/recoll-albert/blob/master/recoll/recoll"

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

class Plugin(QueryHandler):

    def id(self):
        return __name__

    def name(self):
        return md_name

    def description(self):
        return md_description

    def defaultTrigger(self):
        return "rc "

    def initialize(self):
        info('initialize')
    """Called when the extension is loaded (ticked in the settings) - blocking."""

    # create plugin locations
    for p in (cache_path, config_path, data_path):
        p.mkdir(parents=False, exist_ok=True)

    def finalize(self):
        info('finalize')

    def query_recoll(self, query_str, max_results=10, max_chars=80, context_words=4, verbose=False):
        """
        Query recoll index for simple query string and return the filenames in order of relevancy
        :param query_str:
        :param max_results:
        :return:
        """
        if not query_str:
            return []

        info(f'Recoll query\'{query_str}\'')
        db = recoll.connect()
        db.setAbstractParams(maxchars=max_chars, contextwords=context_words)
        querydb = db.query()
        nres = querydb.execute(query_str)
        docs = []
        if nres > max_results:
            nres = max_results
        for i in range(nres):
            doc = querydb.fetchone() # TODO: JUst use fetchall and return the lot?!
            docs.append(doc)

        return docs


    def path_from_url(self, url: str) -> str:
        if not url.startswith('file://'):
            return None
        else:
            return url.replace("file://", "")


    def get_open_dir_action(self, dir: str):
        if platform == "linux" or platform == "linux2":
            return # ProcAction(text=REVEAL_IN_FILE_BROWSER, commandline=["xdg-open", dir])
        elif platform == "darwin":
            return ProcAction(text=REVEAL_IN_FILE_BROWSER, commandline=["open", dir])
        elif platform == "win32": # From https://stackoverflow.com/a/2878744/916382
            return FuncAction(text=REVEAL_IN_FILE_BROWSER, callable=lambda : os.startfile(dir))


    def doc_to_icon_path(self, doc) -> str:
        """ Attempts to convert a mime type to a text string that is accepted by """
        mime_str = getattr(doc, "mtype", None)
        if not mime_str:
            return albert.iconLookup("unknown")
        mime_str = mime_str.replace("/", "-")
        icon_path = ['xdg:albert']
        if not icon_path:
            icon_path = ['xdg:albert']
        return icon_path


    def remove_duplicate_docs(self, docs: list):
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

    def recoll_docs_as_items(self, docs: list):
        """Return an item - ready to be appended to the items list and be rendered by Albert."""

        items = []

        # First we find duplicates if so configured
        if remove_duplicates:
            docs = self.remove_duplicate_docs(docs)

        for doc in docs:
            path = self.path_from_url(doc.url) # The path is not always given as an attribute by recoll doc
            dir = os.path.dirname(path)


            file_extension = Path(path).suffix # Get the file extension and work out the mimetype
            mime_type = mimetypes.guess_type(file_extension)[0]

            dir_open = self.get_open_dir_action(dir)

            if path:
                actions=[
                        Action(
                            id="clip",
                            text="setClipboardText (ClipAction)",
                            callable=lambda: setClipboardText(text=configLocation())
                        ),
                        Action(
                            id="url",
                            text="openUrl (UrlAction)",
                            callable=lambda: openUrl(url="https://www.google.de")
                        ),
                        Action(
                            id="run",
                            text="runDetachedProcess (ProcAction)",
                            callable=lambda: runDetachedProcess(
                                cmdln=["espeak", "hello"],
                                workdir="~"
                            )
                        ),
                        Action(
                            id="term",
                            text="runTerminal (TermAction)",
                            callable=lambda: runTerminal(
                                script="[ -e issue ] && cat issue | echo /etc/issue not found.",
                                workdir="/etc",
                                close_on_exit=False
                            )
                        ),
                        Action(
                            id="notify",
                            text="sendTrayNotification",
                            callable=lambda: sendTrayNotification(
                                title="Title",
                                msg="Message"
                            )
                        )
                    ]

                if dir_open:
                    actions.append(dir_open)

                # Add the item
                #query.add(Item(
                #    id=md_name,
                #    icon=self.doc_to_icon_path(doc),
                #    text=doc.filename,
                 #   subtext=dir,
                 #   completion="",
                 #   actions=actions
                #)#)
        return items

    def setup(self, query):
        results = []
        return results

    def handleQuery(self, query: Query) -> None:
        """Hook that is called by albert with *every new keypress*."""  # noqa
        results = []

        stripped = str(query.string.strip())
        simple_q = f'{stripped}'
        if not query.isValid:
            return


        # Avoid rate limiting
        for _ in range(50):
            time.sleep(0.01)
            if not query.isValid:
                return

        try:
           # if __triggers__  and not query.isTriggered:
           #     return []
            # be backwards compatible with v0.2
            if "disableSort" in dir(query):
                query.disableSort()

            results_setup = self.setup(query)
            if results_setup:
                return results_setup
            
            info(f'Here is the query string ....\'{stripped}\'')
            
            docs = self.query_recoll(f'{simple_q}')
            #results = self.recoll_docs_as_items(docs)

            info(f'{docs}')

        except Exception:  # user to report error
            if dev_mode:  # let exceptions fly!
                print(traceback.format_exc())
                raise

        trash_path = '/home/ben/'

        # First we find duplicates if so configured
        if remove_duplicates:
            docs = self.remove_duplicate_docs(docs)

        for doc in docs:
            path = self.path_from_url(doc.url) # The path is not always given as an attribute by recoll doc
            dir_hit = os.path.dirname(path)


            file_extension = Path(path).suffix # Get the file extension and work out the mimetype
            mime_type = mimetypes.guess_type(file_extension)[0]

            dir_open = self.get_open_dir_action(dir_hit)

            if path:
                actions=[
                        Action(
                            id="clip",
                            text="setClipboardText (ClipAction)",
                            callable=lambda: setClipboardText(text=configLocation())
                        ),
                        Action(
                            id="url",
                            text="openUrl (UrlAction)",
                            callable=lambda: openUrl(url="https://www.google.de")
                        ),
                        Action(
                            id="run",
                            text="runDetachedProcess (ProcAction)",
                            callable=lambda: runDetachedProcess(
                                cmdln=["espeak", "hello"],
                                workdir="~"
                            )
                        ),
                        Action(
                            id="term",
                            text="runTerminal (TermAction)",
                            callable=lambda: runTerminal(
                                script="[ -e issue ] && cat issue | echo /etc/issue not found.",
                                workdir="/etc",
                                close_on_exit=False
                            )
                        ),
                        Action(
                            id="notify",
                            text="sendTrayNotification",
                            callable=lambda: sendTrayNotification(
                                title="Title",
                                msg="Message"
                            )
                        )
                    ]

                if dir_open:
                    actions.append(dir_open)

                # Add the item
                query.add(Item(
                    id=md_name,
                    icon=self.doc_to_icon_path(doc),
                    text=doc.filename,
                    subtext=dir_hit,
                    completion="",
                    actions=actions
                ))
        #query.add(Item(
        #    id="Id",
        #    text="Text",
        #    subtext="Subtext",
        #    icon=["xdg:some-xdg-icon-name",
        #          "qfip:/path/to/file/a/file/icon/provider/can/handle",
        #          ":resource-path",
        #          "/full/path/to/icon/file"],
        #    actions=[Action(
        #        "trash-open",
        #        "Open trash",
        #        lambda path=trash_path: openUrl(path)
        #    )]
        #))


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


    # In case the __triggers__ was not set at all we set it to the empty string
   # try:
    #    __triggers__
    #except NameError:
    #    __triggers__ = ""
