#!/usr/bin/python

"""Classes related to the drawing and area-selection primitives. Note that
this file is quite low-level, in that its objects are mostly restricted to
dealing with drawing the components of a real-time graph given coordinates
rather than having an abstract knowledge of the graph's measurements or
any information about events."""

import math
import cairo
import os
import copy

import util
from format import *

def snap(pos):
    """Takes in an x- or y-coordinate ``pos'' and snaps it to the pixel grid.
    This is necessary because integer coordinates in Cairo actually denote
    the spaces between pixels, not the pixels themselves, so if we draw a
    line of width 1 on integer coordinates, it will come out blurry unless we shift it,
    since the line will get distributed over two pixels. We actually apply this to all
    coordinates to make sure everything is aligned."""
    return pos - 0.5

class Surface(object):
    def __init__(self, fname='temp', ctx=None):
        self.virt_x = 0
        self.virt_y = 0
        self.surface = None
        self.width = 0
        self.height = 0
        self.scale = 1.0
        self.fname = fname
        self.ctx = ctx

    def renew(self, width, height):
        raise NotImplementedError

    def change_ctx(self, ctx):
        self.ctx = ctx

    def get_fname(self):
        return self.fname

    def write_out(self, fname):
        raise NotImplementedError

    def pan(self, x, y, width, height):
        """A surface actually represents just a ``window'' into
        what we are drawing on. For instance, if we are scrolling through
        a graph, then the surface represents the area in the GUI window,
        not the entire graph (visible or not). So this method basically
        moves the ``window's'' upper-left corner to (x, y), and resizes
        the dimensions to (width, height)."""
        self.virt_x = x
        self.virt_y = y
        self.width = width
        self.height = height

    def set_scale(self, scale):
        """Sets the scale factor."""
        self.scale = scale

    def get_real_coor(self, x, y):
        """Translates the coordinates (x, y)
        in the ``theoretical'' plane to the true (x, y) coordinates on this surface
        that we should draw to. Note that these might actually be outside the
        bounds of the surface,
        if we want something outside the surface's ``window''."""
        return (x - self.virt_x * self.scale, y - self.virt_y * self.scale)

    def get_virt_coor(self, x, y):
        """Does the inverse of the last method."""
        return (x + self.virt_x * self.scale, y + self.virt_y * self.scale)

    def get_virt_coor_unscaled(self, x, y):
        """Does the same, but removes the scale factor (i.e. behaves as if
        the scale was 1.0 all along)."""
        return (x / self.scale + self.virt_x, y / self.scale + self.virt_y)

class SVGSurface(Surface):
    def renew(self, width, height):
        iwidth = int(math.ceil(width))
        iheight = int(math.ceil(height))
        self.surface = cairo.SVGSurface(self.fname, iwidth, iheight)
        self.ctx = cairo.Context(self.surface)

    def write_out(self, fname):
        os.execl('cp', self.fname, fname)

class ImageSurface(Surface):
    def renew(self, width, height):
        iwidth = int(math.ceil(width))
        iheight = int(math.ceil(height))
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, iwidth, iheight)
        self.ctx = cairo.Context(self.surface)

    def write_out(self, fname):
        if self.surface is None:
            raise ValueError('Don\'t own surface, can\'t write to to file')

        self.surface.write_to_png(fname)

class Pattern(object):
    DEF_STRIPE_SIZE = 10
    MAX_FADE_WIDTH = 250

    def __init__(self, color_list, stripe_size=DEF_STRIPE_SIZE):
        self.color_list = color_list
        self.stripe_size = stripe_size

    def render_on_canvas(self, canvas, x, y, width, height, fade=False):
        fade_span = min(width, Pattern.MAX_FADE_WIDTH)

        if len(self.color_list) == 1:
            if fade:
                canvas.fill_rect_fade(x, y, fade_span, height, (1.0, 1.0, 1.0), \
                    self.color_list[0])
            else:
                canvas.fill_rect(x, y, width, height, self.color_list[0])

            if width > Pattern.MAX_FADE_WIDTH:
                    canvas.fill_rect(x + Pattern.MAX_FADE_WIDTH, y, width - Pattern.MAX_FADE_WIDTH,
                                     height, self.color_list[0])
        else:
            n = 0
            bottom = y + height
            while y < bottom:
                i = n % len(self.color_list)
                if fade:
                    canvas.fill_rect_fade(x, y, fade_span, \
                        min(self.stripe_size, bottom - y), (1.0, 1.0, 1.0), self.color_list[i])
                else:
                    canvas.fill_rect(x, y, width, min(self.stripe_size, bottom - y), self.color_list[i])

                if width > Pattern.MAX_FADE_WIDTH:
                    canvas.fill_rect(x + Pattern.MAX_FADE_WIDTH, y, width - Pattern.MAX_FADE_WIDTH,
                                     min(self.stripe_size, bottom - y), self.color_list[i])

                y += self.stripe_size
                n += 1

