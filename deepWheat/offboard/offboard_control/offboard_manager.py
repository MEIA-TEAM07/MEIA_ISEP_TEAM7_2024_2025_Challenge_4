# dentro de tu módulo offboard_control.py
import threading, rclpy
from offboard_control.offboard_control import OffboardControl

class OffboardManager:
    def __init__(self):
        rclpy.init()
        self.node = OffboardControl("")
        self._thread = threading.Thread(target=rclpy.spin, args=(self.node,), daemon=True)
        self._thread.start()
    
    def shutdown(self):
        self.node.destroy_node()
        rclpy.shutdown()
        self._thread.join()
