import pyqtgraph as pg
import pyqtgraph.console
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.dockarea import *
import numpy as np
from threading import Thread
import subprocess
import math
import time

COLOR_GREEN = 255
COLOR_ORANGE = 127
COLOR_RED = 0



ip_list = [
    "8.8.8.8",
    "8.8.4.4",
    "139.130.4.5"
]

network_nodes = []


def console_add(ip: str):
    ip_list.extend([ip])
    process()
    print("IP added")

def console_remove(ip: str):
    if ip in ip_list:
        ip_list.remove(ip)
        process()
        print("IP removed")
    else:
        print("IP not found")


class Graph(pg.GraphItem):
    def __init__(self):
        self.dragPoint = None
        self.dragOffset = None
        self.textItems = []
        pg.GraphItem.__init__(self)
        self.scatter.sigClicked.connect(self.clicked)
        
    def setData(self, **kwds):
        self.text = kwds.pop('text', [])
        self.data = kwds
        if 'pos' in self.data:
            npts = self.data['pos'].shape[0]
            self.data['data'] = np.empty(npts, dtype=[('index', int)])
            self.data['data']['index'] = np.arange(npts)
        self.setTexts(self.text)
        self.updateGraph()
        
    def setTexts(self, text):
        for i in self.textItems:
            i.scene().removeItem(i)
        self.textItems = []
        for t in text:
            item = pg.TextItem(t)
            self.textItems.append(item)
            item.setParentItem(self)
        
    def updateGraph(self):
        pg.GraphItem.setData(self, **self.data)
        for i,item in enumerate(self.textItems):
            item.setPos(*self.data['pos'][i])
        
    def clicked(self, pts):
        print(pts.getData())

# Enable antialiasing for prettier plots
pg.setConfigOptions(antialias=True)


# Set up window dock
app = QtGui.QApplication([])
win = QtGui.QMainWindow()
area = DockArea()
win.setCentralWidget(area)
win.resize(1000,500)
win.setWindowTitle("Network Graph")
dock_gui = Dock("Console")
dock_graph = Dock("Graph")
area.addDock(dock_gui, "left")
area.addDock(dock_graph, "right")
namespace = {
    'add': console_add, 
    'remove': console_remove
}
console = pyqtgraph.console.ConsoleWidget(namespace=namespace)
dock_gui.addWidget(console)
g = Graph()
glw = pg.GraphicsLayoutWidget()
glv = glw.addViewBox()
glv.addItem(g)
dock_graph.addWidget(glw)


class NetworkNode:
    _UNSURE = "unsure"
    _CONNECTED = "connected"
    _DISCONNECTED = "disconnected"
    def __init__(self, ip: str="127.0.0.1", pos=[0,0], conn=[0,0]):
        self.ip = ip
        self.position = pos
        self.connection = conn
        self.status = self._UNSURE

    def get_position(self):
        return self.position

    def get_connection(self):
        return self.connection

    def get_ip(self):
        return self.ip

    def get_status_color(self):
        if self.status == self._UNSURE:
            return COLOR_ORANGE
        elif self.status == self._CONNECTED:
            return COLOR_GREEN
        elif self.status == self._DISCONNECTED:
            return COLOR_RED
        else:
            return COLOR_RED

    def ping(self):
        args = ['ping', '-c', '1', '-W', '1', self.ip]
        p_ping = subprocess.Popen(
            args,
            shell=False,
            stdout=subprocess.PIPE
        )
        p_ping.communicate()
        return_code = p_ping.returncode
        if return_code == 0:
            self.status = self._CONNECTED
        else:
            self.status = self._DISCONNECTED


def get_node_coords(index: int, num: int, magnitude: int=5):
    if num <= 0 or index < 0:
        return [0, 0]
    comp = (2*math.pi) / num
    rad = comp * index
    x = math.cos(rad) * magnitude
    y = math.sin(rad) * magnitude
    return [x, y]


def get_network_nodes(ips):
    nodes = np.array([NetworkNode()])
    ip_len = len(ips)
    for i in range(0, ip_len):
        pos = get_node_coords(i, ip_len)
        nodes = np.append(
            nodes,
            [NetworkNode(
                ip=ips[i], 
                pos=pos, 
                conn=[0, i+1]
            )]
        )
    return nodes


def process_network_nodes(nodes):
    length = len(nodes)
    if length <= 0:
        return
    positions = np.array([nodes[0].get_position()])
    connections = np.array([nodes[0].get_connection()])
    labels = np.array([nodes[0].get_ip()])
    status = np.array([nodes[0].get_status_color()])
    for i in range(1, length):
        positions = np.append(
            positions,
            [nodes[i].get_position()],
            axis=0
        )
        connections = np.append(
            connections,
            [nodes[i].get_connection()],
            axis=0
        )
        labels = np.append(
            labels,
            [nodes[i].get_ip()],
            axis=0
        )
        status = np.append(
            status,
            [nodes[i].get_status_color()],
            axis=0
        )
    g.setData(
        pos=positions,
        adj=connections,
        size=1,
        pxMode=False,
        brush=status,
        text=labels
    )

def process(update=True):
    global network_nodes
    if update == True:
        network_nodes = get_network_nodes(ip_list)
    process_network_nodes(network_nodes)

class PingLoop(QtCore.QThread):
    update_signal = QtCore.pyqtSignal()
    def __init__(self):
        super().__init__()
        # QT Thread Timer
        self.update = lambda: process(update=False)
        self.update_signal.connect(self.update)
        self.ping_timer = QtCore.QTimer()
        self.ping_timer.moveToThread(self)
        self.ping_timer.timeout.connect(self.spawn_ping_loop)

    def run(self):
        self.ping_timer.start(2 * 1000)
        loop = QtCore.QEventLoop()
        loop.exec_()

    def spawn_ping_loop(self):
        Thread(target=self.ping_loop).start()

    def ping_loop(self):
        length = len(network_nodes)
        # Split pings into threads
        threads = []
        for i in range(0, length):
            t = Thread(target=network_nodes[i].ping)
            threads.append(t)
            t.start()
        # Wait for all threads to join
        for t in threads:
            t.join()
        self.update_signal.emit()

# Build nodes
process()

# Show window
win.show()

# Network Ping loop
p_loop = PingLoop()
p_loop.start()

## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    import sys
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
