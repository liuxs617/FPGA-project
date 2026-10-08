"""""" # start delvewheel patch
def _delvewheel_patch_1_13_1():
    import os
    if os.path.isdir(libs_dir := os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, 'cv2_enumerate_cameras.libs'))):
        os.add_dll_directory(libs_dir)


_delvewheel_patch_1_13_1()
del _delvewheel_patch_1_13_1
# end delvewheel patch

__version__ = '1.4.0'

from cv2_enumerate_cameras.camera_info import CameraInfo
import platform

system = platform.system()

try:
    import cv2
    CAP_ANY = cv2.CAP_ANY
except ModuleNotFoundError:
    CAP_ANY = 0

if system == 'Windows':
    from cv2_enumerate_cameras.windows_backend import supported_backends, cameras_generator
elif system == 'Linux':
    from cv2_enumerate_cameras.linux_backend import supported_backends, cameras_generator
elif system == 'Darwin':
    from cv2_enumerate_cameras.macos_backend import supported_backends, cameras_generator
else:
    from cv2_enumerate_cameras.opencv_backend import supported_backends, cameras_generator


def enumerate_cameras(apiPreference=CAP_ANY):
    if apiPreference != CAP_ANY and apiPreference not in supported_backends:
        raise NotImplementedError(f"Unsupported backend: {apiPreference}!")

    if apiPreference == CAP_ANY:
        return [CameraInfo(i.index + i.backend, i.name, i.path, i.vid, i.pid, CAP_ANY) for j in supported_backends for i in enumerate_cameras(j)]
    else:
        return list(cameras_generator(apiPreference))


__all__ = ['CameraInfo', 'supported_backends', 'enumerate_cameras']
