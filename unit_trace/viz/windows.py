"""Module for various miscellanious GUI windows."""

import pygtk
import gtk
import gobject

class TextInputDialog(gtk.Dialog):
    WINDOW_WIDTH_REQ = 250
    WINDOW_HEIGHT_REQ = 100

    def __init__(self, title, label, parent_window=None):
        super(TextInputDialog, self).__init__(title, parent_window,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                            gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        label_widget = gtk.Label(label)
        label_widget.set_alignment(0.0, 0.0)
        self.text_input = gtk.Entry()
        label_widget.show()
        self.text_input.show()

        vbox = self.get_content_area()

        vbox.pack_start(label_widget, False, False, 0)
        vbox.pack_start(self.text_input, False, False, 0)
        vbox.show()

        self.set_resizable(False)

        self.set_size_request(TextInputDialog.WINDOW_WIDTH_REQ, TextInputDialog.WINDOW_HEIGHT_REQ)

    def get_input(self):
        return self.text_input.get_text()

class InfoWindow(gtk.Window):
    """Window designed to show information about an event."""

    WINDOW_WIDTH_REQ = 400
    WINDOW_HEIGHT_REQ = 300

    def __init__(self):
        super(InfoWindow, self).__init__(gtk.WINDOW_TOPLEVEL)

        self.frm = gtk.Frame()

        self.connect('delete_event', gtk.Widget.hide_on_delete)

        self.text_view = gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.show()
        self.frm.add(self.text_view)
        self.frm.show()

        self.vbox = gtk.VBox(False, 0)
        self.vbox.pack_start(self.frm, True, True, 0)
        self.vbox.show()

        self.add(self.vbox)

        self.set_default_size(InfoWindow.WINDOW_WIDTH_REQ, InfoWindow.WINDOW_HEIGHT_REQ)
        self.set_title('Event Details')

    def set_event(self, event):
        self.text_view.get_buffer().set_text(event.str_long())
        self.frm.set_label('Details for ' + event.get_name())
