from krita import *


class HorizontalInterface(QHBoxLayout):
    """
    A collection of interfaces in a horizontal layout container (QHBoxLayout)
    :param widgets: A list of widgets to add to the layout
    :param interfaces: A list of interfaces to add to the layout
    """

    def __init__(self, widgets=[], interfaces=[]):
        super().__init__()
        self.add_widgets(widgets)
        self.add_interfaces(interfaces)

    def add_widgets(self, widgets):
        """
        Add each widget from list of widgets to this interface
        :param widgets:
        :return:
        """
        for widget in widgets:
            self.addWidget(widget.widget)

    def add_interfaces(self, interfaces):
        """
        Add each interface from list of interfaces to this interface
        :param interfaces:
        :return:
        """
        for interface in interfaces:
            self.addLayout(interface)
