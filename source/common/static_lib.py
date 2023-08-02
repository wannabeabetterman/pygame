from source.util import *

global W_KEYDOWN, HANDLE
W_KEYDOWN = False

exe_name='向日葵远程控制'
def get_handle():
    """获得句柄

    Returns:
        _type_: _description_
    """
    if True:

        handle = ctypes.windll.user32.FindWindowW(None, exe_name)
        if handle != 0:
            return handle


HANDLE = get_handle()


def search_handle():
    global HANDLE
    HANDLE = get_handle()


if __name__ == '__main__':
    pass
