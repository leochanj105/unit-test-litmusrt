#!/usr/bin/python

"""GUI stuff."""

from schedule import *
from renderer import *
from windows import *

import pygtk
import gtk
import gobject
import copy

class GraphContextMenu(gtk.Menu):
    MAX_STR_LEN = 80

    def __init__(self, selected, info_win):
        super(GraphContextMenu, self).__init__()

        self.info_win = info_win

        if not selected:
            item = gtk.MenuItem("(No events selected)")
            item.set_sensitive(False)
            self.append(item)
            item.show()
        else:
            for layer in selected:
                for event in selected[layer]:
                    string = str(event)
                    if len(string) > GraphContextMenu.MAX_STR_LEN - 3:
                        string = string[:GraphContextMenu.MAX_STR_LEN - 3] + '...'
                    item = gtk.MenuItem(string)
                    item.connect('activate', self.update_info_window, event)
                    self.append(item)
                    item.show()

    def update_info_window(self, widget, data):
        self.info_win.set_event(data)
        self.info_win.present()

class GraphArea(gtk.DrawingArea):
    HORIZ_PAGE_SCROLL_FACTOR = 10.8
    HORIZ_STEP_SCROLL_FACTOR = 0.8
    VERT_PAGE_SCROLL_FACTOR = 3.0
    VERT_STEP_SCROLL_FACTOR = 0.5

    REFRESH_INFLATION_FACTOR = 4.0

    MIN_ZOOM_OUT = 0.25
    MAX_ZOOM_IN = 4.0
    ZOOM_INCR = 0.25

    def __init__(self, renderer):
        super(GraphArea, self).__init__()

        self.renderer = renderer

        self.cur_x = 0
        self.cur_y = 0
        self.width = 0
        self.height = 0
        self.scale = 1.0

        self.set_set_scroll_adjustments_signal('set-scroll-adjustments')

        self.add_events(gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.POINTER_MOTION_MASK | gtk.gdk.POINTER_MOTION_HINT_MASK |
                        gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.EXPOSURE_MASK)

        self.band_rect = None
        self.ctrl_clicked = False
        self.last_selected = {}
        self.dirtied_regions = []

        self.connect('expose-event', self.expose)
        self.connect('size-allocate', self.size_allocate)
        self.connect('set-scroll-adjustments', self.set_scroll_adjustments)
        self.connect('button-press-event', self.button_press)
        self.connect('button-release-event', self.button_release)
        self.connect('motion-notify-event', self.motion_notify)

    def expose(self, widget, expose_event, data=None):
        ctx = widget.window.cairo_create()
        graph = self.renderer.get_graph()
        graph.update_view(self.cur_x, self.cur_y, self.width, self.height, self.scale, ctx)

        # If X caused the expose event, we need to update the entire area, not just the
        # changes we might have made. An expose event caused by X needs to take priority
        # over any expose events caused by updates to the state of the graph because
        # the areas we marked as dirty only include the state changes, which is completely
        # unrelated to the area that X indicates must be updated.
        if expose_event.type == gtk.gdk.EXPOSE:
            self.dirtied_regions = [(expose_event.area.x, expose_event.area.y,
                                     expose_event.area.width, expose_event.area.height)]

        graph.render_surface(self.renderer.get_schedule(), self.dirtied_regions)

        # render dragging band rectangle, if there is one
        if self.band_rect is not None:
            x, y, width, height = self.band_rect
            thickness = GraphFormat.BAND_THICKNESS
            color = GraphFormat.BAND_COLOR

            ctx.rectangle(x, y, width, height)
            ctx.set_line_width(thickness)
            ctx.set_source_rgb(color[0], color[1], color[2])
            ctx.stroke()

        self.dirtied_regions = []

    def get_renderer(self):
        return self.renderer

    def get_graph(self):
        return self.renderer.get_graph()

    def get_schedule(self):
        return self.renderer.get_schedule()

    def zoom_in(self):
        scale = self.scale + GraphArea.ZOOM_INCR
        if scale > GraphArea.MAX_ZOOM_IN:
            scale = GraphArea.MAX_ZOOM_IN
        self.set_scale(scale)
        self.config_scrollbars(self.cur_x, self.cur_y, self.scale)

    def zoom_out(self):
        scale = self.scale - GraphArea.ZOOM_INCR
        if scale < GraphArea.MIN_ZOOM_OUT:
            scale = GraphArea.MIN_ZOOM_OUT
        self.set_scale(scale)
        self.config_scrollbars(self.cur_x, self.cur_y, self.scale)

    def set_scale(self, scale):
        if scale == self.scale:
            return

        self.scale = scale
        self._dirty(0, 0, self.width, self.height)

    def set_hvalue(self, value):
        if self.horizontal is None:
            return

        value = max(value, self.horizontal.get_lower())
        value = min(value, self.horizontal.get_upper() - self.horizontal.get_page_size())
        self.horizontal.set_value(value)

    def set_vvalue(self, value):
        if self.vertical is None:
            return

        value = max(value, self.vertical.get_lower())
        value = min(value, self.vertical.get_upper() - self.vertical.get_page_size())
        self.vertical.set_value(value)

    def set_scroll_adjustments(self, widget, horizontal, vertical, data=None):
        graph = self.renderer.get_graph()
        width = graph.get_width()
        height = graph.get_height()

        self.horizontal = horizontal
        self.vertical = vertical
        self.config_scrollbars(self.cur_x, self.cur_y, self.scale)

        if self.horizontal is not None:
            self.horizontal.connect('value-changed', self.horizontal_value_changed)
        if self.vertical is not None:
            self.vertical.connect('value-changed', self.vertical_value_changed)

    def horizontal_value_changed(self, adjustment):
        self.cur_x = min(adjustment.value, self.renderer.get_graph().get_width())
        self.cur_x = max(adjustment.value, 0.0)

        self.renderer.get_graph().render_surface(self.renderer.get_schedule(), [(0, 0, self.width, self.height)], True)
        self._dirty(0, 0, self.width, self.height)

    def vertical_value_changed(self, adjustment):
        self.cur_y = min(adjustment.value, self.renderer.get_graph().get_height())
        self.cur_y = max(adjustment.value, 0.0)

        self.renderer.get_graph().render_surface(self.renderer.get_schedule(), [(0, 0, self.width, self.height)], True)
        self._dirty(0, 0, self.width, self.height)

    def size_allocate(self, widget, allocation):
        self.width = allocation.width
        self.height = allocation.height
        self.config_scrollbars(self.cur_x, self.cur_y, self.scale)

    def config_scrollbars(self, hvalue, vvalue, scale):
        graph = self.renderer.get_graph()
        width = graph.get_width()
        height = graph.get_height()

        if self.horizontal is not None:
            self.horizontal.set_all(0.0, 0.0, width,
                                graph.get_attrs().maj_sep * GraphArea.HORIZ_STEP_SCROLL_FACTOR / scale,
                                graph.get_attrs().maj_sep * GraphArea.HORIZ_PAGE_SCROLL_FACTOR / scale,
                                self.width / scale)
            self.set_hvalue(hvalue)
        if self.vertical is not None:
            self.vertical.set_all(0.0, 0.0, height,
                                graph.get_attrs().y_item_size * GraphArea.VERT_STEP_SCROLL_FACTOR / scale,
                                graph.get_attrs().y_item_size * GraphArea.VERT_PAGE_SCROLL_FACTOR / scale,
                                self.height / scale)
            self.set_vvalue(vvalue)

    def refresh_events(self, sender, new, old, replace):
        """Even if the selected areas change on one graph, they change
        everywhere, and different events might be in different regions on
        different graphs. So when an event is selected on one graph its
        region on a completely different graph needs to be updated. This
        is why this method is here: given the graph that requested the
        change, the old set of events selected, and the new set of events
        selected, it updates the selected regions of this graph, and
        refreshes the drawing of the graph that requested the change."""
        if self is not sender:
            self.renderer.get_graph().render_events(new, True)

        self._tag_events(new)

        if self is sender:
            self._copy_tags(old)
            self._dirty_events(new)
            self._dirty_events(old)
            if replace:
                self.renderer.get_schedule().set_selected(new)
            else:
                self.renderer.get_schedule().remove_selected(old)
                self.renderer.get_schedule().add_selected(new)

    def _find_max_layer(self, regions):
        max_layer = Canvas.BOTTOM_LAYER
        for event in regions:
            if event.get_layer() > max_layer:
                max_layer = event.get_layer()
        return max_layer

    def _dirty_events(self, events):
        # if an event changed selected status, update the bounding area
        for layer in events:
            for event in events[layer]:
                x, y, width, height = events[layer][event][self].get_dimensions()
                self._dirty_inflate((x - self.cur_x) * self.scale,
                                (y - self.cur_y) * self.scale,
                                width * self.scale,
                                height * self.scale,
                                GraphFormat.BORDER_THICKNESS * self.scale)

    def _tag_events(self, selected):
        """Some of the events in the collection of selected events might be new.
        In this case, these events are not yet associated with the region on
        the graph that they belong to. This method fixes this.
        """
        graph = self.renderer.get_graph()
        for layer in selected:
            for event in selected[layer]:
                # note that each graph has its own region associated
                # with the event
                selected[layer][event][self] = graph.get_sel_region(event)

    def _copy_tags(self, selected):
        """When we want to specify a collection of selected events to perform
        an operation on, we usually do not know ahead of time what regions (in
        which graphs) the events are associated with. But we have this information
        stored in the collection of all selected events. This method just copies
        this information over to the selected variable."""
        cur_selected = self.renderer.get_schedule().get_selected()
        for layer in selected:
            for event in selected[layer]:
                selected[layer][event] = cur_selected[layer][event]

    def _select_event(self, coll, event):
        if event.get_layer() not in coll:
            coll[event.get_layer()] = {}
        if event not in coll[event.get_layer()]:
            coll[event.get_layer()][event] = {}

    def motion_notify(self, widget, motion_event, data=None):
        msg = None

        graph = self.renderer.get_graph()

        graph.render_surface(self.renderer.get_schedule(), [(motion_event.x, motion_event.y,
                             0, 0)], True)

        just_selected = graph.get_selected_regions(motion_event.x, motion_event.y, 0, 0)
        was_selected = self.renderer.get_schedule().get_selected()
        if not just_selected:
            msg = ''
            the_event = None
        else:
            max_layer = self._find_max_layer(just_selected)

            for event in just_selected:
                if event.get_layer() == max_layer:
                    the_event = event
                    break

            msg = str(the_event)

        self.emit('update-event-description', the_event, msg)

        if self.band_rect is not None:
            remove_selected = {}
            add_selected = {}

            # dragging a rectangle
            x = self.band_rect[0]
            y = self.band_rect[1]
            width = motion_event.x - self.band_rect[0]
            height = motion_event.y - self.band_rect[1]
            old_x, old_y, old_width, old_height = self.band_rect

            x_p, y_p, width_p, height_p = self._positivify(x, y, width, height)
            old_x_p, old_y_p, old_width_p, old_height_p = self._positivify(old_x, old_y, old_width, old_height)
            x_p, y_p, width_p, height_p = int(x_p), int(y_p), int(width_p), int(height_p)
            old_x_p, old_y_p, old_width_p, old_height_p = int(old_x_p), int(old_y_p), int(old_width_p), int(old_height_p)

            new_reg = gtk.gdk.region_rectangle(gtk.gdk.Rectangle(x_p, y_p, width_p, height_p))
            old_reg = gtk.gdk.region_rectangle(gtk.gdk.Rectangle(old_x_p, old_y_p, old_width_p, old_height_p))

            # To find the events that should be deselected and the new events that should be selected, compute
            # the set differences between the old and new selection rectangles

            remove_reg = gtk.gdk.region_rectangle(gtk.gdk.Rectangle(old_x_p, old_y_p, old_width_p, old_height_p))
            remove_reg.subtract(new_reg)
            dirty_list = []
            for rect in remove_reg.get_rectangles():
                dirty_list.append((rect.x, rect.y, rect.width, rect.height))
            graph.render_surface(self.renderer.get_schedule(), dirty_list, True)
            for rect in dirty_list:
                rx, ry, rwidth, rheight = rect
                for event in graph.get_selected_regions(rx, ry, rwidth, rheight):
                    if event.get_layer() in was_selected and event in was_selected[event.get_layer()]:
                        self._select_event(remove_selected, event)

            add_reg = gtk.gdk.region_rectangle(gtk.gdk.Rectangle(x_p, y_p, width_p, height_p))
            add_reg.subtract(old_reg)
            dirty_list = [(x_p, y_p, width_p, 0), (x_p, y_p, 0, height_p),
                          (x_p, y_p + height_p, width_p, 0), (x_p + width_p, y_p, 0, height_p)]
            for rect in add_reg.get_rectangles():
                dirty_list.append((rect.x, rect.y, rect.width, rect.height))
            graph.render_surface(self.renderer.get_schedule(), dirty_list, True)
            for rect in dirty_list:
                rx, ry, rwidth, rheight = rect
                for event in graph.get_selected_regions(rx, ry, rwidth, rheight):
                    self._select_event(add_selected, event)

            self.band_rect = x, y, width, height
            self.emit('request-refresh-events', self, add_selected, remove_selected, False)

            self._dirty_rect_border(old_x, old_y, old_width, old_height, GraphFormat.BAND_THICKNESS)
            self._dirty_rect_border(x, y, width, height, GraphFormat.BAND_THICKNESS)

    def button_press(self, widget, button_event, data=None):
        graph = self.renderer.get_graph()

        self.ctrl_clicked = button_event.state & gtk.gdk.CONTROL_MASK

        if button_event.button == 1:
            self.left_button_start_coor = (button_event.x, button_event.y)
            graph.render_surface(self.renderer.get_schedule(), \
                                 [(button_event.x, button_event.y, 0, 0)], True)

            just_selected = graph.get_selected_regions(button_event.x, button_event.y, 0, 0)

            max_layer = self._find_max_layer(just_selected)

            was_selected = self.renderer.get_schedule().get_selected()
            if not self.ctrl_clicked:
                new_now_selected = {}

                more_than_one = 0
                for layer in was_selected:
                    for event in was_selected[layer]:
                        more_than_one += 1
                        if more_than_one > 1:
                            break

                # only select those events which were in the top layer (it's
                # not intuitive to click something and then have something
                # below it get selected). Also, clicking something that
                # is selected deselects it, if it's the only thing selected
                for event in just_selected:
                    if event.get_layer() == max_layer:
                        if not (more_than_one == 1 and event in was_selected):
                            self._select_event(new_now_selected, event)
                        break # only pick one event when just clicking

                self.emit('request-refresh-events', self, new_now_selected, was_selected, True)
            else:
                remove_selected = {}
                add_selected = {}

                for event in just_selected:
                    layer = event.get_layer()
                    if layer == max_layer:
                        if layer in was_selected and event in was_selected[layer]:
                            self._select_event(remove_selected, event)
                        else:
                            self._select_event(add_selected, event)
                        break # again, only pick one event because we are just clicking

                self.emit('request-refresh-events', self, add_selected, remove_selected, False)

            if self.band_rect is None:
                self.band_rect = (button_event.x, button_event.y, 0, 0)

        elif button_event.button == 3:
            self._release_band()
            self.emit('request-context-menu', button_event, self.renderer.get_schedule().get_selected())

    def button_release(self, widget, button_event, data=None):
        self.ctrl_clicked = False

        if button_event.button == 1:
            self._release_band()

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def _release_band(self):
        if self.band_rect is not None:
            x, y, width, height = self.band_rect
            self._dirty_rect_border(x, y, width, height, GraphFormat.BAND_THICKNESS)
            self.band_rect = None

    def _dirty(self, x, y, width, height):
        x = max(int(math.floor(x)), 0)
        y = max(int(math.floor(y)), 0)
        width = min(int(math.ceil(width)), self.width)
        height = min(int(math.ceil(height)), self.height)

        self.dirtied_regions.append((x, y, width, height))

        rect = gtk.gdk.Rectangle(x, y, width, height)
        self.window.invalidate_rect(rect, True)

    def _dirty_inflate(self, x, y, width, height, thickness):
        t = thickness * GraphArea.REFRESH_INFLATION_FACTOR
        x -= t / 2.0
        y -= t / 2.0
        width += t
        height += t
        self._dirty(x, y, width, height)

    def _dirty_rect_border(self, x, y, width, height, thickness):
        # support rectangles with negative width and height (i.e. -width = width, but going leftwards
        # instead of rightwards)
        x, y, width, height = self._positivify(x, y, width, height)

        self._dirty_inflate(x, y, width, 0, thickness)
        self._dirty_inflate(x, y, 0, height, thickness)
        self._dirty_inflate(x, y + height, width, 0, thickness)
        self._dirty_inflate(x + width, y, 0, height, thickness)

    def _positivify(self, x, y, width, height):
        if width < 0:
            x += width
            width = -width
        if height < 0:
            y += height
            height = -height

        return x, y, width, height

