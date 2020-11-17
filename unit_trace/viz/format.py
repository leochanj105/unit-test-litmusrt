"""Various formatting parameters intended to be accessible by the client."""

class FontOptions(object):
    """Class for combining assorted simple font options."""
    def __init__(self, name, size, color):
        self.name = name
        self.size = size
        self.color = color

class AlignMode(object):
    """Type that specifies the way something (probably text)
    should be aligned, horizontally and/or vertically."""
    LEFT = 0
    CENTER = 1
    RIGHT = 2

    BOTTOM = 3
    TOP = 4

class GraphFormat(object):
    """Container class for a bunch of optional and non-optional attributes to configure the appearance of the graph
    (because it would be annoying to just have these all as raw arguments to the Graph constructor, and many people
    probably don't care about most of them anyway)."""

    GRID_COLOR = (0.7, 0.7, 0.7)
    HIGHLIGHT_COLOR = (0.85, 0.0, 0.0)
    BORDER_COLOR = (0.0, 0.0, 0.0)
    LITE_BORDER_COLOR = (0.4, 0.4, 0.4)

    BORDER_THICKNESS = 1
    GRID_THICKNESS = 1
    AXIS_THICKNESS = 1

    BAND_THICKNESS = 1.5
    BAND_COLOR = (0.85, 0.0, 0.0)

    X_AXIS_MEASURE_OFS = 30
    X_AXIS_LABEL_GAP = 10
    Y_AXIS_ITEM_GAP = 10
    MAJ_TICK_SIZE = 20
    MIN_TICK_SIZE = 12

    BIG_ARROWHEAD_FACTOR = 0.2
    SMALL_ARROWHEAD_FACTOR = 0.3
    TEE_FACTOR = 0.3

    DEF_FOPTS_LABEL = FontOptions("Times", 16, (0.0, 0.0, 0.0))
    DEF_FOPTS_LABEL_SSCRIPT = FontOptions("Times", 8, (0.0, 0.0, 0.0))
    DEF_FOPTS_MAJ = FontOptions("Times", 14, (0.1, 0.1, 0.1))
    DEF_FOPTS_MIN = FontOptions("Times", 9, (0.1, 0.1, 0.1))
    DEF_FOPTS_ITEM = FontOptions("Times", 20, (0.0, 0.5, 0.1))
    DEF_FOPTS_BAR = FontOptions("Times", 14, (0.0, 0.0, 0.0))
    DEF_FOPTS_BAR_SSCRIPT = FontOptions("Times", 7, (0.0, 0.0, 0.0))
    DEF_FOPTS_MINI_BAR = FontOptions("Times", 11, (0.0, 0.0, 0.0))
    DEF_FOPTS_MINI_BAR_SSCRIPT = FontOptions("Times", 7, (0.0, 0.0, 0.0))
    DEF_FOPTS_ARROW = FontOptions("Times", 12, (0.0, 0.0, 0.0))
    DEF_FOPTS_ARROW_SSCRIPT = FontOptions("Times", 7, (0.0, 0.0, 0.0))

    LEFT_SIDE_PAD = 30
    WIDTH_PAD = 50
    HEIGHT_PAD = 150
    Y_ITEM_PAD_FACTOR = 0.5

    DEF_TIME_PER_MAJ = 10
    DEF_MAJ_SEP = 200
    DEF_MIN_PER_MAJ = 5
    DEF_Y_ITEM_SIZE = 50

    AXIS_LABEL_VERT_OFS = 30
    BAR_SIZE_FACTOR = 0.4
    MINI_BAR_SIZE_FACTOR = 0.2
    BAR_MINI_BAR_GAP_FACTOR = 0.1

    BAR_LABEL_OFS = 2
    MINI_BAR_LABEL_OFS = 1
    ARROW_LABEL_OFS = 2

    BLOCK_TRIANGLE_FACTOR = 0.7
    BIG_ARROW_FACTOR = 1.6
    SMALL_ARROW_FACTOR = 0.6
    COMPLETION_MARKER_FACTOR = 1.6

    def __init__(self, time_per_maj=DEF_TIME_PER_MAJ, maj_sep=DEF_MAJ_SEP,
    min_per_maj=DEF_MIN_PER_MAJ, y_item_size=DEF_Y_ITEM_SIZE, bar_fopts=DEF_FOPTS_BAR,
    item_fopts=DEF_FOPTS_ITEM, show_min=False, majfopts=DEF_FOPTS_MAJ,
    minfopts=DEF_FOPTS_MIN):
        self.time_per_maj = time_per_maj
        self.maj_sep = maj_sep
        self.min_per_maj = min_per_maj
        self.y_item_size = y_item_size
        self.item_fopts = item_fopts
        self.bar_fopts = bar_fopts
        self.show_min = show_min
        self.majfopts = majfopts
        self.minfopts = minfopts
