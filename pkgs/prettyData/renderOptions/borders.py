from typing import Any, Union


import ukkoUtils
from appLogging import appLog


################################################################################


class Borders:
    #                                   0...4...8...12..16..20..24
    # | eg:            top___________= "┏━━━┳━━━┳━━━┯━━━┳━━━┳━━━┓",
    # | eg:            title_________= "┃ A ┃ B ┃ C │ D ┃ E ┃ F ┃",
    # | eg:            undTopTitle___= "┣━━━╋━━━╋━━━┿━━━╋━━━╋━━━┫",
    # | eg:            entry_1_______= "┃ A ┃ B ┃ n │ n ┃ E ┃ F ┃",
    # | eg:            betweenEntries= "┠───╂───╂───┼───╂───╂───┨",
    # | eg:            entry_2_______= "┃ A ┃ B ┃ n │ n ┃ E ┃ F ┃",
    # | eg:            overBotTitle__= "┣━━━╋━━━╋━━━┿━━━╋━━━╋━━━┫",
    # | eg:            title_________= "┃ A ┃ B ┃ C │ D ┃ E ┃ F ┃",
    # | eg:            bottom________= "┗━━━┻━━━┻━━━┷━━━┻━━━┻━━━┛")

    class RowBorders:

        def __init__(
            self,
            blankEquiv: str,
            middleDiv: str,
            leftLimit: str = "",
            leftTitleMiddle: str = "",
            leftTitleEdge: str = "",
            rightTitleEdge: str = "",
            rightTitleMiddle: str = "",
            rightLimit: str = "",
        ):
            self.blankEquiv = blankEquiv
            self.midDiv = middleDiv

            self.leftLimit = leftLimit
            self.leftTitleMiddle = leftTitleMiddle
            self.leftTitleEdge = leftTitleEdge
            self.rightTitleEdge = rightTitleEdge
            self.rightTitleMiddle = rightTitleMiddle
            self.rightLimit = rightLimit

    @staticmethod
    def createRowBordersFrom_div(divider: str | None = None) -> RowBorders:
        return Borders.RowBorders(" ", " " if divider is None else divider)

    @staticmethod
    def createRowBordersFrom_template(
        paddingCount: int, template: str = ""
    ) -> RowBorders | None:

        if template == "":
            return None

        # isEmpty=(template=='')

        if len(template) != 25:  # not isEmpty and len(template)!=25:
            appLog.print_warning(
                f"RowBorders.createFrom_template(): Expecting template of length 25: '{template}'"
            )
            return None

        # if isEmpty:
        #    paddingText=' '*paddingCount
        #    return Borders.RowBorders(' ',paddingText+'│'+paddingText)
        # else:

        blankEquiv = template[1]

        leftLimit = template[0]
        leftTitleMiddle = template[4]
        leftTitleEdge = template[8]
        midDiv = template[12]
        rightTitleEdge = template[16]
        rightTitleMiddle = template[20]
        rightLimit = template[24]

        paddingText = blankEquiv * paddingCount

        return Borders.RowBorders(
            blankEquiv,
            paddingText + midDiv + paddingText,
            leftLimit + paddingText,
            paddingText + leftTitleMiddle + paddingText,
            paddingText + leftTitleEdge + paddingText,
            paddingText + rightTitleEdge + paddingText,
            paddingText + rightTitleMiddle + paddingText,
            paddingText + rightLimit,
        )

    def __init__(self):
        self.rowBorders: dict[str, Borders.RowBorders] = {}

    def get(self, name: str) -> Union["Borders.RowBorders", None]:
        result = self.rowBorders.get(name.strip("_ \t"))
        # |x| print(f"!!! Borders.get({ukkoUtils.asJsonStr(name)}) in {ukkoUtils.asJsonStr(list(self.rowBorders.keys()))}={result}")

        return result

    def set(self, name: str | list[str], entry: RowBorders | None):
        if entry:
            for singleName in [name] if isinstance(name, str) else name:
                self.rowBorders[singleName.strip("_")] = entry

    @staticmethod
    def createOrNoneFrom_name(name: str) -> Union["Borders", None]:

        standard_borders: dict[str, Borders] = {
            "outer+vert": Borders.createFrom_template(
                1,
                top___________="┏━━━┳━━━┳━━━┯━━━┳━━━┳━━━┓",
                title_________="┃ A ┃ B ┃ C │ D ┃ E ┃ F ┃",
                undTopTitle___="┣━━━╋━━━╋━━━┿━━━╋━━━╋━━━┫",
                entry_1_______="┃ A ┃ B ┃ n │ n ┃ E ┃ F ┃",
                betweenEntries="",
                entry_2_______="┃ A ┃ B ┃ n │ n ┃ E ┃ F ┃",
                overBotTitle__="┣━━━╋━━━╋━━━┿━━━╋━━━╋━━━┫",
                bottom________="┗━━━┻━━━┻━━━┷━━━┻━━━┻━━━┛",
            ),
            "outer+all": Borders.createFrom_template(
                1,
                top___________="┏━━━┳━━━┳━━━┯━━━┳━━━┳━━━┓",
                title_________="┃ A ┃ B ┃ C │ D ┃ E ┃ F ┃",
                undTopTitle___="┣━━━╋━━━╋━━━┿━━━╋━━━╋━━━┫",
                entry_1_______="┃ A ┃ B ┃ n │ n ┃ E ┃ F ┃",
                betweenEntries="┠───╂───╂───┼───╂───╂───┨",
                entry_2_______="┃ A ┃ B ┃ n │ n ┃ E ┃ F ┃",
                overBotTitle__="┣━━━╋━━━╋━━━┿━━━╋━━━╋━━━┫",
                bottom________="┗━━━┻━━━┻━━━┷━━━┻━━━┻━━━┛",
            ),
            "mild": Borders.createFrom_template(
                1,
                top___________="┌───┬───┬───┬───┬───┬───┐",
                title_________="│ A │ B │ C │ D │ E │ F │",
                undTopTitle___="├───┼───┼───┼───┼───┼───┤",
                entry_1_______="│ A │ B │ n │ n │ E │ F │",
                betweenEntries="",
                entry_2_______="│ A │ B │ n │ n │ E │ F │",
                overBotTitle__="├───┼───┼───┼───┼───┼───┤",
                bottom________="└───┴───┴───┴───┴───┴───┘",
            ),
            "rounded": Borders.createFrom_template(
                1,
                top___________="╭───┬───┬───┬───┬───┬───╮",
                title_________="│ A │ B │ C │ D │ E │ F │",
                undTopTitle___="├───┼───┼───┼───┼───┼───┤",
                entry_1_______="│ A │ B │ n │ n │ E │ F │",
                betweenEntries="",
                entry_2_______="│ A │ B │ n │ n │ E │ F │",
                overBotTitle__="├───┼───┼───┼───┼───┼───┤",
                bottom________="╰───┴───┴───┴───┴───┴───╯",
            ),
            "blank": Borders.createFrom_divider(" "),
            "|": Borders.createFrom_divider(" │ "),
        }
        if name in standard_borders:
            return standard_borders[name]
        else:
            appLog.print_warning(
                f"Borders.createOrNoneFrom_name({name}) ignored.  Only valid entries are {ukkoUtils.asJsonStr(list(standard_borders.keys()))}"
            )
            return None

    @staticmethod
    def createFrom_template(
        paddingCount: int,
        top___________: str,
        title_________: str,
        undTopTitle___: str,
        entry_1_______: str,
        betweenEntries: str,
        entry_2_______: str,
        overBotTitle__: str,
        bottom________: str,
    ) -> "Borders":
        result = Borders()

        result.set(
            "top",
            Borders.createRowBordersFrom_template(paddingCount, top___________),
        )
        result.set(
            "title",
            Borders.createRowBordersFrom_template(paddingCount, title_________),
        )
        result.set(
            "undTopTitle",
            Borders.createRowBordersFrom_template(paddingCount, undTopTitle___),
        )
        result.set(
            "entry",
            Borders.createRowBordersFrom_template(paddingCount, entry_1_______),
        )
        result.set(
            "betweenEntries",
            Borders.createRowBordersFrom_template(paddingCount, betweenEntries),
        )
        result.set(
            "overBotTitle",
            Borders.createRowBordersFrom_template(paddingCount, overBotTitle__),
        )
        result.set(
            "bottom",
            Borders.createRowBordersFrom_template(paddingCount, bottom________),
        )
        return result

    @staticmethod
    def createFrom_divider(divider: str | None) -> "Borders":
        result = Borders()
        result.set(["entry", "title"], Borders.createRowBordersFrom_div(divider))
        return result

    @staticmethod
    def createFrom_dict(src: dict[str, Any] | str | Any | None) -> "Borders":

        if type(src) is str:
            result = Borders.createOrNoneFrom_name(src)
            if result is not None:
                return result
        if type(src) is dict:

            if "divider" in src:
                return Borders.createFrom_divider(src["divider"])

            if "template" in src:
                template: dict[str, Any] = src["template"]
                return Borders.createFrom_template(
                    template.get("paddingCount", 0),
                    template.get("top___________", ""),
                    template.get("title_________", ""),
                    template.get("undTopTitle___", ""),
                    template.get("entry_________", ""),
                    template.get("betweenEntries", ""),
                    "",
                    template.get("overBotTitle__", ""),
                    template.get("bottom________", ""),
                )
        return Borders.createFrom_divider(" ")
