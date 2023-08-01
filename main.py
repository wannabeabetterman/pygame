import asyncio
import threading

from pywebio import platform

from source import manager
from source.webpages import main
from source.webpages.main import MainPage

def main():

    manager.reg_page('MainPage', MainPage())
    manager.reg_page('page', MainPage())

    manager.load_page('MainPage')


def server_thread():
    # https://zhuanlan.zhihu.com/p/101586682
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    platform.tornado.start_server(main, auto_open_webbrowser=True, port=7777, debug=True)


if __name__ == '__main__':
    threading.Thread(target=server_thread, daemon=False).start()
