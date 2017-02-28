import sys
if getattr(sys, 'frozen', False):
    print('Frozen.')
    print(sys._MEIPASS)
else:
    print('Not frozen.')


import traceback
from tierpsy.analysis.compress import selectVideoReader

if __name__ == '__main__':
    print('HOLA')
    print(sys.argv)
    try:
        if len(sys.argv) == 1:
            video_file = r'C:\Users\Avelino.Avelino_VM\OneDrive - Imperial College London\MWTracker\Tests\test_1\RawVideos\Capture_Ch1_18062015_140908.mjpg'
        else:
            video_file = sys.argv[1]

        vid, im_width, im_height, reader_type = selectVideoReader(video_file)
        print(im_width, im_height, reader_type)
    except Exception as e:
        print(e)
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(
            exc_type,
            exc_value,
            exc_traceback,
            limit=2,
            file=sys.stdout)
