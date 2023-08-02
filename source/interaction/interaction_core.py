import ctypes
import inspect
import math
import random
import threading
import time
from asyncio.log import logger

import cv2
import numpy as np

from source.common import static_lib
from source.manager.button_manager import Button
from source.manager.img_manager import ImgIcon
from source.test.util import euclidean_distance_plist, crop

IMG_RATE = 0
IMG_POSI = 1
IMG_POINT = 2
IMG_RECT = 3
IMG_BOOL = 4
IMG_BOOLRATE = 5

winname_default = ["Genshin Impact", "原神"]


def before_operation(print_log=True):
    def outwrapper(func):
        def wrapper(*args, **kwargs):
            func_name = inspect.getframeinfo(inspect.currentframe().f_back)[2]
            func_name_2 = inspect.getframeinfo(inspect.currentframe().f_back.f_back)[2]

            if print_log:
                logger.trace(
                    f" operation: {func.__name__} | args: {args[1:]} | {kwargs} | function name: {func_name} & {func_name_2}")
            return func(*args, **kwargs)

        return wrapper

    return outwrapper


GetDC = ctypes.windll.user32.GetDC
CreateCompatibleDC = ctypes.windll.gdi32.CreateCompatibleDC
GetClientRect = ctypes.windll.user32.GetClientRect
CreateCompatibleBitmap = ctypes.windll.gdi32.CreateCompatibleBitmap
SelectObject = ctypes.windll.gdi32.SelectObject
BitBlt = ctypes.windll.gdi32.BitBlt
SRCCOPY = 0x00CC0020
GetBitmapBits = ctypes.windll.gdi32.GetBitmapBits
DeleteObject = ctypes.windll.gdi32.DeleteObject
ReleaseDC = ctypes.windll.user32.ReleaseDC
PostMessageW = ctypes.windll.user32.PostMessageW
MapVirtualKeyW = ctypes.windll.user32.MapVirtualKeyW


