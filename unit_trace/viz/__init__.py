try:
    import pygtk
    import gtk
    import gobject
    import cairo
    import visualizer
    import viewer
    import renderer
    import format
    import convert
except ImportError:
    import sys

    print 'Unit-Trace could not find pycairo and/or pygtk installed on your system. Please\n' \
            + 'make sure these libraries are installed before attempting to use the visualizer.'
    sys.exit(1)

gobject.signal_new('set-scroll-adjustments', viewer.GraphArea, gobject.SIGNAL_RUN_FIRST,
                        None, (gtk.Adjustment, gtk.Adjustment))
gobject.signal_new('update-event-description', viewer.GraphArea, gobject.SIGNAL_RUN_FIRST,
                        None, (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT))
gobject.signal_new('request-context-menu', viewer.GraphArea, gobject.SIGNAL_RUN_FIRST,
                        None, (gtk.gdk.Event, gobject.TYPE_PYOBJECT))
gobject.signal_new('request-refresh-events', viewer.GraphArea, gobject.SIGNAL_RUN_FIRST,
                        None, (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT,
                               gobject.TYPE_PYOBJECT))
gobject.signal_new('request-zoom-in', viewer.GraphWindow, gobject.SIGNAL_RUN_FIRST,
                        None, ())
gobject.signal_new('request-zoom-out', viewer.GraphWindow, gobject.SIGNAL_RUN_FIRST,
                        None, ())