class GraphWindow(gtk.ScrolledWindow):
    def __init__(self, renderer):
        super(GraphWindow, self).__init__(None, None)

        self.add_events(gtk.gdk.KEY_PRESS_MASK | gtk.gdk.SCROLL_MASK)

        self.ctr = 0
        self.connect('key-press-event', self.key_press)
        self.connect('scroll-event', self.scroll)

        self.garea = GraphArea(renderer)
        self.add(self.garea)
        self.garea.show()

    def key_press(self, widget, key_event):
        hadj = self.get_hadjustment()
        vadj = self.get_vadjustment()
        if hadj is None or vadj is None:
            return

        ctrl_clicked = key_event.state & gtk.gdk.CONTROL_MASK

        keystr = None
        keymap = {gtk.keysyms.Up : 'up', gtk.keysyms.Down : 'down',
                  gtk.keysyms.Left : 'left', gtk.keysyms.Right : 'right'}
        if key_event.keyval in keymap:
            keystr = keymap[key_event.keyval]
        else:
            return True

        if ctrl_clicked:
            keystr = 'ctrl-' + keystr

        if keystr is not None:
            self._scroll_direction(keystr)

        return True

    def set_hvalue(self, value):
        self.get_graph_area().set_hvalue(value)

    def set_vvalue(self, value):
        self.get_graph_area().set_vvalue(value)

    def _scroll_direction(self, keystr):
        hadj = self.get_hadjustment()
        vadj = self.get_vadjustment()
        if hadj is None or vadj is None:
            return

        hupper = hadj.get_upper()
        hlower = hadj.get_lower()
        hpincr = hadj.get_page_increment()
        hsincr = hadj.get_step_increment()
        hpsize = hadj.get_page_size()
        hval = hadj.get_value()
        vupper = vadj.get_upper()
        vlower = vadj.get_lower()
        vval = vadj.get_value()
        vpincr = vadj.get_page_increment()
        vsincr = vadj.get_step_increment()
        vpsize = vadj.get_page_size()

        adj_tuple = {'up' :     (vadj, -vsincr, 0, vval, max),
                     'ctrl-up' :    (vadj, -vpincr, 0, vval, max),
                     'down' :   (vadj, vsincr, vupper - vpsize, vval, min),
                     'ctrl-down' :  (vadj, vpincr, vupper - vpsize, vval, min),
                     'left' :   (hadj, -hsincr, 0, hval, max),
                     'ctrl-left' :  (hadj, -hpincr, 0, hval, max),
                     'right' :  (hadj, hsincr, hupper - hpsize, hval, min),
                     'ctrl-right' : (hadj, hpincr, hupper - hpsize, hval, min)}

        adj, inc, lim, val, extr = adj_tuple[keystr]
        adj.set_value(extr(val + inc, lim))

    def scroll(self, widget, scroll_event):
        if scroll_event.state & gtk.gdk.CONTROL_MASK:
            if scroll_event.direction == gtk.gdk.SCROLL_UP:
                self.emit('request-zoom-in')
            elif scroll_event.direction == gtk.gdk.SCROLL_DOWN:
                self.emit('request-zoom-out')
        else:
            if scroll_event.direction == gtk.gdk.SCROLL_UP:
                self._scroll_direction('up')
            elif scroll_event.direction == gtk.gdk.SCROLL_DOWN:
                self._scroll_direction('down')

        return True

    def get_graph_area(self):
        return self.garea