class Canvas(object):
    """This is a basic class that stores and draws on a Cairo surface,
    using various primitives related to drawing a real-time graph (up-arrows,
    down-arrows, bars, ...).

    This is the lowest-level representation (aside perhaps from the Cairo
    surface itself) of a real-time graph. It allows the user to draw
    primitives at certain locations, but for the most part does not know
    anything about real-time scheduling, just how to draw the basic parts
    that make up a schedule graph. For that, see Graph or its descendants."""

    BOTTOM_LAYER = 0
    MIDDLE_LAYER = 1
    TOP_LAYER = 2

    LAYERS = (BOTTOM_LAYER, MIDDLE_LAYER, TOP_LAYER)

    NULL_PATTERN = -1

    SQRT3 = math.sqrt(3.0)

    def __init__(self, width, height, item_clist, bar_plist, surface):
        """Creates a new Canvas of dimensions (width, height). The
        parameters ``item_plist'' and ``bar_plist'' each specify a list
        of patterns to choose from when drawing the items on the y-axis
        or filling in bars, respectively."""

        self.surface = surface

        self.width = int(math.ceil(width))
        self.height = int(math.ceil(height))
        self.item_clist = item_clist
        self.bar_plist = bar_plist

        self.selectable_regions = {}

        self.scale = 1.0

    # clears the canvas.
    def clear(self):
        raise NotImplementedError

    def set_scale(self, scale):
        self.scale = scale
        self.surface.set_scale(scale)
        for event in self.selectable_regions:
            self.selectable_regions[event].set_scale(scale)

    def scaled(self, *coors):
        """Scales a series of coordinates."""
        return [coor * self.scale for coor in coors]

    def unscaled(self, *coors):
        """Inverse of scale()."""
        return [coor / self.scale for coor in coors]

    def draw_rect(self, x, y, width, height, color, thickness, snap=True):
        """Draws a rectangle somewhere (border only)."""
        raise NotImplementedError

    def fill_rect(self, x, y, width, height, color, snap=True):
        """Draws a filled rectangle somewhere. ``color'' is a 3-tuple."""
        raise NotImplementedError

    def fill_rect_fade(self, x, y, width, height, lcolor, rcolor, snap=True):
        """Draws a rectangle somewhere, filled in with the fade."""
        raise NotImplementedError

    def draw_line(self, p0, p1, color, thickness, snap=True):
        """Draws a line from p0 to p1 with a certain color and thickness."""
        raise NotImplementedError

    def draw_polyline(self, coor_list, color, thickness, snap=True):
        """Draws a polyline, where coor_list = [(x_0, y_0), (x_1, y_1), ... (x_m, y_m)]
        specifies a polyline from (x_0, y_0) to (x_1, y_1), etc."""
        raise NotImplementedError

    def fill_polyline(self, coor_list, color, thickness, snap=True):
        """Draws a polyline (probably a polygon) and fills it."""
        raise NotImplementedError

    def draw_label(self, text, x, y, fopts=GraphFormat.DEF_FOPTS_LABEL,
                   halign=AlignMode.LEFT, valign=AlignMode.BOTTOM, snap=True):
        """Draws text at a position with a certain alignment."""
        raise NotImplementedError

    def draw_label_with_sscripts(self, text, supscript, subscript, x, y, \
                                 textfopts=GraphFormat.DEF_FOPTS_LABEL,
                                 sscriptfopts=GraphFormat.DEF_FOPTS_LABEL_SSCRIPT, \
                                 halign=AlignMode.LEFT, valign=AlignMode.BOTTOM, snap=True):
        """Draws text at a position with a certain alignment, along with optionally a superscript and
        subscript (which are None if either is not used.)"""
        raise NotImplementedError

    def draw_y_axis(self, x, y, height):
        """Draws the y-axis, starting from the bottom at the point x, y."""
        self.surface.ctx.set_source_rgb(0.0, 0.0, 0.0)

        self.draw_line((x, y), (x, y - height), (0.0, 0.0, 0.0), GraphFormat.AXIS_THICKNESS)

    def draw_y_axis_labels(self, x, y, height, item_list, item_size, fopts=None):
        """Draws the item labels on the y-axis. ``item_list'' is the list
        of strings to print, while item_size gives the vertical amount of
        space that each item shall take up, in pixels."""
        if fopts is None:
            fopts = GraphFormat.DEF_FOPTS_ITEM

        x -= GraphFormat.Y_AXIS_ITEM_GAP
        y -= height - item_size / 2.0

        orig_color = fopts.color
        for ctr, item in enumerate(item_list):
            fopts.color = self.get_item_color(ctr)
            self.draw_label(item, x, y, fopts, AlignMode.RIGHT, AlignMode.CENTER)
            y += item_size

        fopts.color = orig_color

    def draw_x_axis(self, x, y, start_tick, end_tick, maj_sep, min_per_maj):
        """Draws the x-axis, including all the major and minor ticks (but not the labels).
        ``num_maj'' gives the number of major ticks, ``maj_sep'' the number of pixels between
        major ticks, and ``min_per_maj'' the number of minor ticks between two major ticks
        (including the first major tick)"""
        self.draw_line((x, y), (x + GraphFormat.X_AXIS_MEASURE_OFS, y),
                       (0.0, 0.0, 0.0), GraphFormat.AXIS_THICKNESS)
        x += GraphFormat.X_AXIS_MEASURE_OFS + start_tick * maj_sep

        for i in range(start_tick, end_tick + 1):
            self.draw_line((x, y), (x, y + GraphFormat.MAJ_TICK_SIZE),
                           (0.0, 0.0, 0.0), GraphFormat.AXIS_THICKNESS)

            if (i < end_tick):
                for j in range(0, min_per_maj):
                    self.draw_line((x, y), (x + maj_sep / min_per_maj, y),
                        (0.0, 0.0, 0.0), GraphFormat.AXIS_THICKNESS)

                    x += 1.0 * maj_sep / min_per_maj
                    if j < min_per_maj - 1:
                        self.draw_line((x, y), (x, y + GraphFormat.MIN_TICK_SIZE),
                        (0.0, 0.0, 0.0), GraphFormat.AXIS_THICKNESS)

    def draw_x_axis_labels(self, x, y, start_tick, end_tick, maj_sep, min_per_maj, start=0, incr=1, show_min=False, \
                           majfopts=GraphFormat.DEF_FOPTS_MAJ, minfopts=GraphFormat.DEF_FOPTS_MIN):
        """Draws the labels for the x-axis. (x, y) should give the origin.
        how far down you want the text. ``incr'' gives the increment per major
        tick. ``start'' gives the value of the first tick. ``show_min'' specifies
        whether to draw labels at minor ticks."""

        x += GraphFormat.X_AXIS_MEASURE_OFS + start_tick * maj_sep
        y += GraphFormat.X_AXIS_LABEL_GAP + GraphFormat.MAJ_TICK_SIZE

        minincr = incr / (min_per_maj * 1.0)

        cur = start * 1.0

        for i in range(start_tick, end_tick + 1):
            text = util.format_float(cur, 2)
            self.draw_label(text, x, y, majfopts, AlignMode.CENTER, AlignMode.TOP)

            if (i < end_tick):
                if show_min:
                    for j in range(0, min_per_maj):
                        x += 1.0 * maj_sep / min_per_maj
                        cur += minincr
                        text = util.format_float(cur, 2)

                        if j < min_per_maj - 1:
                            self.draw_label(text, x, y, minfopts, AlignMode.CENTER, AlignMode.TOP)
                else:
                    x += maj_sep
                    cur += incr

    def draw_grid(self, x, y, height, start_tick, end_tick, start_item, end_item, maj_sep, item_size, \
                  min_per_maj=None, show_min=False):
        """Draws a grid dividing along the item boundaries and the major ticks.
        (x, y) gives the origin. ``show_min'' specifies whether to draw vertical grid lines at minor ticks.
        ``start_tick'' and ``end_tick'' give the major ticks to start and end at for drawing vertical lines.
        ``start_item'' and ``end_item'' give the item boundaries to start and end drawing horizontal lines."""
        if start_tick > end_tick or start_item > end_item:
            return

        line_width = (end_tick - start_tick) * maj_sep
        line_height = (end_item - start_item) * item_size

        origin = (x, y)

        # draw horizontal lines first
        x = origin[0] + GraphFormat.X_AXIS_MEASURE_OFS + start_tick * maj_sep
        y = origin[1] - height + start_item * item_size
        for i in range(start_item, end_item + 1):
            self.draw_line((x, y), (x + line_width, y), GraphFormat.GRID_COLOR, GraphFormat.GRID_THICKNESS)
            y += item_size

        x = origin[0] + GraphFormat.X_AXIS_MEASURE_OFS + start_tick * maj_sep
        y = origin[1] - height + start_item * item_size

        if show_min:
            for i in range(0, (end_tick - start_tick) * min_per_maj + 1):
                self.draw_line((x, y), (x, y + line_height), GraphFormat.GRID_COLOR, GraphFormat.GRID_THICKNESS)
                x += maj_sep * 1.0 / min_per_maj
        else:
            for i in range(start_tick, end_tick + 1):
                self.draw_line((x, y), (x, y + line_height), GraphFormat.GRID_COLOR, GraphFormat.GRID_THICKNESS)
                x += maj_sep

    def draw_bar(self, x, y, width, height, n, clip_side, selected):
        """Draws a bar with a certain set of dimensions, using pattern ``n'' from the
        bar pattern list."""

        color, thickness = {False : (GraphFormat.BORDER_COLOR, GraphFormat.BORDER_THICKNESS),
                            True : (GraphFormat.HIGHLIGHT_COLOR, GraphFormat.BORDER_THICKNESS * 2.0)}[selected]

        # use a pattern to be pretty
        self.get_bar_pattern(n).render_on_canvas(self, x, y, width, height, True)

        self.draw_rect(x, y, width, height, color, thickness, clip_side)

    def add_sel_bar(self, x, y, width, height, event):
        self.add_sel_region(SelectableRegion(x, y, width, height, event))

    def draw_mini_bar(self, x, y, width, height, n, clip_side, selected):
        """Like the above, except it draws a miniature version. This is usually used for
        secondary purposes (i.e. to show jobs that _should_ have been running at a certain time).

        Of course we don't enforce the fact that this is mini, since the user can pass in width
        and height (but the mini bars do look slightly different: namely the borders are a different
        color)"""

        color, thickness = {False : (GraphFormat.LITE_BORDER_COLOR, GraphFormat.BORDER_THICKNESS),
                            True : (GraphFormat.HIGHLIGHT_COLOR, GraphFormat.BORDER_THICKNESS * 1.5)}[selected]

        self.get_bar_pattern(n).render_on_canvas(self, x, y, width, height, True)

        self.draw_rect(x, y, width, height, color, thickness, clip_side)

    def add_sel_mini_bar(self, x, y, width, height, event):
        self.add_sel_region(SelectableRegion(x, y, width, height, event))

    def draw_completion_marker(self, x, y, height, selected):
        """Draws the symbol that represents a job completion, using a certain height."""

        color = {False : GraphFormat.BORDER_COLOR, True : GraphFormat.HIGHLIGHT_COLOR}[selected]
        self.draw_line((x - height * GraphFormat.TEE_FACTOR / 2.0, y),
                       (x + height * GraphFormat.TEE_FACTOR / 2.0, y),
                       color, GraphFormat.BORDER_THICKNESS)
        self.draw_line((x, y), (x, y + height), color, GraphFormat.BORDER_THICKNESS)

    def add_sel_completion_marker(self, x, y, height, event):
        self.add_sel_region(SelectableRegion(x - height * GraphFormat.TEE_FACTOR / 2.0, y,
            height * GraphFormat.TEE_FACTOR, height, event))

    def draw_release_arrow_big(self, x, y, height, selected):
        """Draws a release arrow of a certain height: (x, y) should give the top
        (northernmost point) of the arrow. The height includes the arrowhead."""
        big_arrowhead_height = GraphFormat.BIG_ARROWHEAD_FACTOR * height

        color = {False : GraphFormat.BORDER_COLOR, True : GraphFormat.HIGHLIGHT_COLOR}[selected]
        colors = [(1.0, 1.0, 1.0), color]
        draw_funcs = [self.__class__.fill_polyline, self.__class__.draw_polyline]
        for i in range(0, 2):
            color = colors[i]
            draw_func = draw_funcs[i]

            draw_func(self, [(x, y), (x - big_arrowhead_height / Canvas.SQRT3, y + big_arrowhead_height), \
                       (x + big_arrowhead_height / Canvas.SQRT3, y + big_arrowhead_height), (x, y)], \
                       color, GraphFormat.BORDER_THICKNESS)

        self.draw_line((x, y + big_arrowhead_height), (x, y + height), color, GraphFormat.BORDER_THICKNESS)

    def add_sel_release_arrow_big(self, x, y, height, event):
        self.add_sel_arrow_big(x, y, height, event)

    def draw_deadline_arrow_big(self, x, y, height, selected):
        """Draws a release arrow: x, y should give the top (northernmost
        point) of the arrow. The height includes the arrowhead."""
        big_arrowhead_height = GraphFormat.BIG_ARROWHEAD_FACTOR * height

        color = {False : GraphFormat.BORDER_COLOR, True : GraphFormat.HIGHLIGHT_COLOR}[selected]
        colors = [(1.0, 1.0, 1.0), color]
        draw_funcs = [self.__class__.fill_polyline, self.__class__.draw_polyline]
        for i in range(0, 2):
            color = colors[i]
            draw_func = draw_funcs[i]

            draw_func(self, [(x, y + height), (x - big_arrowhead_height / Canvas.SQRT3, \
                        y + height - big_arrowhead_height), \
                        (x + big_arrowhead_height / Canvas.SQRT3, \
                        y + height - big_arrowhead_height), \
                        (x, y + height)], color, GraphFormat.BORDER_THICKNESS)

        self.draw_line((x, y), (x, y + height - big_arrowhead_height),
                       color, GraphFormat.BORDER_THICKNESS)

    def add_sel_deadline_arrow_big(self, x, y, height, event):
        self.add_sel_arrow_big(x, y, height, event)

    def add_sel_arrow_big(self, x, y, height, event):
        big_arrowhead_height = GraphFormat.BIG_ARROWHEAD_FACTOR * height

        self.add_sel_region(SelectableRegion(x - big_arrowhead_height / Canvas.SQRT3,
            y, 2.0 * big_arrowhead_height / Canvas.SQRT3, height, event))

    def draw_action_symbol(self, item, action, x, y, height, selected):
        """Draws a release arrow: x, y should give the top (northernmost
        point) of the arrow. The height includes the arrowhead."""

        color = {False : GraphFormat.BORDER_COLOR,
                 True : GraphFormat.HIGHLIGHT_COLOR}[selected]

        colors = [self.get_bar_pattern(item).get_color_list()[0], color]
        draw_funcs = [self.__class__.fill_polyline, self.__class__.draw_polyline]

        for i in range(0, 2):
            color = colors[i]
            draw_func = draw_funcs[i]

            draw_func(self, [(x, y), (x - height / Canvas.SQRT3, \
                        y - height), \
                        (x + height / Canvas.SQRT3, \
                        y - height), \
                        (x, y)], color, GraphFormat.BORDER_THICKNESS)

        self.draw_label(str(action), x, y - height / 2 - .1 * height,
                        GraphFormat.DEF_FOPTS_LABEL,
                        AlignMode.CENTER, AlignMode.CENTER, True)

    def add_sel_action_symbol(self, x, y, height, event):
        self.add_sel_region(SelectableRegion(x - height / Canvas.SQRT3,
            y - height, 2.0 * height / Canvas.SQRT3, height, event))

    def draw_release_arrow_small(self, x, y, height, selected):
        """Draws a small release arrow (most likely coming off the x-axis, although
        this method doesn't enforce this): x, y should give the top of the arrow"""
        small_arrowhead_height = GraphFormat.SMALL_ARROWHEAD_FACTOR * height

        color = {False : GraphFormat.BORDER_COLOR, 
                 True : GraphFormat.HIGHLIGHT_COLOR}[selected]

        self.draw_line((x, y),
                       (x - small_arrowhead_height, y + small_arrowhead_height),
                       color, GraphFormat.BORDER_THICKNESS)
        self.draw_line((x, y), (x + small_arrowhead_height, y + small_arrowhead_height), \
                       color, GraphFormat.BORDER_THICKNESS)
        self.draw_line((x, y), (x, y + height), color, GraphFormat.BORDER_THICKNESS)

    def add_sel_release_arrow_small(self, x, y, height, event):
        self.add_sel_arrow_small(x, y, height, event)

    def draw_deadline_arrow_small(self, x, y, height, selected):
        """Draws a small deadline arrow (most likely coming off the x-axis, although
        this method doesn't enforce this): x, y should give the top of the arrow"""
        small_arrowhead_height = GraphFormat.SMALL_ARROWHEAD_FACTOR * height

        color = {False : GraphFormat.BORDER_COLOR, True : GraphFormat.HIGHLIGHT_COLOR}[selected]

        self.draw_line((x, y), (x, y + height), color, GraphFormat.BORDER_THICKNESS)
        self.draw_line((x - small_arrowhead_height, y + height - small_arrowhead_height), \
                       (x, y + height), color, GraphFormat.BORDER_THICKNESS)
        self.draw_line((x + small_arrowhead_height, y + height - small_arrowhead_height), \
                       (x, y + height), color, GraphFormat.BORDER_THICKNESS)

    def add_sel_deadline_arrow_small(self, x, y, height, event):
        self.add_sel_arrow_small(x, y, height, event)

    def add_sel_arrow_small(self, x, y, height, event):
        small_arrowhead_height = GraphFormat.SMALL_ARROWHEAD_FACTOR * height

        self.add_sel_region(SelectableRegion(x - small_arrowhead_height, y,
            small_arrowhead_height * 2.0, height, event))

    def draw_suspend_triangle(self, x, y, height, selected):
        """Draws the triangle that marks a suspension. (x, y) gives the topmost (northernmost) point
        of the symbol."""

        color = {False : GraphFormat.BORDER_COLOR, True : GraphFormat.HIGHLIGHT_COLOR}[selected]
        colors = [(0.0, 0.0, 0.0), color]

        draw_funcs = [self.__class__.fill_polyline, self.__class__.draw_polyline]
        for i in range(0, 2):
            color = colors[i]
            draw_func = draw_funcs[i]
            draw_func(self, [(x, y), (x + height / 2.0, y + height / 2.0), (x, y + height), (x, y)], \
                      color, GraphFormat.BORDER_THICKNESS)

    def add_sel_suspend_triangle(self, x, y, height, event):
        self.add_sel_region(SelectableRegion(x, y, height / 2.0, height, event))

    def draw_resume_triangle(self, x, y, height, selected):
        """Draws the triangle that marks a resumption. (x, y) gives the topmost (northernmost) point
        of the symbol."""

        color = {False : GraphFormat.BORDER_COLOR, True : GraphFormat.HIGHLIGHT_COLOR}[selected]
        colors = [(1.0, 1.0, 1.0), color]

        draw_funcs = [self.__class__.fill_polyline, self.__class__.draw_polyline]
        for i in range(0, 2):
            color = colors[i]
            draw_func = draw_funcs[i]
            draw_func(self, [(x, y), (x - height / 2.0, y + height / 2.0), (x, y + height), (x, y)], \
                      color, GraphFormat.BORDER_THICKNESS)

    def add_sel_resume_triangle(self, x, y, height, event):
        self.add_sel_region(SelectableRegion(x - height / 2.0, y, height / 2.0, height, event))

    def clear_selectable_regions(self):
        self.selectable_regions = {}

    #def clear_selectable_regions(self, real_x, real_y, width, height):
    #    x, y = self.surface.get_virt_coor(real_x, real_y)
    #    for event in self.selectable_regions.keys():
    #        if self.selectable_regions[event].intersects(x, y, width, height):
    #            del self.selectable_regions[event]

    def add_sel_region(self, region):
        region.set_scale(self.scale)
        self.selectable_regions[region.get_event()] = region

    def get_sel_region(self, event):
        return self.selectable_regions[event]

    def has_sel_region(self, event):
        return event in self.selectable_regions

    def get_selected_regions(self, real_x, real_y, width, height):
        x, y = self.surface.get_virt_coor(real_x, real_y)

        selected = {}
        for event in self.selectable_regions:
            region = self.selectable_regions[event]
            if region.intersects(x, y, width, height):
                selected[event] = region

        return selected

    def whiteout(self):
        """Overwrites the surface completely white, but technically doesn't delete anything"""
        # Make sure we don't scale here (we want to literally white out just this region)

        x, y = self.surface.get_virt_coor_unscaled(0, 0)
        width, height = self.unscaled(self.surface.width, self.surface.height)

        self.fill_rect(x, y, width, height, (1.0, 1.0, 1.0), False)

    def get_item_color(self, n):
        """Gets the nth color in the item color list, which are the colors used to draw the items
        on the y-axis. Note that there are conceptually infinitely
        many patterns because the patterns repeat -- that is, we just mod out by the size of the pattern
        list when indexing."""
        return self.item_clist[n % len(self.item_clist)]

    def get_bar_pattern(self, n):
        """Gets the nth pattern in the bar pattern list, which is a list of surfaces that are used to
        fill in the bars. Note that there are conceptually infinitely
        many patterns because the patterns repeat -- that is, we just mod out by the size of the pattern
        list when indexing."""
        if n < 0:
            return self.bar_plist[-1]
        return self.bar_plist[n % (len(self.bar_plist) - 1)]

