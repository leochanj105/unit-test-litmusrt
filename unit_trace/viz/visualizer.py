#!/usr/bin/python

import convert
import viewer
import renderer
import schedule
import format
import pygtk
import gtk

def visualizer(stream, time_per_maj):
    sched = convert.convert_trace_to_schedule(stream)
    sched.scan(time_per_maj)

    task_renderer = renderer.Renderer(sched)
    task_renderer.prepare_task_graph(attrs=format.GraphFormat(time_per_maj=time_per_maj))
    cpu_renderer = renderer.Renderer(sched)
    cpu_renderer.prepare_cpu_graph(attrs=format.GraphFormat(time_per_maj=time_per_maj))

    window = viewer.MainWindow()
    window.set_renderers({'Tasks' : task_renderer, 'CPUs' : cpu_renderer})

    gtk.main()
