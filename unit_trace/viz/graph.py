import util
import schedule
from format import *
from canvas import *

"""The higher-level components of the rendering engine. The graph classes deal with more abstract dimensions
than the canvas classes (time and task/cpu number rather than plain coordinates). Also, graphs know how to
update themselves, unlike the Canvas which can only overwrite itself."""

class Graph(object):
    DEF_BAR_PLIST = [Pattern([(0.0, 0.9, 0.9)]), Pattern([(0.9, 0.3, 0.0)]),
                     Pattern([(0.9, 0.7, 0.0)]), Pattern([(0.0, 0.0, 0.8)]),
                     Pattern([(0.0, 0.2, 0.9)]), Pattern([(0.0, 0.6, 0.6)]),
                     Pattern([(0.75, 0.75, 0.75)])]
    DEF_ITEM_CLIST = [(0.3, 0.0, 0.0), (0.0, 0.3, 0.0), (0.0, 0.0, 0.3),
                      (0.3, 0.3, 0.0), (0.0, 0.3, 0.3), (0.3, 0.0, 0.3)]

    def __init__(self, CanvasType, surface, start_time, end_time, y_item_list, attrs=GraphFormat(),
                 item_clist=DEF_ITEM_CLIST, bar_plist=DEF_BAR_PLIST):
        # deal with possibly blank schedules
        if start_time is None:
            start_time = 0
        if end_time is None:
            end_time = 0

        if start_time > end_time:
            raise ValueError("Litmus is not a time machine")

        self.attrs = attrs
        self.start_time = start_time
        self.end_time = end_time
        self.y_item_list = y_item_list
        self.num_maj = int(math.ceil((self.end_time - self.start_time) * 1.0 / self.attrs.time_per_maj)) + 1

        width = self.num_maj * self.attrs.maj_sep + GraphFormat.X_AXIS_MEASURE_OFS + GraphFormat.WIDTH_PAD
        height = (len(self.y_item_list) + 1) * self.attrs.y_item_size + GraphFormat.HEIGHT_PAD

        # We need to stretch the width in order to fit the y-axis labels. To do this we need
        # the extents information, but we haven't set up a surface yet, so we just use a
        # temporary one.
        extra_width = 0.0
        dummy_surface = surface.__class__()
        dummy_surface.renew(10, 10)

        dummy_surface.ctx.select_font_face(self.attrs.item_fopts.name, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        dummy_surface.ctx.set_font_size(self.attrs.item_fopts.size)
        for item in self.y_item_list:
            dummy_surface.ctx.set_source_rgb(0.0, 0.0, 0.0)
            te = dummy_surface.ctx.text_extents(item)
            cur_width = te[2]
            if cur_width > extra_width:
                extra_width = cur_width

        width += extra_width

        self.origin = (extra_width + GraphFormat.WIDTH_PAD / 2.0, height - GraphFormat.HEIGHT_PAD / 2.0)

        self.width = width
        self.height = height

        #if surface.ctx is None:
        #    surface.renew(width, height)

        self.canvas = CanvasType(width, height, item_clist, bar_plist, surface)

    def get_selected_regions(self, real_x, real_y, width, height):
        return self.canvas.get_selected_regions(real_x, real_y, width, height)

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def get_origin(self):
        return self.origin

    def get_attrs(self):
        return self.attrs

    def add_sel_region(self, region):
        self.canvas.add_sel_region(region)

    def get_sel_region(self, event):
        return self.canvas.get_sel_region(event)

    def has_sel_region(self, event):
        return self.canvas.has_sel_region(event)

    def update_view(self, x, y, width, height, scale, ctx):
        """Proxy into the surface's pan."""
        self.canvas.surface.pan(x, y, width, height)
        self.canvas.set_scale(scale)
        self.canvas.surface.change_ctx(ctx)

    def _recomp_min_max(self, start_time, end_time, start_item, end_item):
        if self.min_time is None or start_time < self.min_time:
            self.min_time = start_time
        if self.max_time is None or end_time > self.max_time:
            self.max_time = end_time
        if self.min_item is None or start_item < self.min_item:
            self.min_item = start_item
        if self.max_item is None or end_item > self.max_item:
            self.max_item = end_item

    def get_time_xpos(self, time):
        """get x so that x is at instant ``time'' on the graph"""
        return self.origin[0] + GraphFormat.X_AXIS_MEASURE_OFS + 1.0 * (time - self.start_time) / self.attrs.time_per_maj * self.attrs.maj_sep

    def get_item_yorigin(self, item_no):
        return self.origin[1] - self._get_y_axis_height() + self.attrs.y_item_size * item_no;

    def get_item_ypos(self, item_no):
        """get y so that y is where the top of a bar would be in item #n's area"""
        return self.get_item_yorigin(item_no) + self.attrs.y_item_size * (0.5 - GraphFormat.BAR_SIZE_FACTOR / 2.0)

    def _get_bar_width(self, start_time, end_time):
        return 1.0 * (end_time - start_time) / self.attrs.time_per_maj * self.attrs.maj_sep

    def _get_bar_height(self):
        return self.attrs.y_item_size * GraphFormat.BAR_SIZE_FACTOR

    def _get_mini_bar_height(self):
        return self.attrs.y_item_size * GraphFormat.MINI_BAR_SIZE_FACTOR

    def _get_mini_bar_ofs(self):
        return self.attrs.y_item_size * (GraphFormat.MINI_BAR_SIZE_FACTOR + GraphFormat.BAR_MINI_BAR_GAP_FACTOR)

    def _get_y_axis_height(self):
        return (len(self.y_item_list) + 1) * self.attrs.y_item_size

    def _get_bottom_tick(self, time):
        return int(math.floor((time - self.start_time) / self.attrs.time_per_maj))

    def _get_top_tick(self, time):
        return int(math.ceil((time - self.start_time) / self.attrs.time_per_maj))

    def get_surface(self):
        """Gets the underlying surface."""
        return self.canvas.get_surface()

    def xcoor_to_time(self, x):
        #x = self.origin[0] + GraphFormat.X_AXIS_MEASURE_OFS + (time - self.start) / self.attrs.time_per_maj * self.attrs.maj_sep
        return (x - self.origin[0] - GraphFormat.X_AXIS_MEASURE_OFS) / self.attrs.maj_sep \
                * self.attrs.time_per_maj + self.start_time

    def ycoor_to_item_no(self, y):
        return int((y - self.origin[1] + self._get_y_axis_height()) // self.attrs.y_item_size)

    def get_offset_params(self, real_x, real_y, width, height):
        x_start, y_start = self.canvas.surface.get_virt_coor_unscaled(real_x, real_y)
        x_end, y_end = self.canvas.surface.get_virt_coor_unscaled(real_x + width, real_y + height)

        start_time = self.xcoor_to_time(x_start)
        end_time = self.xcoor_to_time(x_end)

        start_item = self.ycoor_to_item_no(y_start)
        end_item = 1 + self.ycoor_to_item_no(y_end)

        return (start_time, end_time, start_item, end_item)

    def draw_skeleton(self, start_time, end_time, start_item, end_item):
        self.draw_grid_at_time(start_time, end_time, start_item, end_item)
        self.draw_x_axis_with_labels_at_time(start_time, end_time)
        self.draw_y_axis_with_labels()

    def render_surface(self, sched, regions, selectable=False):
        raise NotImplementedError

    def render_all(self, schedule):
        raise NotImplementedError

    def get_events_to_render(self, sched, regions, selectable=False):
        slots = {}

        self.min_time, self.max_time, self.min_item, self.max_item = None, None, None, None
        for region in regions:
            x, y, width, height = region
            start_time, end_time, start_item, end_item = self.get_offset_params(x, y, width, height)
            self._recomp_min_max(start_time, end_time, start_item, end_item)

            sched.get_time_slot_array().get_slots(slots,
                        start_time, end_time, start_item, end_item,
                        self.list_type)

        events_to_render = {}
        for layer in Canvas.LAYERS:
            events_to_render[layer] = {}

        for event in sched.get_time_slot_array().get_events(slots,
                self.list_type, schedule.EVENT_LIST):
            events_to_render[event.get_layer()][event] = None
        for event in sched.get_jobless():
            events_to_render[event.get_layer()][event] = None

        return events_to_render

    def render_surface(self, sched, regions, selectable=False):
        if not selectable:
            self.canvas.whiteout()
        else:
            self.canvas.clear_selectable_regions()
        self.render_events(self.get_events_to_render(sched, regions, selectable), selectable)

    def render_events(self, events, selectable=False):
        for layer in Canvas.LAYERS:
            prev_events = {}
            if layer in events:
                for event in events[layer]:
                    event.render(self, layer, prev_events, selectable)

    def draw_axes(self, x_axis_label, y_axis_label):
        """Draws and labels the axes according to the parameters that we were initialized
        with."""
        self.draw_grid_at_time(self.start_time, self.end_time, 0, len(self.attrs.y_item_list) - 1)

        self.canvas.draw_x_axis(self.origin[0], self.origin[1], self.num_maj, self.attrs.maj_sep, self.attrs.min_per_maj)
        self.canvas.draw_y_axis(self.origin[0], self.origin[1], self._get_y_axis_height())
        self.canvas.draw_x_axis_labels(self.origin[0], self.origin[1], 0, self.num_maj - 1,\
                                self.attrs.maj_sep, self.attrs.min_per_maj, self.start_time, \
                                self.attrs.time_per_maj, self.attrs.show_min, self.attrs.majfopts, self.attrs.minfopts)
        self.canvas.draw_y_axis_labels(self.origin[0], self.origin[1], self._get_y_axis_height(), self.y_item_list, \
                                       self.attrs.y_item_size, self.attrs.item_fopts)

    def draw_grid_at_time(self, start_time, end_time, start_item, end_item):
        """Draws the grid, but only in a certain time and item range."""
        start_tick = max(0, self._get_bottom_tick(start_time))
        end_tick = min(self.num_maj - 1, self._get_top_tick(end_time))

        start_item = max(0, start_item)
        end_item = min(len(self.y_item_list), end_item)

        self.canvas.draw_grid(self.origin[0], self.origin[1], self._get_y_axis_height(),
                              start_tick, end_tick, start_item, end_item, self.attrs.maj_sep, self.attrs.y_item_size, \
                              self.attrs.min_per_maj, True)

    def draw_x_axis_with_labels_at_time(self, start_time, end_time):
        start_tick = max(0, self._get_bottom_tick(start_time))
        end_tick = min(self.num_maj - 1, self._get_top_tick(end_time))

        self.canvas.draw_x_axis(self.origin[0], self.origin[1], start_tick, end_tick, \
                                self.attrs.maj_sep, self.attrs.min_per_maj)
        self.canvas.draw_x_axis_labels(self.origin[0], self.origin[1], start_tick, \
                                end_tick, self.attrs.maj_sep, self.attrs.min_per_maj,
                                self.start_time + start_tick * self.attrs.time_per_maj,
                                self.attrs.time_per_maj, False)

    def draw_y_axis_with_labels(self):
        self.canvas.draw_y_axis(self.origin[0], self.origin[1], self._get_y_axis_height())
        self.canvas.draw_y_axis_labels(self.origin[0], self.origin[1], self._get_y_axis_height(), \
                                       self.y_item_list, self.attrs.y_item_size)

    def draw_suspend_triangle_at_time(self, time, task_no, cpu_no, selected=False):
        """Draws a suspension symbol for a dcertain task at an instant in time."""
        raise NotImplementedError

    def add_sel_suspend_triangle_at_time(self, time, task_no, cpu_no, event):
        """Same as above, except instead of drawing adds a selectable region at
        a certain time."""
        raise NotImplementedError

    def draw_resume_triangle_at_time(self, time, task_no, cpu_no, selected=False):
        """Draws a resumption symbol for a certain task at an instant in time."""
        raise NotImplementedError

    def add_sel_resume_triangle_at_time(self, time, task_no, cpu_no, event):
        """Same as above, except instead of drawing adds a selectable region at
        a certain time."""
        raise NotImplementedError

    def draw_completion_marker_at_time(self, time, task_no, cpu_no, selected=False):
        """Draws a completion marker for a certain task at an instant in time."""
        raise NotImplementedError

    def add_sel_completion_marker_at_time(self, time, task_no, cpu_no, event):
        """Same as above, except instead of drawing adds a selectable region at
        a certain time."""
        raise NotImplementedError

    def draw_release_arrow_at_time(self, time, task_no, job_no, selected=False):
        """Draws a release arrow at a certain time for some task and job"""
        raise NotImplementedError

    def add_sel_release_arrow_at_time(self, time, task_no, event):
        """Same as above, except instead of drawing adds a selectable region at
        a certain time."""
        raise NotImplementedError

    def draw_deadline_arrow_at_time(self, time, task_no, job_no, selected=False):
        """Draws a deadline arrow at a certain time for some task and job"""
        raise NotImplementedError

    def add_sel_deadline_arrow_at_time(self, time, task_no, event):
        """Same as above, except instead of drawing adds a selectable region at
        a certain time."""
        raise NotImplementedError

    def draw_action_symbol_at_time(self, time, task_no, cpu_no, action,
                                   job_no, selected=False):
        """Draws an action symbol at a certain time for some task and job"""
        raise NotImplementedError

    def add_sel_action_symbol_at_time(self, time, task_no, cpu_no, event):
        """Same as above, except instead of drawing adds a selectable region at
        a certain time."""
        raise NotImplementedError

    def draw_bar_at_time(self, start_time, end_time, task_no, cpu_no, job_no=None, clip_side=None):
        """Draws a bar over a certain time period for some task, optionally labelling it."""
        raise NotImplementedError

    def add_sel_bar_at_time(self, start_time, end_time, task_no, cpu_no, event):
        """Same as above, except instead of drawing adds a selectable region at
        a certain time."""
        raise NotImplementedError

    def draw_mini_bar_at_time(self, start_time, end_time, task_no, cpu_no, clip_side=None, job_no=None):
        """Draws a mini bar over a certain time period for some task, optionally labelling it."""
        raise NotImplementedError

    def add_sel_mini_bar_at_time(self, start_time, end_time, task_no, cpu_no, event):
        """Same as above, except instead of drawing adds a selectable region at
        a certain time."""
        raise NotImplementedError

class TaskGraph(Graph):
    def get_events_to_render(self, sched, regions, selectable=False):
        slots = {}

        self.min_time, self.max_time, self.min_item, self.max_item = None, None, None, None
        for region in regions:
            x, y, width, height = region
            start_time, end_time, start_item, end_item = self.get_offset_params(x, y, width, height)
            self._recomp_min_max(start_time, end_time, start_item, end_item)

            sched.get_time_slot_array().get_slots(slots,
                        start_time, end_time, start_item, end_item,
                        schedule.TimeSlotArray.TASK_LIST)


        if not selectable:
            self.draw_skeleton(self.min_time, self.max_time,
                               self.min_item, self.max_item)

        events_to_render = {}
        for layer in Canvas.LAYERS:
            events_to_render[layer] = {}

        for event in sched.get_time_slot_array().get_events(slots,
                schedule.TimeSlotArray.TASK_LIST,
                schedule.EVENT_LIST):
            events_to_render[event.get_layer()][event] = None

        return events_to_render

    def draw_suspend_triangle_at_time(self, time, task_no, cpu_no, selected=False):
        height = self._get_bar_height() * GraphFormat.BLOCK_TRIANGLE_FACTOR
        x = self.get_time_xpos(time)
        y = self.get_item_ypos(task_no) + self._get_bar_height() / 2.0 - height / 2.0
        self.canvas.draw_suspend_triangle(x, y, height, selected)

    def add_sel_suspend_triangle_at_time(self, time, task_no, cpu_no, event):
        height = self._get_bar_height() * GraphFormat.BLOCK_TRIANGLE_FACTOR
        x = self.get_time_xpos(time)
        y = self.get_item_ypos(task_no) + self._get_bar_height() / 2.0 - height / 2.0

        self.canvas.add_sel_suspend_triangle(x, y, height, event)

    def draw_resume_triangle_at_time(self, time, task_no, cpu_no, selected=False):
        height = self._get_bar_height() * GraphFormat.BLOCK_TRIANGLE_FACTOR
        x = self.get_time_xpos(time)
        y = self.get_item_ypos(task_no) + self._get_bar_height() / 2.0 - height / 2.0

        self.canvas.draw_resume_triangle(x, y, height, selected)

    def add_sel_resume_triangle_at_time(self, time, task_no, cpu_no, event):
        height = self._get_bar_height() * GraphFormat.BLOCK_TRIANGLE_FACTOR
        x = self.get_time_xpos(time)
        y = self.get_item_ypos(task_no) + self._get_bar_height() / 2.0 - height / 2.0

        self.canvas.add_sel_resume_triangle(x, y, height, event)

    def draw_completion_marker_at_time(self, time, task_no, cpu_no, selected=False):
        height = self._get_bar_height() * GraphFormat.COMPLETION_MARKER_FACTOR
        x = self.get_time_xpos(time)
        y = self.get_item_ypos(task_no) + self._get_bar_height() - height

        self.canvas.draw_completion_marker(x, y, height, selected)

    def add_sel_completion_marker_at_time(self, time, task_no, cpu_no, event):
        height = self._get_bar_height() * GraphFormat.COMPLETION_MARKER_FACTOR

        x = self.get_time_xpos(time)
        y = self.get_item_ypos(task_no) + self._get_bar_height() - height

        self.canvas.add_sel_completion_marker(x, y, height, event)

    def draw_release_arrow_at_time(self, time, task_no, job_no=None, selected=False):
        height = self._get_bar_height() * GraphFormat.BIG_ARROW_FACTOR

        x = self.get_time_xpos(time)
        y = self.get_item_ypos(task_no) + self._get_bar_height() - height

        self.canvas.draw_release_arrow_big(x, y, height, selected)

    def add_sel_release_arrow_at_time(self, time, task_no, event):
        height = self._get_bar_height() * GraphFormat.BIG_ARROW_FACTOR

        x = self.get_time_xpos(time)
        y = self.get_item_ypos(task_no) + self._get_bar_height() - height

        self.canvas.add_sel_release_arrow_big(x, y, height, event)

    def draw_deadline_arrow_at_time(self, time, task_no, job_no=None, selected=False):
        height = self._get_bar_height() * GraphFormat.BIG_ARROW_FACTOR

        x = self.get_time_xpos(time)
        y = self.get_item_ypos(task_no)

        self.canvas.draw_deadline_arrow_big(x, y, height, selected)

    def add_sel_deadline_arrow_at_time(self, time, task_no, event):
        height = self._get_bar_height() * GraphFormat.BIG_ARROW_FACTOR

        x = self.get_time_xpos(time)
        y = self.get_item_ypos(task_no)

        self.canvas.add_sel_deadline_arrow_big(x, y, height, event)

    def draw_action_symbol_at_time(self, time, task_no, cpu_no, action,
                                   job_no=None, selected=False):
        x = self.get_time_xpos(time)
        y = None

        if task_no != -1:
            y = self.get_item_ypos(task_no)
        else:
            y = self.origin[1]

        height = 1.5 * (self.get_item_ypos(0) - self.get_item_yorigin(0))

        self.canvas.draw_action_symbol(cpu_no, action, x, y, height, selected)

    def add_sel_action_symbol_at_time(self, time, task_no, cpu_no, event):
        x = self.get_time_xpos(time)
        y = None

        if task_no != -1:
            y = self.get_item_ypos(task_no)
        else:
            y = self.origin[1]

        height = 1.5 * (self.get_item_ypos(0) - self.get_item_yorigin(0))

        self.canvas.add_sel_action_symbol(x, y, height, event)

    def draw_bar_at_time(self, start_time, end_time, task_no, cpu_no, job_no=None, clip_side=None, selected=False):
        if start_time > end_time:
            raise ValueError("Litmus is not a time machine")

        x = self.get_time_xpos(start_time)
        y = self.get_item_ypos(task_no)
        width = self._get_bar_width(start_time, end_time)
        height = self._get_bar_height()

        self.canvas.draw_bar(x, y, width, height, cpu_no, clip_side, selected)

        # if a job number is specified, we want to draw a superscript and subscript for the task and job number, respectively
        if job_no is not None:
            x += GraphFormat.BAR_LABEL_OFS
            y += self.attrs.y_item_size * GraphFormat.BAR_SIZE_FACTOR / 2.0
            self.canvas.draw_label_with_sscripts('T', str(task_no), str(job_no), x, y, \
                GraphFormat.DEF_FOPTS_BAR, GraphFormat.DEF_FOPTS_BAR_SSCRIPT, AlignMode.LEFT, AlignMode.CENTER)

    def add_sel_bar_at_time(self, start_time, end_time, task_no, cpu_no, event):
        if start_time > end_time:
            raise ValueError("Litmus is not a time machine")

        x = self.get_time_xpos(start_time)
        y = self.get_item_ypos(task_no)
        width = self._get_bar_width(start_time, end_time)
        height = self._get_bar_height()

        self.canvas.add_sel_bar(x, y, width, height, event)

    def draw_mini_bar_at_time(self, start_time, end_time, task_no, cpu_no, job_no=None, clip_side=None, selected=False):
        if start_time > end_time:
            raise ValueError("Litmus is not a time machine")

        x = self.get_time_xpos(start_time)
        y = self.get_item_ypos(task_no) - self._get_mini_bar_ofs()
        width = self._get_bar_width(start_time, end_time)
        height = self._get_mini_bar_height()

        self.canvas.draw_mini_bar(x, y, width, height, Canvas.NULL_PATTERN, clip_side, selected)

        if job_no is not None:
            x += GraphFormat.MINI_BAR_LABEL_OFS
            y += self.attrs.y_item_size * GraphFormat.MINI_BAR_SIZE_FACTOR / 2.0
            self.canvas.draw_label_with_sscripts('T', str(task_no), str(job_no), x, y, \
                GraphFormat.DEF_FOPTS_MINI_BAR, GraphFormat.DEF_FOPTS_MINI_BAR_SSCRIPT, AlignMode.LEFT, AlignMode.CENTER)

    def add_sel_mini_bar_at_time(self, start_time, end_time, task_no, cpu_no, event):
        x = self.get_time_xpos(start_time)
        y = self.get_item_ypos(task_no) - self._get_mini_bar_ofs()
        width = self._get_bar_width(start_time, end_time)
        height = self._get_mini_bar_height()

        self.canvas.add_sel_mini_bar(x, y, width, height, event)

class CpuGraph(Graph):
    def get_events_to_render(self, sched, regions, selectable=False):
        BOTTOM_EVENTS = [schedule.ReleaseEvent, schedule.DeadlineEvent, schedule.InversionStartEvent,
                     schedule.InversionEndEvent, schedule.InversionDummy]
        TOP_EVENTS = [schedule.SuspendEvent, schedule.ResumeEvent, schedule.CompleteEvent,
                  schedule.SwitchAwayEvent, schedule.SwitchToEvent, schedule.IsRunningDummy]

        if not regions:
            return {}

        top_slots = {}
        bottom_slots = {}

        self.min_time, self.max_time, self.min_item, self.max_item = None, None, None, None
        for region in regions:
            x, y, width, height = region
            start_time, end_time, start_item, end_item = self.get_offset_params(x, y, width, height)
            self._recomp_min_max(start_time, end_time, start_item, end_item)

            sched.get_time_slot_array().get_slots(top_slots,
                        start_time, end_time, start_item, end_item,
                        schedule.TimeSlotArray.CPU_LIST)

            if end_item >= len(self.y_item_list):
                # we are far down enough that we should render the releases and deadlines and inversions,
                # which appear near the x-axis
                sched.get_time_slot_array().get_slots(bottom_slots,
                        start_time, end_time, 0, sched.get_num_cpus(),
                        schedule.TimeSlotArray.CPU_LIST)

        if not selectable:
            self.draw_skeleton(self.min_time, self.max_time,
                               self.min_item, self.max_item)

        events_to_render = {}
        for layer in Canvas.LAYERS:
            events_to_render[layer] = {}

        for event in sched.get_time_slot_array().get_events(top_slots,
                schedule.TimeSlotArray.CPU_LIST,
                TOP_EVENTS):
            events_to_render[event.get_layer()][event] = None
        for event in sched.get_time_slot_array().get_events(bottom_slots,
                schedule.TimeSlotArray.CPU_LIST,
                BOTTOM_EVENTS):
            events_to_render[event.get_layer()][event] = None

        return events_to_render

    def render(self, schedule, start_time=None, end_time=None):
        if end_time < start_time:
            raise ValueError('start must be less than end')

        if start_time is None:
            start_time = self.start
        if end_time is None:
            end_time = self.end
        start_slot = self.get_time_slot(start_time)
        end_slot = min(len(self.time_slots), self.get_time_slot(end_time) + 1)

        for layer in Canvas.LAYERS:
            prev_events = {}
            for i in range(start_slot, end_slot):
                for event in self.time_slots[i]:
                    event.render(graph, layer, prev_events)

    def draw_suspend_triangle_at_time(self, time, task_no, cpu_no, selected=False):
        height = self._get_bar_height() * GraphFormat.BLOCK_TRIANGLE_FACTOR
        x = self.get_time_xpos(time)
        y = self.get_item_ypos(cpu_no) + self._get_bar_height() / 2.0 - height / 2.0
        self.canvas.draw_suspend_triangle(x, y, height, selected)

    def add_sel_suspend_triangle_at_time(self, time, task_no, cpu_no, event):
        height = self._get_bar_height() * GraphFormat.BLOCK_TRIANGLE_FACTOR
        x = self.get_time_xpos(time)
        y = self.get_item_ypos(cpu_no) + self._get_bar_height() / 2.0 - height / 2.0

        self.canvas.add_sel_suspend_triangle(x, y, height, event)

    def draw_resume_triangle_at_time(self, time, task_no, cpu_no, selected=False):
        height = self._get_bar_height() * GraphFormat.BLOCK_TRIANGLE_FACTOR
        x = self.get_time_xpos(time)
        y = self.get_item_ypos(cpu_no) + self._get_bar_height() / 2.0 - height / 2.0

        self.canvas.draw_resume_triangle(x, y, height, selected)

    def add_sel_resume_triangle_at_time(self, time, task_no, cpu_no, event):
        height = self._get_bar_height() * GraphFormat.BLOCK_TRIANGLE_FACTOR
        x = self.get_time_xpos(time)
        y = self.get_item_ypos(cpu_no) + self._get_bar_height() / 2.0 - height / 2.0

        self.canvas.add_sel_resume_triangle(x, y, height, event)

    def draw_completion_marker_at_time(self, time, task_no, cpu_no, selected=False):
        height = self._get_bar_height() * GraphFormat.COMPLETION_MARKER_FACTOR
        x = self.get_time_xpos(time)
        y = self.get_item_ypos(cpu_no) + self._get_bar_height() - height

        self.canvas.draw_completion_marker(x, y, height, selected)

    def add_sel_completion_marker_at_time(self, time, task_no, cpu_no, event):
        height = self._get_bar_height() * GraphFormat.COMPLETION_MARKER_FACTOR

        x = self.get_time_xpos(time)
        y = self.get_item_ypos(cpu_no) + self._get_bar_height() - height

        self.canvas.add_sel_completion_marker(x, y, height, event)

    def draw_release_arrow_at_time(self, time, task_no, job_no=None, selected=False):
        if job_no is None and task_no is not None:
            raise ValueError("Must specify a job number along with the task number")

        height = self._get_bar_height() * GraphFormat.SMALL_ARROW_FACTOR

        x = self.get_time_xpos(time)
        y = self.origin[1] - height

        self.canvas.draw_release_arrow_small(x, y, height, selected)

        if task_no is not None:
            y -= GraphFormat.ARROW_LABEL_OFS
            self.canvas.draw_label_with_sscripts('T', str(task_no), str(job_no), x, y, \
                                          GraphFormat.DEF_FOPTS_ARROW, GraphFormat.DEF_FOPTS_ARROW_SSCRIPT, \
                                          AlignMode.CENTER, AlignMode.BOTTOM)

    def add_sel_release_arrow_at_time(self, time, task_no, event):
        height = self._get_bar_height() * GraphFormat.SMALL_ARROW_FACTOR

        x = self.get_time_xpos(time)
        y = self.origin[1] - height

        self.canvas.add_sel_release_arrow_small(x, y, height, event)

    def draw_deadline_arrow_at_time(self, time, task_no, job_no=None, selected=False):
        if job_no is None and task_no is not None:
            raise ValueError("Must specify a job number along with the task number")

        height = self._get_bar_height() * GraphFormat.SMALL_ARROW_FACTOR

        x = self.get_time_xpos(time)
        y = self.origin[1] - height

        self.canvas.draw_deadline_arrow_small(x, y, height, selected)

        if task_no is not None:
            y -= GraphFormat.ARROW_LABEL_OFS
            self.canvas.draw_label_with_sscripts('T', str(task_no), str(job_no), x, y, \
                                          GraphFormat.DEF_FOPTS_ARROW, GraphFormat.DEF_FOPTS_ARROW_SSCRIPT, \
                                          AlignMode.CENTER, AlignMode.BOTTOM)

    def add_sel_deadline_arrow_at_time(self, time, task_no, event):
        height = self._get_bar_height() * GraphFormat.SMALL_ARROW_FACTOR

        x = self.get_time_xpos(time)
        y = self.get_item_ypos(task_no)

        self.canvas.add_sel_deadline_arrow_small(x, y, height, event)

    def draw_action_symbol_at_time(self, time, task_no, cpu_no, action,
                                   job_no=None, selected=False):
        x = self.get_time_xpos(time)
        y = self.get_item_ypos(cpu_no)

        height = 1.5 * (y - self.get_item_yorigin(cpu_no))

        self.canvas.draw_action_symbol(task_no, action, x, y, height, selected)

    def add_sel_action_symbol_at_time(self, time, task_no, cpu_no, event):
        x = self.get_time_xpos(time)
        y = self.get_item_ypos(cpu_no)

        height = 1.5 * (y - self.get_item_yorigin(cpu_no))

        self.canvas.add_sel_action_symbol(x, y, height, event)

    def draw_bar_at_time(self, start_time, end_time, task_no, cpu_no, job_no=None, clip_side=None, selected=False):
        if start_time > end_time:
            raise ValueError("Litmus is not a time machine")

        x = self.get_time_xpos(start_time)
        y = self.get_item_ypos(cpu_no)
        width = self._get_bar_width(start_time, end_time)
        height = self._get_bar_height()

        self.canvas.draw_bar(x, y, width, height, task_no, clip_side, selected)

        # if a job number is specified, we want to draw a superscript and subscript for the task and job number, respectively
        if job_no is not None:
            x += GraphFormat.BAR_LABEL_OFS
            y += self.attrs.y_item_size * GraphFormat.BAR_SIZE_FACTOR / 2.0
            self.canvas.draw_label_with_sscripts('T', str(task_no), str(job_no), x, y, \
                                                 GraphFormat.DEF_FOPTS_BAR, GraphFormat.DEF_FOPTS_BAR_SSCRIPT, \
                                                 AlignMode.LEFT, AlignMode.CENTER)

    def add_sel_bar_at_time(self, start_time, end_time, task_no, cpu_no, event):
        x = self.get_time_xpos(start_time)
        y = self.get_item_ypos(cpu_no)
        width = self._get_bar_width(start_time, end_time)
        height = self._get_bar_height()

        self.canvas.add_sel_bar(x, y, width, height, event)

    def draw_mini_bar_at_time(self, start_time, end_time, task_no, cpu_no, job_no=None, clip_side=None, selected=False):
        if start_time > end_time:
            raise ValueError("Litmus is not a time machine")

        x = self.get_time_xpos(start_time)
        y = self.get_item_ypos(len(self.y_item_list))
        width = self._get_bar_width(start_time, end_time)
        height = self._get_mini_bar_height()

        self.canvas.draw_mini_bar(x, y, width, height, task_no, clip_side, selected)

        if job_no is not None:
            x += GraphFormat.MINI_BAR_LABEL_OFS
            y += self.attrs.y_item_size * GraphFormat.MINI_BAR_SIZE_FACTOR / 2.0
            self.canvas.draw_label_with_sscripts('T', str(task_no), str(job_no), x, y, \
                GraphFormat.DEF_FOPTS_MINI_BAR, GraphFormat.DEF_FOPTS_MINI_BAR_SSCRIPT, AlignMode.LEFT, AlignMode.CENTER)

    def add_sel_mini_bar_at_time(self, start_time, end_time, task_no, cpu_no, event):
        x = self.get_time_xpos(start_time)
        y = self.get_item_ypos(len(self.y_item_list))
        width = self._get_bar_width(start_time, end_time)
        height = self._get_mini_bar_height()

        self.canvas.add_sel_mini_bar(x, y, width, height, event)