class InteractionBGD:
    """
    default size:1920x1080
    support size:1920x1080
    thanks for https://zhuanlan.zhihu.com/p/361569101
    """

    def __init__(self):
        logger.info("InteractionBGD created")
        self.WHEEL_DELTA = 120
        self.DEFAULT_DELAY_TIME = 0.05
        self.DEBUG_MODE = False
        self.CONSOLE_ONLY = False
        self.itt_exec = None
        self.capture_obj = None
        self.operation_lock = threading.Lock()
        if True:
            import source.interaction.interaction_normal
            self.itt_exec = source.interaction.interaction_normal.InteractionNormal()

        if True:
            from source.interaction.capture import WindowsCapture
            self.capture_obj = WindowsCapture()

        self.key_status = {'w': False}
        self.key_freeze = {}

    def capture(self, posi=None, shape='yx', jpgmode=None, check_shape=True):
        """窗口客户区截图

        Args:
            posi ( [x1,y1,x2,y2] ): 截图区域的坐标, y2>y1,x2>x1. 全屏截图时为None。
            shape (str): 为'yx'或'xy'.决定返回数组是[1080,1920]或[1920,1080]。
            jpgmode(int): 
                0:return jpg (3 channels, delete the alpha channel)
                1:return genshin background channel, background color is black
                2:return genshin ui channel, background color is black

        Returns:
            numpy.ndarray: 图片数组
        """

        ret = self.capture_obj.capture()

        if posi is not None:
            ret = crop(ret, posi)
        if ret.shape[2] == 3:
            pass
        elif jpgmode == 0:
            ret = ret[:, :, :3]
        elif jpgmode == 1:
            ret = self.png2jpg(ret, bgcolor='black', channel='bg')
        elif jpgmode == 2:
            ret = self.png2jpg(ret, bgcolor='black', channel='ui')  # before v3.1
        elif jpgmode == 3:
            ret = ret[:, :, :3]
        return ret

    def match_multiple_img(self, img, template, is_gray=False, is_show_res: bool = False, ret_mode=IMG_POINT,
                           threshold=0.98, ignore_close=False):
        """多图片识别

        Args:
            img (numpy): 截图Mat
            template (numpy): 要匹配的样板图片
            is_gray (bool, optional): 是否启用灰度匹配. Defaults to False.
            is_show_res (bool, optional): 结果显示. Defaults to False.
            ret_mode (int, optional): 返回值模式,目前只有IMG_POINT. Defaults to IMG_POINT. 
            threshold (float, optional): 最小匹配度. Defaults to 0.98.

        Returns:
            list[list[], ...]: 匹配成功的坐标列表
        """
        if is_gray:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            template = cv2.cvtColor(template, cv2.COLOR_BGRA2GRAY)
        res = cv2.matchTemplate(img, template, cv2.TM_CCORR_NORMED)

        loc = np.where(res >= threshold)  # 匹配结果小于阈值的位置

        matched_coordinates = sorted(zip(*loc[::-1]), key=lambda x: res[x[1], x[0]], reverse=True)
        if ignore_close:
            ret_coordinates = []
            for i in matched_coordinates:
                if len(ret_coordinates) == 0:
                    ret_coordinates.append(i)
                    continue
                if min(euclidean_distance_plist(i, ret_coordinates)) >= 15:
                    ret_coordinates.append(i)
            return ret_coordinates

        return matched_coordinates

    def similar_img(self, img, target, is_gray=False, is_show_res: bool = False, ret_mode=IMG_RATE):
        """单个图片匹配

        Args:
            img (numpy): Mat
            template (numpy): 要匹配的样板图片
            is_gray (bool, optional): 是否启用灰度匹配. Defaults to False.
            is_show_res (bool, optional): 结果显示. Defaults to False.
            ret_mode (int, optional): 返回值模式. Defaults to IMG_RATE.

        Returns:
            float/(float, list[]): 匹配度或者匹配度和它的坐标
        """
        if is_gray:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            target = cv2.cvtColor(target, cv2.COLOR_BGRA2GRAY)
        # 模板匹配，将alpha作为mask，TM_CCORR_NORMED方法的计算结果范围为[0, 1]，越接近1越匹配
        # img_manager.qshow(img)
        result = cv2.matchTemplate(img, target, cv2.TM_CCORR_NORMED)  # TM_CCOEFF_NORMED
        # 获取结果中最大值和最小值以及他们的坐标
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        if is_show_res:
            cv2.waitKey()
        # 在窗口截图中匹配位置画红色方框
        matching_rate = max_val

        if ret_mode == IMG_RATE:
            return matching_rate
        elif ret_mode == IMG_POSI:
            return matching_rate, max_loc

    def get_img_position(self, imgicon: ImgIcon, is_gray=False, is_log=False):
        """获得图片在屏幕上的坐标

        Args:
            imgicon (img_manager.ImgIcon): imgicon对象
            is_gray (bool, optional): 是否启用灰度匹配. Defaults to False.
            is_log (bool, optional): 是否打印日志. Defaults to False.

        Returns:
            list[]/bool: 返回坐标或False
        """
        upper_func_name = inspect.getframeinfo(inspect.currentframe().f_back)[2]
        # if imgname in img_manager.alpha_dict:
        #     cap = self.capture()
        #     cap = self.png2jpg(cap, bgcolor='black', channel='ui', alpha_num=img_manager.alpha_dict[imgname])
        # else:
        cap = self.capture(posi=imgicon.cap_posi, jpgmode=imgicon.jpgmode)

        matching_rate, max_loc = self.similar_img(cap, imgicon.image, ret_mode=IMG_POSI)

        if imgicon.is_print_log(matching_rate >= imgicon.threshold):
            logger.debug(
                'imgname: ' + imgicon.name + 'max_loc: ' + str(max_loc) + ' |function name: ' + upper_func_name)

        if matching_rate >= imgicon.threshold:
            return max_loc
        else:
            return False

    def get_img_existence(self, imgicon: ImgIcon, is_gray=False, is_log=True, ret_mode=IMG_BOOL,
                          show_res=False, cap=None):
        """检测图片是否存在

        Args:
            imgicon (img_manager.ImgIcon): imgicon对象
            is_gray (bool, optional): 是否启用灰度匹配. Defaults to False.
            is_log (bool, optional): 是否打印日志. Defaults to False.

        Returns:
            bool: bool
        """
        # 获取当前函数方法名称
        upper_func_name = inspect.getframeinfo(inspect.currentframe().f_back)[2]

        if cap is None:
            cap = self.capture(posi=imgicon.cap_posi, jpgmode=imgicon.jpgmode)

        matching_rate = self.similar_img(cap, imgicon.image)

        if show_res:
            cv2.imshow(imgicon.name, cap)
            cv2.waitKey(100)

        if imgicon.is_print_log(matching_rate >= imgicon.threshold) and is_log:
            logger.debug(
                'imgname: ' + imgicon.name + 'matching_rate: ' + str(
                    matching_rate) + ' |function name: ' + upper_func_name)
        if ret_mode == IMG_BOOL:
            if matching_rate >= imgicon.threshold:
                return True
            else:
                return False
        elif ret_mode == IMG_BOOLRATE:
            if matching_rate >= imgicon.threshold:
                return matching_rate
            else:
                return False
        elif ret_mode == IMG_RATE:
            return matching_rate

    appear = get_img_existence

    def appear_then_click(self, inputvar, is_gray=False, is_log=False):
        """appear then click

        Args:
            inputvar (img_manager.ImgIcon/text_manager.TextTemplate/button_manager.Button)
            is_gray (bool, optional): 是否启用灰度匹配. Defaults to False.

        Returns:
            bool: bool,点击操作是否成功
        """

        if isinstance(inputvar, Button):
            imgicon = inputvar
            upper_func_name = inspect.getframeinfo(inspect.currentframe().f_back)[2]

            if not inputvar.click_retry_timer.reached():
                return False

            if inputvar.click_fail_timer.reached_and_reset():
                logger.error("appear then click fail")
                logger.info(f"{inputvar.name} {inputvar.click_position}")
                return False

            cap = self.capture(posi=imgicon.cap_posi, jpgmode=imgicon.jpgmode)

            if inputvar.is_bbg == False:
                matching_rate, click_posi = self.similar_img(imgicon.image, cap, is_gray=is_gray, ret_mode=IMG_POSI)
            else:
                matching_rate = self.similar_img(imgicon.image, cap, is_gray=is_gray)

            if imgicon.is_print_log(matching_rate >= imgicon.threshold) or is_log:
                logger.debug(
                    'imgname: ' + imgicon.name + 'matching_rate: ' + str(
                        matching_rate) + ' |function name: ' + upper_func_name)

            if matching_rate >= imgicon.threshold:
                if inputvar.is_bbg == True:
                    self.move_and_click(position=imgicon.click_position())
                else:
                    self.move_and_click(position=click_posi)
                logger.debug(f"appear then click: True: {imgicon.name} func: {upper_func_name}")
                inputvar.click_fail_timer.reset()
                inputvar.click_retry_timer.reset()
                return True
            else:
                return False

        elif isinstance(inputvar, img_manager.ImgIcon):
            imgicon = inputvar
            upper_func_name = inspect.getframeinfo(inspect.currentframe().f_back)[2]

            cap = self.capture(posi=imgicon.cap_posi, jpgmode=imgicon.jpgmode)

            matching_rate = self.similar_img(imgicon.image, cap, is_gray=is_gray)

            if imgicon.is_print_log(matching_rate >= imgicon.threshold) or is_log:
                logger.debug('imgname: ' + imgicon.name + 'matching_rate: ' + str(
                    matching_rate) + ' |function name: ' + upper_func_name)

            if matching_rate >= imgicon.threshold:
                p = imgicon.cap_posi
                center_p = [(p[0] + p[2]) / 2, (p[1] + p[3]) / 2]
                self.move_and_click([center_p[0], center_p[1]])
                logger.debug(f"appear then click: True: {imgicon.name} func: {upper_func_name}")
                return True
            else:
                return False

    def appear_then_click_groups(self, verify_img: ImgIcon, inputvar_list: list, stop_func,
                                 verify_mode=False):
        """
        Click each inputvar in list.
        
        """
        succ_flags = [False for i in len(inputvar_list)]
        while 1:
            time.sleep(0.1)
            if stop_func: return False
            if all(succ_flags):
                if self.get_img_existence(verify_img) == verify_mode:
                    return True
            for i in len(inputvar_list):
                r = self.appear_then_click(inputvar_list[i])
                if r: succ_flags[i] = True

    def appear_then_press(self, imgicon: ImgIcon, key_name, is_gray=False):
        """appear then press

        Args:
            imgicon (img_manager.ImgIcon): imgicon对象
            key_name (str): key_name
            is_gray (bool, optional): 是否启用灰度匹配. Defaults to False.

        Returns:
            bool: 操作是否成功
        """
        upper_func_name = inspect.getframeinfo(inspect.currentframe().f_back)[2]

        cap = self.capture(posi=imgicon.cap_posi, jpgmode=imgicon.jpgmode)

        matching_rate = self.similar_img(imgicon.image, cap, is_gray=is_gray)

        if imgicon.is_print_log(matching_rate >= imgicon.threshold):
            logger.debug(
                'imgname: ' + imgicon.name + 'matching_rate: ' + str(
                    matching_rate) + 'key_name:' + key_name + ' |function name: ' + upper_func_name)

        if matching_rate >= imgicon.threshold:
            self.key_press(key_name)
            return True
        else:
            return False

    def extract_white_letters(image, threshold=128):
        """_summary_

        Args:
            image (_type_): _description_
            threshold (int, optional): _description_. Defaults to 128.

        Returns:
            _type_: _description_
        """
        r, g, b = cv2.split(cv2.subtract((255, 255, 255, 0), image))
        minimum = cv2.min(cv2.min(r, g), b)
        maximum = cv2.max(cv2.max(r, g), b)
        return cv2.multiply(cv2.add(maximum, cv2.subtract(maximum, minimum)), 255.0 / threshold)

    # @staticmethod
    def png2jpg(self, png, bgcolor='black', channel='bg', alpha_num=50):
        """将截图的4通道png转换为3通道jpg

        Args:
            png (Mat/ndarray): 4通道图片
            bgcolor (str, optional): 背景的颜色. Defaults to 'black'.
            channel (str, optional): 提取背景或UI. Defaults to 'bg'.
            alpha_num (int, optional): 透明通道的大小. Defaults to 50.

        Returns:
            Mat/ndarray: 3通道图片
        """
        if bgcolor == 'black':
            bgcol = 0
        else:
            bgcol = 255

        jpg = png[:, :, :3]
        if channel == 'bg':
            over_item_list = png[:, :, 3] > alpha_num
        else:
            over_item_list = png[:, :, 3] < alpha_num
        jpg[:, :, 0][over_item_list] = bgcol
        jpg[:, :, 1][over_item_list] = bgcol
        jpg[:, :, 2][over_item_list] = bgcol
        return jpg

    # @staticmethod
    def color_sd(self, x_col, target_col):  # standard deviation
        """Not in use

        Args:
            x_col (_type_): _description_
            target_col (_type_): _description_

        Returns:
            _type_: _description_
        """
        ret = 0
        for i in range(min(len(x_col), len(target_col))):
            t = abs(x_col[i] - target_col[i])
            math.pow(t, 2)
            ret += t
        return math.sqrt(ret / min(len(x_col), len(target_col)))

    # @staticmethod
    def delay(self, x, randtime=False, isprint=True, comment=''):
        """延迟一段时间，单位为秒

        Args:
            x : 延迟时间/key words
            randtime (bool, optional): 是否启用加入随机秒. Defaults to True.
            isprint (bool, optional): 是否打印日志. Defaults to True.
            comment (str, optional): 日志注释. Defaults to ''.
        """
        if x == "animation":
            time.sleep(0.3)
            return
        if x == "2animation":
            time.sleep(0.6)
            return
        upper_func_name = inspect.getframeinfo(inspect.currentframe().f_back)[2]
        a = random.randint(-10, 10)
        if randtime:
            a = a * x * 0.02
            if x > 0.2 and isprint:
                logger.debug('delay: ' + str(x) + ' rand: ' +
                             str(x + a) + ' |function name: ' + upper_func_name + ' |comment: ' + comment)
            time.sleep(x + a)
        else:
            if x > 0.2 and isprint:
                logger.debug('delay: ' + str(x) + ' |function name: ' + upper_func_name + ' |comment: ' + comment)
            time.sleep(x)

    # @before_operation(print_log = False)
    # def DONTUSEget_mouse_pointDONTUSE(self):
    #     """获得当前鼠标在窗口内的位置 不要用！

    #     Returns:
    #         (x,y): 坐标
    #     """

    #     p = win32api.GetCursorPos()
    #     # print(p[0],p[1])
    #     #  GetWindowRect 获得整个窗口的范围矩形，窗口的边框、标题栏、滚动条及菜单等都在这个矩形内 
    #     x, y, w, h = win32gui.GetWindowRect(static_lib.HANDLE)
    #     # 鼠标坐标减去指定窗口坐标为鼠标在窗口中的坐标值
    #     pos_x = p[0] - x
    #     pos_y = p[1] - y
    #     return pos_x, pos_y

    @before_operation()
    def left_click(self):
        """左键点击
        
        """

        self.operation_lock.acquire()
        if True:
            logger.demo("左键点击")
        self.itt_exec.left_click()
        self.operation_lock.release()

    @before_operation()
    def left_down(self):
        """左键按下

        """

        self.operation_lock.acquire()
        if True:
            logger.demo("左键按下")
        self.itt_exec.left_down()
        self.operation_lock.release()

    @before_operation()
    def left_up(self):
        """左键抬起

        """

        self.operation_lock.acquire()
        if True:
            logger.demo("左键抬起")
        self.itt_exec.left_up()
        self.operation_lock.release()

    @before_operation()
    def left_double_click(self, dt=0.05):
        """左键双击

        Args:
            dt (float, optional): 间隔时间. Defaults to 0.05.
        """

        self.operation_lock.acquire()
        if True:
            logger.demo("左键双击")
        self.itt_exec.left_double_click(dt=dt)
        self.operation_lock.release()

    @before_operation()
    def right_click(self):
        """右键单击

        """

        self.operation_lock.acquire()
        if True:
            logger.demo("右键单击")
        self.itt_exec.right_click()
        self.operation_lock.release()
        self.delay(0.05)

    @before_operation()
    def middle_click(self):
        """点击鼠标中键
        """

        self.operation_lock.acquire()
        if True:
            logger.demo("点击鼠标中键")
        self.itt_exec.middle_click()
        self.operation_lock.release()

    @before_operation()
    def key_down(self, key):
        """按下按键

        Args:
            key (str): 按键代号。查阅vkCode.py
        """

        self.operation_lock.acquire()
        if True:
            logger.demo("按下按键: ") + str(key)
        if key == 'w':
            static_lib.W_KEYDOWN = True
        self.itt_exec.key_down(key)
        self.key_status[key] = True
        self.operation_lock.release()

        # if is_log:
        #     logger.debug(
        #         "keyDown " + key + ' |function name: ' + inspect.getframeinfo(inspect.currentframe().f_back)[2])

    @before_operation()
    def key_up(self, key):
        """松开按键

        Args:
            key (str): 按键代号。查阅vkCode.py
        """

        self.operation_lock.acquire()
        if True:
            logger.demo("松开按键: ") + str(key)
        if key == 'w':
            static_lib.W_KEYDOWN = False
        self.itt_exec.key_up(key)
        self.key_status[key] = False
        self.operation_lock.release()

        # if is_log:
        #     logger.debug("keyUp " + key + ' |function name: ' + inspect.getframeinfo(inspect.currentframe().f_back)[2])

    @before_operation()
    def key_press(self, key):
        """点击按键

        Args:
            key (str): 按键代号。查阅vkCode.py
        """

        self.operation_lock.acquire()
        if True:
            logger.demo("点击按键: ") + str(key)
        self.itt_exec.key_press(key)
        self.key_status[key] = False
        self.operation_lock.release()

    @before_operation(print_log=False)
    def move_to(self, x, y, relative=False):
        """移动鼠标到坐标（x, y)

        Args:
            x (int): 横坐标
            y (int): 纵坐标
            relative (bool): 是否为相对移动。
        """

        self.operation_lock.acquire()
        if True:
            logger.demo("移动鼠标到坐标: ") + f"{round(x, 0)},{round(y, 0)}"
        self.itt_exec.move_to(int(x), int(y), relative=relative)
        self.operation_lock.release()

    # @staticmethod
    def crop_image(self, imsrc, posilist):
        return imsrc[posilist[0]:posilist[2], posilist[1]:posilist[3]]

    @before_operation()
    def move_and_click(self, position, type='left', delay=0.3):

        self.operation_lock.acquire()
        if True:
            logger.demo("移动鼠标到坐标: ") + f"{round(position[0], 0)},{round(position[1], 0)} 并点击"
        x = int(position[0])
        y = int(position[1])

        self.itt_exec.move_to(int(x), int(y), relative=False)
        time.sleep(delay)

        if type == 'left':
            self.itt_exec.left_click()
        else:
            self.itt_exec.right_click()

        self.operation_lock.release()

    @before_operation()
    def drag(self, origin_xy: list, targe_xy: list):
        self.operation_lock.acquire()
        self.itt_exec.drag(origin_xy, targe_xy)
        self.operation_lock.release()

    @before_operation()
    def freeze_key(self, key, operate="down"):
        self.operation_lock.acquire()
        self.key_freeze[key] = self.key_status[key]
        if operate == "down":
            self.itt_exec.key_down(key)
        else:
            self.itt_exec.key_up(key)
        self.operation_lock.release()

    @before_operation()
    def unfreeze_key(self, key):
        self.operation_lock.acquire()
        operate = self.key_freeze[key]
        if operate:
            self.itt_exec.key_down(key)
        else:
            self.itt_exec.key_up(key)
        self.operation_lock.release()

    # def save_snapshot(self, reason: str = ''):
    #     img = self.capture()
    #     if img.shape[2] == 4:
    #         img = img[:, :, :3]
    #     img_path = os.path.join(ROOT_PATH, "Logs", get_logger_format_date(),
    #                             f"{reason} | {time.strftime('%H-%M-%S', time.localtime())}.jpg")
    #     logger.warning(f"Snapshot saved to {img_path}")
    #     cv2.imwrite(img_path, img)