class MainWindow(gtk.Window):
    WINDOW_WIDTH_REQ = 500
    WINDOW_HEIGHT_REQ = 300

    def __init__(self):
        super(MainWindow, self).__init__(gtk.WINDOW_TOPLEVEL)

        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)

        self.connect('delete_event', self.delete_event)
        self.connect('destroy', self.die)

        file_menu = gtk.Menu()
        view_menu = gtk.Menu()

        agr = gtk.AccelGroup()
        self.add_accel_group(agr)

        quit_item = gtk.ImageMenuItem(gtk.STOCK_QUIT, agr)
        key, mod = gtk.accelerator_parse('Q')
        quit_item.add_accelerator('activate', agr, key, mod,
            gtk.ACCEL_VISIBLE)
        quit_item.connect('activate', self.quit_item_activate)
        quit_item.show()

        file_menu.append(quit_item)

        file_item = gtk.MenuItem('_File', True)
        file_item.set_submenu(file_menu)
        file_item.show()

        self.move_item = gtk.ImageMenuItem('_Move to Time')
        key, mod = gtk.accelerator_parse('<Ctrl>M')
        self.move_item.add_accelerator('activate', agr, key, mod,
            gtk.ACCEL_VISIBLE)
        self.move_item.set_sensitive(False)

        self.move_item.connect('activate', self.move_to_time_activate)
        self.move_item.show()

        zoom_in_item = gtk.ImageMenuItem(gtk.STOCK_ZOOM_IN, agr)
        key, mod = gtk.accelerator_parse('<Ctrl>plus')
        zoom_in_item.add_accelerator('activate', agr, key, mod,
            gtk.ACCEL_VISIBLE)
        key, mod = gtk.accelerator_parse('<Ctrl>equal')
        zoom_in_item.add_accelerator('activate', agr, key, mod, 0)

        zoom_in_item.connect('activate', self.zoom_in_item_activate)
        zoom_in_item.show()

        zoom_out_item = gtk.ImageMenuItem(gtk.STOCK_ZOOM_OUT, agr)
        key, mod = gtk.accelerator_parse('<Ctrl>minus')
        zoom_out_item.add_accelerator('activate', agr, key, mod,
            gtk.ACCEL_VISIBLE)
        key, mod = gtk.accelerator_parse('<Ctrl>underscore')
        zoom_out_item.add_accelerator('activate', agr, key, mod, 0)

        zoom_out_item.connect('activate', self.zoom_out_item_activate)
        zoom_out_item.show()

        view_menu.append(self.move_item)
        view_menu.append(zoom_in_item)
        view_menu.append(zoom_out_item)

        view_item = gtk.MenuItem('_View', True)
        view_item.set_submenu(view_menu)
        view_item.show()

        menu_bar = gtk.MenuBar()
        menu_bar.append(file_item)
        menu_bar.append(view_item)

        menu_bar.show()
        self.vbox = gtk.VBox(False, 0)

        self.notebook = gtk.Notebook()

        self.notebook.last_page = -1
        self.notebook.connect('switch-page', self.switch_page)

        self.notebook.show()

        self.desc_label = gtk.Label('')
        self.desc_label.set_alignment(0.0, 0.0)
        self.desc_label.show()

        self.vbox.pack_start(menu_bar, False, False, 0)
        self.vbox.pack_start(self.notebook, True, True, 0)
        self.vbox.pack_start(self.desc_label, False, False, 0)
        self.vbox.show()

        self.add(self.vbox)

        self.info_win = InfoWindow()

        self.set_size_request(MainWindow.WINDOW_WIDTH_REQ, MainWindow.WINDOW_HEIGHT_REQ)

        self.set_title('Unit-Trace Visualizer')
        self.show()

    def connect_widgets(self, gwindow):
        gwindow.get_graph_area().connect('update-event-description', self.update_event_description)
        gwindow.get_graph_area().connect('request-context-menu', self.request_context_menu)
        gwindow.get_graph_area().connect('request-refresh-events', self.request_refresh_events)
        gwindow.connect('request-zoom-in', self.zoom_in_item_activate)
        gwindow.connect('request-zoom-out', self.zoom_out_item_activate)

    def set_renderers(self, renderers):
        for i in range(0, self.notebook.get_n_pages()):
            self.notebook.remove_page(0)
        for title in renderers:
            gwindow = GraphWindow(renderers[title])
            self.connect_widgets(gwindow)
            gwindow.show()
            self.notebook.append_page(gwindow, gtk.Label(title))
        if self.notebook.get_n_pages() > 0:
            self.notebook.get_nth_page(0).grab_focus()

        if self.notebook.get_n_pages() > 0:
            self.move_item.set_sensitive(True)
        else:
            self.move_item.set_sensitive(False)


    def switch_page(self, widget, page, page_num):
        if self.notebook.get_nth_page(self.notebook.last_page) is not None:
            old_value = self.notebook.get_nth_page(self.notebook.last_page).get_hadjustment().get_value()
            old_ofs = self.notebook.get_nth_page(self.notebook.last_page).get_graph_area().get_graph().get_origin()[0]
            new_ofs = self.notebook.get_nth_page(page_num).get_graph_area().get_graph().get_origin()[0]
            new_value = old_value - old_ofs + new_ofs
            self.notebook.get_nth_page(page_num).get_hadjustment().set_value(new_value)

        self.notebook.last_page = page_num

    def update_event_description(self, widget, event, msg):
        self.desc_label.set_text(msg)

    def request_context_menu(self, widget, gdk_event, selected):
        button = 0
        if hasattr(gdk_event, 'button'):
           button = gdk_event.button
        time = gdk_event.time

        menu = GraphContextMenu(selected, self.info_win)
        menu.popup(None, None, None, button, time)

    def request_refresh_events(self, widget, sender, old, new, replace):
        for i in range(0, self.notebook.get_n_pages()):
            if self.notebook.get_nth_page(i).get_graph_area() is not sender:
                self.notebook.get_nth_page(i).get_graph_area().refresh_events(sender, old, new, replace)
                break
        for i in range(0, self.notebook.get_n_pages()):
            if self.notebook.get_nth_page(i).get_graph_area() is sender:
                self.notebook.get_nth_page(i).get_graph_area().refresh_events(sender, old, new, replace)

    def move_to_time_activate(self, widget):
        dialog = TextInputDialog('Move to Time', 'What time to move to?', self)

        err = True
        while err:
            ret = dialog.run()

            if ret == gtk.RESPONSE_ACCEPT:
                err, time = None, None
                try:
                    time = float(dialog.get_input())
                    start, end = self.notebook.get_nth_page(0).get_graph_area().get_schedule().get_time_bounds()
                    if time < start or time > end:
                        err = 'Time out of range!'
                except ValueError:
                    err = 'Must input a number!'

                if not err:
                    for i in xrange(0, self.notebook.get_n_pages()):
                        garea = self.notebook.get_nth_page(i).get_graph_area()
                        # Center as much as possible
                        pos = garea.get_graph().get_time_xpos(time) - garea.get_width() / 2.0
                        self.notebook.get_nth_page(i).set_hvalue(pos)
                else:
                    err_dialog = gtk.MessageDialog(self, gtk.DIALOG_DESTROY_WITH_PARENT,
                                                         gtk.MESSAGE_ERROR,
                                                         gtk.BUTTONS_CLOSE,
                                                         err)
                    err_dialog.set_title('Input Error')
                    err_dialog.run()
                    err_dialog.destroy()

            else:
                break

        dialog.destroy()

    def zoom_in_item_activate(self, widget):
        for i in range(0, self.notebook.get_n_pages()):
            self.notebook.get_nth_page(i).get_graph_area().zoom_in()

    def zoom_out_item_activate(self, widget):
        for i in range(0, self.notebook.get_n_pages()):
            self.notebook.get_nth_page(i).get_graph_area().zoom_out()

    def quit_item_activate(self, widget):
        self.destroy()

    def delete_event(self, widget, event, data=None):
        return False

    def die(self, widget, data=None):
        gtk.main_quit()