class CairoCanvas(Canvas):
    """This is a basic class that stores and draws on a Cairo surface,
    using various primitives related to drawing a real-time graph (up-arrows,
    down-arrows, bars, ...).

    This is the lowest-level non-abstract representation
    (aside perhaps from the Cairo surface itself) of a real-time graph.
    It allows the user to draw primitives at certain locations, but for
    the most part does not know anything about real-time scheduling,
    just how to draw the basic parts that make up a schedule graph.
    For that, see Graph or its descendants."""

    #def __init__(self, fname, width, height, item_clist, bar_plist, surface):
    #    """Creates a new Canvas of dimensions (width, height). The
    #    parameters ``item_plist'' and ``bar_plist'' each specify a list
    #    of patterns to choose from when drawing the items on the y-axis
    #    or filling in bars, respectively."""

    #    super(CairoCanvas, self).__init__(fname, width, height, item_clist, bar_plist, surface)

    #def clear(self):
    #    self.surface = self.SurfaceType(self.width, self.height, self.fname)
    #    self.whiteout()

    def get_surface(self):
        """Gets the Surface that we are drawing on in its current state."""
        return self.surface

    def _rect_common(self, x, y, width, height, color, thickness, clip_side=None, do_snap=True):
        EXTRA_FACTOR = 2.0

        x, y, width, height = self.scaled(x, y, width, height)
        x, y = self.surface.get_real_coor(x, y)
        max_width = self.surface.width + EXTRA_FACTOR * thickness
        max_height = self.surface.height + EXTRA_FACTOR * thickness

        # if dimensions are really large this can cause Cairo problems --
        # so clip it to the size of the surface, which is the only part we see anyway
        if x < 0:
            width += x
            x = 0
        if y < 0:
            height += y
            y = 0
        if width > max_width:
            width = max_width
        if height > max_height:
            height = max_height

        if do_snap:
            x = snap(x)
            y = snap(y)

        if clip_side == AlignMode.LEFT:
            self.surface.ctx.move_to(x, y)
            self.surface.ctx.line_to(x + width, y)
            self.surface.ctx.line_to(x + width, y + height)
            self.surface.ctx.line_to(x, y + height)
        elif clip_side == AlignMode.RIGHT:
            self.surface.ctx.move_to(x + width, y)
            self.surface.ctx.line_to(x, y)
            self.surface.ctx.line_to(x, y + height)
            self.surface.ctx.line_to(x + width, y + height)
        else:
            # don't clip one edge of the rectangle -- just draw a Cairo rectangle
            self.surface.ctx.rectangle(x, y, width, height)

        self.surface.ctx.set_line_width(thickness * self.scale)
        self.surface.ctx.set_source_rgb(color[0], color[1], color[2])

    def draw_rect(self, x, y, width, height, color, thickness, clip_side=None, do_snap=True):
        self._rect_common(x, y, width, height, color, thickness, clip_side, do_snap)
        self.surface.ctx.stroke()

    def fill_rect(self, x, y, width, height, color, do_snap=True):
        self._rect_common(x, y, width, height, color, 1, do_snap)
        self.surface.ctx.fill()

    def fill_rect_fade(self, x, y, width, height, lcolor, rcolor, do_snap=True):
        """Draws a rectangle somewhere, filled in with the fade."""
        x, y, width, height = self.scaled(x, y, width, height)
        x, y = self.surface.get_real_coor(x, y)

        if do_snap:
            linear = cairo.LinearGradient(snap(x), snap(y), \
                                      snap(x + width), snap(y + height))
        else:
            linear = cairo.LinearGradient(x, y, \
                                      x + width, y + height)
        linear.add_color_stop_rgb(0.0, lcolor[0], lcolor[1], lcolor[2])
        linear.add_color_stop_rgb(1.0, rcolor[0], rcolor[1], rcolor[2])
        self.surface.ctx.set_source(linear)
        if do_snap:
            self.surface.ctx.rectangle(snap(x), snap(y), width, height)
        else:
            self.surface.ctx.rectangle(x, y, width, height)
        self.surface.ctx.fill()

    def draw_line(self, p0, p1, color, thickness, do_snap=True):
        """Draws a line from p0 to p1 with a certain color and thickness."""
        p0 = self.scaled(p0[0], p0[1])
        p0 = self.surface.get_real_coor(p0[0], p0[1])
        p1 = self.scaled(p1[0], p1[1])
        p1 = self.surface.get_real_coor(p1[0], p1[1])
        if do_snap:
            p0 = (snap(p0[0]), snap(p0[1]))
            p1 = (snap(p1[0]), snap(p1[1]))

        self.surface.ctx.move_to(p0[0], p0[1])
        self.surface.ctx.line_to(p1[0], p1[1])
        self.surface.ctx.set_source_rgb(color[0], color[1], color[2])
        self.surface.ctx.set_line_width(thickness * self.scale)
        self.surface.ctx.stroke()

    def draw_circle(self, x, y, radius, fill_color, border_color,
                     thickness, do_snap=True):
        p = self.surface.get_real_coor(x, y)
        if do_snap:
            p = (snap(p[0]), snap(p[1]))

        self.surface.ctx.save()
        self.surface.ctx.arc(p[0], p[1], radius, 0.0, 2 * math.pi)
        self.surface.ctx.set_source_rgb(border_color[0],
                                        border_color[1],
                                        border_color[2])
        self.surface.ctx.set_line_width(thickness * self.scale)
        self.surface.ctx.stroke()
        self.surface.ctx.arc(p[0], p[1], radius, 0.0, 2 * math.pi)
        self.surface.ctx.set_source_rgb(fill_color[0],
                                        fill_color[1],
                                        fill_color[2])
        self.surface.ctx.fill()
        self.surface.ctx.restore()

    def _polyline_common(self, coor_list, color, thickness, do_snap=True):
        real_coor_list = [self.surface.get_real_coor(coor[0], coor[1]) \
                          for coor in coor_list]

        self.surface.ctx.move_to(real_coor_list[0][0], real_coor_list[0][1])
        if do_snap:
            for i in range(0, len(real_coor_list)):
                real_coor_list[i] = (snap(real_coor_list[i][0]),
                                     snap(real_coor_list[i][1]))

        for coor in real_coor_list[1:]:
            self.surface.ctx.line_to(coor[0], coor[1])

        self.surface.ctx.set_line_width(thickness * self.scale)
        self.surface.ctx.set_source_rgb(color[0], color[1], color[2])

    def draw_polyline(self, coor_list, color, thickness, do_snap=True):
        self._polyline_common(coor_list, color, thickness, do_snap)
        self.surface.ctx.stroke()

    def fill_polyline(self, coor_list, color, thickness, do_snap=True):
        self._polyline_common(coor_list, color, thickness, do_snap)
        self.surface.ctx.fill()

    def _draw_label_common(self, text, x, y, fopts, x_bearing_factor, \
                           f_descent_factor, width_factor, f_height_factor, do_snap=True):
        """Helper function for drawing a label with some alignment. Instead of taking in an alignment,
        it takes in the scale factor for the font extent parameters, which give the raw data of how much to adjust
        the x and y parameters. Only should be used internally."""
        x, y = self.scaled(x, y)
        x, y = self.surface.get_real_coor(x, y)

        self.surface.ctx.set_source_rgb(0.0, 0.0, 0.0)

        self.surface.ctx.select_font_face(fopts.name, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        self.surface.ctx.set_font_size(fopts.size * self.scale)

        fe = self.surface.ctx.font_extents()
        f_ascent, f_descent, f_height = fe[:3]

        te = self.surface.ctx.text_extents(text)
        x_bearing, y_bearing, width, height = te[:4]

        actual_x = x - x_bearing * x_bearing_factor - width * width_factor
        actual_y = y - f_descent * f_descent_factor + f_height * f_height_factor

        self.surface.ctx.set_source_rgb(fopts.color[0], fopts.color[1], fopts.color[2])

        if do_snap:
            self.surface.ctx.move_to(snap(actual_x), snap(actual_y))
        else:
            self.surface.ctx.move_to(actual_x, actual_y)

        self.surface.ctx.show_text(text)

    def draw_label(self, text, x, y, fopts=GraphFormat.DEF_FOPTS_LABEL, halign=AlignMode.LEFT, valign=AlignMode.BOTTOM, do_snap=True):
        """Draws a label with the given parameters, with the given horizontal and vertical justification. One can override
        the color from ``fopts'' by passing something in to ``pattern'', which overrides the color with an arbitrary
        pattern."""
        x_bearing_factor, f_descent_factor, width_factor, f_height_factor = 0.0, 0.0, 0.0, 0.0
        halign_factors = {AlignMode.LEFT : (0.0, 0.0), AlignMode.CENTER : (1.0, 0.5), AlignMode.RIGHT : (1.0, 1.0)}
        if halign not in halign_factors:
            raise ValueError('Invalid alignment value')
        x_bearing_factor, width_factor = halign_factors[halign]

        valign_factors = {AlignMode.BOTTOM : (0.0, 0.0), AlignMode.CENTER : (1.0, 0.5), AlignMode.TOP : (1.0, 1.0)}
        if valign not in valign_factors:
            raise ValueError('Invalid alignment value')
        f_descent_factor, f_height_factor = valign_factors[valign]

        return self._get_label_dim_common(text, x, y, fopts, x_bearing_factor,
                                          f_descent_factor, width_factor, f_height_factor,
                                          do_snap)

    def draw_label(self, text, x, y, fopts=GraphFormat.DEF_FOPTS_LABEL,
                   halign=AlignMode.LEFT, valign=AlignMode.BOTTOM, do_snap=True):
        """Draws a label with the given parameters, with the given horizontal and vertical justification."""

        actual_x, actual_y, width, height, f_height = self.get_label_dim(text, x, y, fopts, halign, valign, do_snap)
        actual_x, actual_y = self.surface.get_real_coor(actual_x, actual_y)

        self.surface.ctx.select_font_face(fopts.name, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        self.surface.ctx.set_font_size(fopts.size * self.scale)
        self.surface.ctx.set_source_rgb(fopts.color[0], fopts.color[1], fopts.color[2])
        self.surface.ctx.move_to(actual_x, actual_y)

        self.surface.ctx.show_text(text)

    def draw_label_with_sscripts(self, text, supscript, subscript, x, y, \
                                 textfopts=GraphFormat.DEF_FOPTS_LABEL, sscriptfopts=GraphFormat.DEF_FOPTS_LABEL_SSCRIPT, \
                                halign=AlignMode.LEFT, valign=AlignMode.BOTTOM, do_snap=True):
        """Draws a label, but also optionally allows a superscript and subscript to be rendered."""
        self.draw_label(text, x, y, textfopts, halign, valign)

        self.surface.ctx.set_source_rgb(0.0, 0.0, 0.0)
        self.surface.ctx.select_font_face(textfopts.name, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        self.surface.ctx.set_font_size(textfopts.size)
        te = self.surface.ctx.text_extents(text)
        fe = self.surface.ctx.font_extents()
        if supscript is not None:
            f_height = fe[2]
            x_advance = te[4]
            xtmp = x + x_advance
            ytmp = y
            ytmp = y - f_height / 4.0
            self.draw_label(supscript, xtmp, ytmp, sscriptfopts, halign, valign, do_snap)
        if subscript is not None:
            f_height = fe[2]
            x_advance = te[4]
            xtmp = x + x_advance
            ytmp = y
            ytmp = y + f_height / 4.0
            self.draw_label(subscript, xtmp, ytmp, sscriptfopts, halign, valign, do_snap)

# represents a selectable region of the graph
class SelectableRegion(object):
    def __init__(self, x, y, width, height, event):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.event = event
        self.scale = 1.0

    def get_dimensions(self):
        return (self.x, self.y, self.width, self.height)

    def get_event(self):
        return self.event

    def set_scale(self, scale):
        self.scale = scale

    def intersects(self, x, y, width, height):
        return x <= (self.x + self.width) * self.scale \
           and x + width >= self.x * self.scale \
           and y <= (self.y + self.height) * self.scale \
           and y + height >= self.y * self.scale