def itt_test(itt: InteractionBGD):
    pass


itt = InteractionBGD()

if __name__ == '__main__':
    ib = InteractionBGD()
    rootpath = "D:\\Program Data\\vscode\\GIA\\genshin_impact_assistant\\dist\\imgs"
    # ib.similar_img_pixel(cv2.imread(rootpath+"\\yunjin_q.png"),cv2.imread(rootpath+"\\zhongli_q.png"))
    from source.manager import asset, img_manager

    itt.appear_then_click(asset.ButtonFoodEgg, is_log=True)
    # print(win32api.GetCursorPos())
    # win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 150, 150)
    # print(win32api.GetCursorPos())
    # a = ib.match_multiple_img(ib.capture(jpgmode=3), img_manager.get_img_from_name(img_manager.bigmap_TeleportWaypoint, reshape=False))
    # print(a)
    # ib.left_down()
    # time.sleep(1)
    # ib.move_to(200, 200)
    # img_manager.qshow(ib.capture())
    # ib.appear_then_click(button_manager.button_exit)
    # for i in range(20):
    #     pydirectinput.mouseDown(0,0)
    #     pydirectinput.moveRel(10,10)
    # win32api.SetCursorPos((300, 300))
    # pydirectinput.
    # a = ib.get_text_existence(asset.LEYLINEDISORDER)
    # print(a)
    # img_manager.qshow(ib.capture())
    print()
    while 1:
        # time.sleep(1)
        # print(ib.get_img_existence(img_manager.motion_flying), ib.get_img_existence(img_manager.motion_climbing),
        #       ib.get_img_existence(asset.motion_swimming))
        time.sleep(2)
        ib.move_and_click([100, 100], type="left")
        # print(ib.get_img_existence(img_manager.USE_20X2RESIN_DOBLE_CHOICES))
        # ib.appear_then_click(imgname=asset.USE_20RESIN_DOBLE_CHOICES)
        # ib.move_to(100,100)
