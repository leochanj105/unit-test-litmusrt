#!/usr/bin/python
from schedule import *
from graph import *

"""The renderer, a glue object which converts a schedule to its representation
on a graph."""

class Renderer(object):
    def __init__(self, schedule):
        self.schedule = schedule

    def prepare_task_graph(self, SurfaceType=ImageSurface, attrs=GraphFormat()):
        """Outputs the fully-rendered graph (y-axis = tasks) to a Cairo ImageSurface"""
        item_list = self.get_task_item_list()
        start, end = self.schedule.get_time_bounds()
        self.graph = TaskGraph(CairoCanvas, SurfaceType(), start, end, item_list, attrs)

    def prepare_cpu_graph(self, SurfaceType=ImageSurface, attrs=GraphFormat()):
        item_list = ['CPU %d' % i for i in range(0, self.schedule.get_num_cpus())]
        start, end = self.schedule.get_time_bounds()
        self.graph = CpuGraph(CairoCanvas, SurfaceType(), start, end, item_list, attrs)

    def render_graph_full(self):
        """Does the heavy lifting for rendering a task or CPU graph, by scanning the schedule
        and drawing it piece by piece"""
        #graph.draw_axes('Time', '')
        self.schedule.render(self.graph)

    def write_out(self, fname):
        self.graph.surface.write_out(fname)

    def get_graph(self):
        return self.graph

    def get_schedule(self):
        return self.schedule

    def get_task_item_list(self):
        return [task.get_name() for task in self.schedule.get_task_list()]

