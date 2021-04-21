#coding=utf-8
import uwsgi
from uwsgidecorators import *
import shutil
import os,django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invest.settings")
django.setup()
from third.views.qiniufile import downloadFileToPath
from utils.somedef import encryptPdfFilesWithPassword, zipDirectory, addWaterMarkToPdfFiles

# def worker(arguments):
#     func_name = arguments.get(b'func_name').decode()
#     be_called_function = getattr(workerFunc, func_name)
#     be_called_function(arguments)
#     return uwsgi.SPOOL_OK
#
#
# # register the worker
# uwsgi.spooler = worker





def makeDirWithdirectoryobjs(directory_objs ,rootpath):
    if os.path.exists(rootpath):
        shutil.rmtree(rootpath)
    os.makedirs(rootpath)
    for file_obj in directory_objs:
        try:
            path = getPathWithFile(file_obj,rootpath)
            os.makedirs(path)
        except OSError:
            pass

def getPathWithFile(file_obj,rootpath,currentpath=None):
    if currentpath is None:
        currentpath = file_obj.filename
    if file_obj.parent is None:
        return rootpath + '/' + currentpath
    else:
        currentpath = file_obj.parent.filename + '/' + currentpath
        return getPathWithFile(file_obj.parent, rootpath, currentpath)



def downloadDataroomFiles(folder_path, file_qs, directory_qs):
    # 建立dataroom各级文件夹
    makeDirWithdirectoryobjs(directory_qs, folder_path)
    # 下载dataroom文件到对应文件夹下
    filepaths = []
    for file_obj in file_qs:
        path = getPathWithFile(file_obj, folder_path)
        downloadFileToPath(key=file_obj.realfilekey, bucket=file_obj.bucket, path=path)
        if os.path.exists(path):
            filetype = path.split('.')[-1]
            if filetype in ['pdf', u'pdf']:
                filepaths.append(path)
    return filepaths



def func_makeDataroomZipFile(arguments):

    folder_path = arguments.get('folder_path')
    password = arguments.get('password')

    file_qs = arguments.get('file_qs')
    directory_qs = arguments.get('directory_qs')
    virtual = arguments.get('virtual')

    filepaths = downloadDataroomFiles(folder_path, file_qs, directory_qs)
    addWaterMarkToPdfFiles(filepaths, virtual)
    encryptPdfFilesWithPassword(folder_path, password)
    zipDirectory(folder_path)


def logremainTime(folder_path):
    pass


@spool(pass_arguments=True)
def makeDataroomZipFile(*args, **kwargs):
    func_makeDataroomZipFile(kwargs)

